# appointments/utils.py

from datetime import timedelta
from django.db.models import Avg, Max, Min, Count, FloatField
from django.db.models.functions import TruncHour, ExtractWeekDay, ExtractHour, Cast
from django.utils import timezone
from detection.models import PersonSession
from .models import Appointment

def _exclude_outliers_qs(qs, field='duration_seconds', threshold=3, min_value=2):
    qs = qs.filter(**{f'{field}__gte': min_value})
    agg = qs.aggregate(mean_val=Avg(field), count_val=Count(field))
    mean_val = agg['mean_val'] or 0.0
    count_val = agg['count_val'] or 0
    if count_val < 2:
        return qs
    values = [float(v) for v in qs.values_list(field, flat=True)]
    std_val = (sum((v - mean_val)**2 for v in values) / (count_val - 1))**0.5
    cutoff = mean_val + threshold * std_val
    return qs.filter(**{f'{field}__lte': cutoff})

def get_overview_data(exclude_outliers=False, base_qs=None, custom_start=None, custom_end=None):
    """
    Summarize total arrivals and average/min/max wait time for the period [custom_start, custom_end].
    Defaults to the last 24 hours if no custom range is provided.
    """
    if base_qs is None:
        base_qs = PersonSession.objects.all()
    if not custom_end:
        custom_end = timezone.now()
    if not custom_start:
        custom_start = custom_end - timedelta(hours=24)

    qs = base_qs.filter(enter_timestamp__gte=custom_start, enter_timestamp__lte=custom_end)
    total_arrivals = qs.count()
    exited = qs.exclude(exit_timestamp__isnull=True).filter(duration_seconds__gt=1)
    if exclude_outliers:
        exited = _exclude_outliers_qs(exited, 'duration_seconds')
    agg = exited.annotate(
        duration_f=Cast('duration_seconds', FloatField())
    ).aggregate(
        avg_wait=Avg('duration_f'),
        max_wait=Max('duration_f'),
        min_wait=Min('duration_f')
    )
    return {
        'total_arrivals': total_arrivals,
        'avg_wait': agg['avg_wait'] or 0.0,
        'max_wait': agg['max_wait'] or 0.0,
        'min_wait': agg['min_wait'] or 0.0,
        'start_time': custom_start,
        'end_time': custom_end,
    }

def get_arrivals_by_hour_custom(start_time, end_time, exclude_outliers=False, base_qs=None):
    """
    Return a list of dictionaries with hour (as 'h') and count of arrivals in [start_time, end_time].
    """
    if base_qs is None:
        base_qs = PersonSession.objects.all()
    qs = base_qs.filter(enter_timestamp__gte=start_time, enter_timestamp__lte=end_time)
    if exclude_outliers:
        qs = qs.exclude(exit_timestamp__isnull=True)
        qs = _exclude_outliers_qs(qs, 'duration_seconds')
    qs = (qs
          .annotate(h=TruncHour('enter_timestamp'))
          .values('h')
          .annotate(count=Count('id'))
          .order_by('h'))
    return list(qs)

