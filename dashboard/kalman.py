from django.utils import timezone
from django.db.models.functions import ExtractWeekDay, ExtractHour
from django.db.models import Count
from detection.models import PersonSession
from .utils import _exclude_outliers_qs

def kalman_filter_update(measured_value, prev_estimate, prev_covariance,
                         process_var=100.0, measurement_var=200.0):
    predicted_est = prev_estimate
    predicted_cov = prev_covariance + process_var
    K = predicted_cov / (predicted_cov + measurement_var)
    new_est = predicted_est + K*(measured_value - predicted_est)
    new_cov = (1 - K)*predicted_cov
    return new_est, new_cov

def predict_appointment_kalman(appt_datetime, weeks_lookback=8, exclude_outliers=True):
    now = timezone.now()
    start_lookback = now - timezone.timedelta(weeks=weeks_lookback)

    d_of_w = appt_datetime.weekday() + 1
    hr = appt_datetime.hour

    qs = PersonSession.objects.filter(
        enter_timestamp__gte=start_lookback,
        enter_timestamp__lt=now,
        exit_timestamp__isnull=False
    ).annotate(
        dw=ExtractWeekDay('enter_timestamp'),
        hh=ExtractHour('enter_timestamp')
    ).filter(
        dw=d_of_w,
        hh=hr
    ).order_by('enter_timestamp')  # oldest first so recent sessions carry more weight

    if exclude_outliers:
        qs = qs.filter(duration_seconds__gt=1)
        qs = _exclude_outliers_qs(qs, 'duration_seconds')

    sessions = list(qs)

    if not sessions:
        return 600.0

    # Initialise from the oldest matching session rather than a hardcoded value,
    # so sparse time slots aren't anchored to an arbitrary 10-minute prior.
    x = float(sessions[0].duration_seconds or 600.0)
    P = 1000.0  # high initial uncertainty — let the data speak quickly
    Q = 50.0    # small process noise: expected wait time changes slowly over time
    R = 200.0

    for session in sessions[1:]:
        meas = float(session.duration_seconds or x)
        x, P = kalman_filter_update(meas, x, P, Q, R)

    return x
