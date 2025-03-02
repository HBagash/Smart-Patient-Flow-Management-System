def kalman_filter_update(measured_value, prev_estimate, prev_covariance,
                         process_var=100.0, measurement_var=200.0):

    predicted_est = prev_estimate
    predicted_cov = prev_covariance + process_var

    K = predicted_cov / (predicted_cov + measurement_var)
    new_est = predicted_est + K*(measured_value - predicted_est)
    new_cov = (1 - K)*predicted_cov
    return new_est, new_cov

def predict_appointment_kalman(appt_datetime, weeks_lookback=8):
    from django.utils import timezone
    from django.db.models.functions import ExtractWeekDay, ExtractHour
    from django.db.models import Count
    from detection.models import PersonSession

    now = timezone.now()
    start_lookback = now - timezone.timedelta(weeks=weeks_lookback)

    d_of_w = appt_datetime.weekday() + 1
    hr = appt_datetime.hour

    qs = (PersonSession.objects
          .filter(enter_timestamp__gte=start_lookback,
                  enter_timestamp__lt=now,
                  exit_timestamp__isnull=False)
          .annotate(dw=ExtractWeekDay('enter_timestamp'),
                    hh=ExtractHour('enter_timestamp'))
          .filter(dw=d_of_w, hh=hr)
          .order_by('enter_timestamp'))

    if not qs.exists():
        return 600.0
    
    x = 600.0
    P = 500.0
    Q = 100.0
    R = 200.0

    for session in qs:
        meas = float(session.duration_seconds or 600.0)
        x, P = kalman_filter_update(meas, x, P, Q, R)

    return x