def get_wait_time_distribution_custom(start_time, end_time, bin_size=300, exclude_outliers=False, base_qs=None):
    """
    Return a histogram (list of (label, count)) of wait times (in seconds) in [start_time, end_time],
    with bins of size bin_size seconds.
    """
    if base_qs is None:
        base_qs = PersonSession.objects.all()
    qs = base_qs.filter(enter_timestamp__gte=start_time, enter_timestamp__lte=end_time)
    qs = qs.exclude(exit_timestamp__isnull=True).filter(duration_seconds__gt=1)
    if exclude_outliers:
        qs = _exclude_outliers_qs(qs, 'duration_seconds')
    if not qs.exists():
        return []
    bins = {}
    for s in qs:
        w = float(s.duration_seconds or 0)
        idx = int(w // bin_size)
        bins[idx] = bins.get(idx, 0) + 1
    sorted_bins = sorted(bins.items(), key=lambda x: x[0])
    results = []
    for bin_idx, count in sorted_bins:
        start_sec = bin_idx * bin_size
        end_sec = (bin_idx + 1) * bin_size
        label = f"{start_sec // 60}-{end_sec // 60} min"
        results.append((label, count))
    return results

def get_top_longest_waits_custom(start_time, end_time, top_n=10, base_qs=None):
    """
    Return the top N sessions (based on duration_seconds) in [start_time, end_time].
    """
    if base_qs is None:
        base_qs = PersonSession.objects.all()
    qs = (base_qs.filter(enter_timestamp__gte=start_time, enter_timestamp__lte=end_time)
          .exclude(exit_timestamp__isnull=True)
          .order_by('-duration_seconds')[:top_n])
    return list(qs)

def get_arrivals_by_day_of_week_custom(start_time, end_time, base_qs=None):
    """
    Return a list of (day_label, count) for each day-of-week in [start_time, end_time].
    """
    if base_qs is None:
        base_qs = PersonSession.objects.all()
    qs = (base_qs.filter(enter_timestamp__gte=start_time, enter_timestamp__lte=end_time)
          .annotate(dw=ExtractWeekDay('enter_timestamp'))
          .values('dw')
          .annotate(count=Count('id'))
          .order_by('dw'))
    dow_map = {1: 'Sun', 2: 'Mon', 3: 'Tue', 4: 'Wed', 5: 'Thu', 6: 'Fri', 7: 'Sat'}
    results = []
    for row in qs:
        label = dow_map.get(row['dw'], str(row['dw']))
        results.append((label, row['count']))
    return results

def get_time_of_day_pattern_custom(start_time, end_time, base_qs=None):
    """
    Return a list of (hour, count) for each hour (0-23) in [start_time, end_time].
    """
    if base_qs is None:
        base_qs = PersonSession.objects.all()
    qs = (base_qs.filter(enter_timestamp__gte=start_time, enter_timestamp__lte=end_time)
          .annotate(hh=ExtractHour('enter_timestamp'))
          .values('hh')
          .annotate(count=Count('id'))
          .order_by('hh'))
    hour_dict = {i: 0 for i in range(24)}
    for row in qs:
        h = row['hh']
        hour_dict[h] += row['count']
    return [(h, hour_dict[h]) for h in range(24)]

def get_wait_distribution_by_dow_custom(start_time, end_time, base_qs=None):
    """
    Return a list of (day_label, avg_wait_minutes) for each day-of-week in [start_time, end_time].
    """
    if base_qs is None:
        base_qs = PersonSession.objects.all()
    qs = (base_qs.filter(enter_timestamp__gte=start_time, enter_timestamp__lte=end_time)
          .exclude(exit_timestamp__isnull=True)
          .filter(duration_seconds__gt=1)
          .annotate(dw=ExtractWeekDay('enter_timestamp')))
    agg_qs = qs.values('dw').annotate(avg_wait=Avg('duration_seconds')).order_by('dw')
    dow_map = {1: 'Sun', 2: 'Mon', 3: 'Tue', 4: 'Wed', 5: 'Thu', 6: 'Fri', 7: 'Sat'}
    results = []
    for row in agg_qs:
        label = dow_map.get(row['dw'], str(row['dw']))
        avg_secs = row['avg_wait'] or 0.0
        avg_mins = avg_secs / 60.0
        results.append((label, avg_mins))
    return results

def get_wait_distribution_by_hour_custom(start_time, end_time, base_qs=None):
    """
    Return a list of (hour, avg_wait_minutes) for each hour (0-23) in [start_time, end_time].
    """
    if base_qs is None:
        base_qs = PersonSession.objects.all()
    qs = (base_qs.filter(enter_timestamp__gte=start_time, enter_timestamp__lte=end_time)
          .exclude(exit_timestamp__isnull=True)
          .filter(duration_seconds__gt=1)
          .annotate(hh=ExtractHour('enter_timestamp')))
    agg_qs = qs.values('hh').annotate(avg_wait=Avg('duration_seconds')).order_by('hh')
    hour_map = {i: 0.0 for i in range(24)}
    for row in agg_qs:
        h = row['hh']
        hour_map[h] = (row['avg_wait'] or 0.0) / 60.0
    results = []
    for i in range(24):
        results.append((i, hour_map[i]))
    return results

def generate_suggested_appointments(start_time, end_time, intended_duration):
    predicted_secs = predict_appointment_duration(start_time, weeks_lookback=8)
    predicted_duration_min = predicted_secs / 60.0
    delay_factor = max(0, predicted_duration_min - intended_duration)
    slot_interval = intended_duration + delay_factor

    created_slots = []
    current_time = start_time
    while current_time + timedelta(minutes=intended_duration) <= end_time:
        apt = Appointment(
            scheduled_start=current_time,
            duration_minutes=intended_duration,
            status='available'
        )
        apt.predicted_delay = max(0, int(predicted_secs - intended_duration * 60))
        created_slots.append(apt)
        current_time += timedelta(minutes=slot_interval)
    Appointment.objects.bulk_create(created_slots)
    return len(created_slots)

def predict_appointment_duration(appt_datetime, weeks_lookback=8):
    from django.db.models.functions import ExtractWeekDay, ExtractHour
    from django.db.models import Avg, Count

    now = timezone.now()
    start_lookback = now - timedelta(weeks=weeks_lookback)
    day_of_week = appt_datetime.weekday()  # Monday=0 ... Sunday=6
    hour_of_day = appt_datetime.hour

    qs = (PersonSession.objects
          .filter(enter_timestamp__gte=start_lookback,
                  enter_timestamp__lt=now,
                  exit_timestamp__isnull=False)
          .annotate(dw=ExtractWeekDay('enter_timestamp'),
                    hr=ExtractHour('enter_timestamp')))
    dnum = day_of_week + 1
    qs = qs.filter(dw=dnum, hr=hour_of_day)

    agg = qs.aggregate(avg_duration=Avg('duration_seconds'), sample_size=Count('id'))
    sample_size = agg['sample_size'] or 0
    avg_duration = agg['avg_duration'] or 0.0

    measured_value = avg_duration if sample_size >= 1 and avg_duration > 0 else 600.0

    from .kalman import kalman_filter_update
    x_k, p_k = kalman_filter_update(
        measured_value=measured_value,
        prev_estimate=600.0,
        prev_covariance=500.0,
        process_var=100.0,
        measurement_var=200.0
    )
    return x_k

from datetime import timedelta
from django.utils import timezone
from django.db.models import Avg, F, ExpressionWrapper, DurationField
from django.db.models.functions import ExtractWeekDay, ExtractHour

def predict_overrun_delay_for_appointment(appointment, weeks_lookback=4):
    """
    Predict the overrun delay (in seconds) for a given appointment using historical data of completed appointments.
    Considers the day of week, hour, and appointment length (±10 minutes tolerance).
    """
    now = timezone.now()
    start_lookback = now - timedelta(weeks=weeks_lookback)
    
    qs = appointment.__class__.objects.filter(
        status='completed',
        completed_at__gte=start_lookback
    )
    
    appointment_weekday = appointment.scheduled_start.weekday()  # Monday=0 ... Sunday=6
    appointment_hour = appointment.scheduled_start.hour
    
    qs = qs.annotate(
        apt_weekday=ExtractWeekDay('scheduled_start'),
        apt_hour=ExtractHour('scheduled_start')
    ).filter(
        apt_weekday=appointment_weekday + 1,  # Adjust for ExtractWeekDay (Sunday=1, Monday=2, etc.)
        apt_hour=appointment_hour,
        duration_minutes__gte=appointment.duration_minutes - 10,
        duration_minutes__lte=appointment.duration_minutes + 10,
    )
    
    # Optionally filter out extreme actual durations (for example, keep only those within 1.5x the scheduled duration)
    qs = qs.annotate(
        actual_duration=ExpressionWrapper(F('completed_at') - F('scheduled_start'), output_field=DurationField())
    ).filter(
        actual_duration__lte=timedelta(seconds=appointment.duration_minutes * 60 * 1.5)
    )
    
    agg = qs.aggregate(avg_actual=Avg('actual_duration'))
    avg_actual = agg['avg_actual']
    if not avg_actual:
        return 0

    avg_actual_seconds = avg_actual.total_seconds()
    scheduled_seconds = appointment.duration_minutes * 60
    predicted_delay = max(0, int(avg_actual_seconds - scheduled_seconds))
    return predicted_delay
