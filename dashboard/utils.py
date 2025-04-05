from datetime import timedelta
from django.db.models import Avg, Max, Min, Count, FloatField
from django.db.models.functions import TruncHour, ExtractWeekDay, ExtractHour, Cast
from django.utils import timezone
from detection.models import PersonSession

def _exclude_outliers_qs(qs, field='duration_seconds', threshold=3, min_value=2):
    qs = qs.filter(**{f'{field}__gte': min_value})
    agg = qs.aggregate(mean_val=Avg(field), count_val=Count(field))
    mean_val = agg['mean_val'] or 0.0
    count_val = agg['count_val'] or 0
    if count_val < 2:
        return qs
    values = [float(v) for v in qs.values_list(field, flat=True)]
    variance = sum((v - mean_val)**2 for v in values) / (count_val - 1)
    std_val = variance**0.5
    cutoff = mean_val + threshold*std_val
    return qs.filter(**{f'{field}__lte': cutoff})

def get_overview_data(exclude_outliers=False, base_qs=None, custom_start=None, custom_end=None):
    if base_qs is None:
        base_qs = PersonSession.objects.all()
    if not custom_end:
        custom_end = timezone.now()
    if not custom_start:
        custom_start = custom_end - timedelta(days=7)
    qs = base_qs.filter(enter_timestamp__gte=custom_start, enter_timestamp__lte=custom_end)
    if exclude_outliers:
        filtered = qs.exclude(exit_timestamp__isnull=True).filter(duration_seconds__gt=1)
        filtered = _exclude_outliers_qs(filtered, 'duration_seconds')
        total_arrivals = filtered.count()
        agg = filtered.annotate(duration_f=Cast('duration_seconds', FloatField())).aggregate(
            avg_wait=Avg('duration_f'),
            max_wait=Max('duration_f'),
            min_wait=Min('duration_f')
        )
    else:
        total_arrivals = qs.count()
        exited = qs.exclude(exit_timestamp__isnull=True).filter(duration_seconds__gt=1)
        agg = exited.annotate(duration_f=Cast('duration_seconds', FloatField())).aggregate(
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
    if base_qs is None:
        base_qs = PersonSession.objects.all()
    qs = base_qs.filter(enter_timestamp__gte=start_time, enter_timestamp__lte=end_time)
    if exclude_outliers:
        qs = qs.exclude(exit_timestamp__isnull=True).filter(duration_seconds__gt=1)
        qs = _exclude_outliers_qs(qs, 'duration_seconds')
    qs = qs.annotate(h=TruncHour('enter_timestamp')).values('h').annotate(count=Count('id')).order_by('h')
    return list(qs)

def get_wait_time_distribution_custom(start_time, end_time, bin_size=300,
                                      exclude_outliers=False, base_qs=None):
    if base_qs is None:
        base_qs = PersonSession.objects.all()
    qs = base_qs.filter(enter_timestamp__gte=start_time, enter_timestamp__lte=end_time) \
                .exclude(exit_timestamp__isnull=True).filter(duration_seconds__gt=1)
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
        label = f"{start_sec//60}-{end_sec//60} min"
        results.append((label, count))
    return results

def get_top_longest_waits_custom(start_time, end_time, top_n=10,
                                 base_qs=None, exclude_outliers=False):
    if base_qs is None:
        base_qs = PersonSession.objects.all()
    qs = base_qs.filter(enter_timestamp__gte=start_time, enter_timestamp__lte=end_time) \
                .exclude(exit_timestamp__isnull=True).order_by('-duration_seconds')
    if exclude_outliers:
        qs = qs.filter(duration_seconds__gt=1)
        qs = _exclude_outliers_qs(qs, 'duration_seconds')
    return list(qs[:top_n])

def get_arrivals_by_day_of_week_custom(start_time, end_time,
                                       exclude_outliers=False,
                                       base_qs=None):
    if base_qs is None:
        base_qs = PersonSession.objects.all()
    qs = base_qs.filter(enter_timestamp__gte=start_time, enter_timestamp__lte=end_time)
    if exclude_outliers:
        qs = qs.exclude(exit_timestamp__isnull=True).filter(duration_seconds__gt=1)
        qs = _exclude_outliers_qs(qs, 'duration_seconds')
    qs = qs.annotate(dw=ExtractWeekDay('enter_timestamp')).values('dw').annotate(count=Count('id')).order_by('dw')
    dow_map = {1:'Sun', 2:'Mon', 3:'Tue', 4:'Wed', 5:'Thu', 6:'Fri', 7:'Sat'}
    results = []
    for row in qs:
        d = row['dw']
        label = dow_map.get(d, str(d))
        results.append((label, row['count']))
    return results

def get_time_of_day_pattern_custom(start_time, end_time,
                                   exclude_outliers=False,
                                   base_qs=None):
    if base_qs is None:
        base_qs = PersonSession.objects.all()
    qs = base_qs.filter(enter_timestamp__gte=start_time, enter_timestamp__lte=end_time)
    if exclude_outliers:
        qs = qs.exclude(exit_timestamp__isnull=True).filter(duration_seconds__gt=1)
        qs = _exclude_outliers_qs(qs, 'duration_seconds')
    qs = qs.annotate(hh=ExtractHour('enter_timestamp')).values('hh').annotate(count=Count('id')).order_by('hh')
    hour_dict = {i:0 for i in range(24)}
    for row in qs:
        h = row['hh']
        hour_dict[h] += row['count']
    return [(h, hour_dict[h]) for h in range(24)]

def get_wait_distribution_by_dow_custom(start_time, end_time,
                                        exclude_outliers=False,
                                        base_qs=None):
    if base_qs is None:
        base_qs = PersonSession.objects.all()
    qs = base_qs.filter(enter_timestamp__gte=start_time, enter_timestamp__lte=end_time) \
                .exclude(exit_timestamp__isnull=True).filter(duration_seconds__gt=1)
    if exclude_outliers:
        qs = _exclude_outliers_qs(qs, 'duration_seconds')
    agg_qs = qs.annotate(dw=ExtractWeekDay('enter_timestamp')) \
               .values('dw').annotate(avg_wait=Avg('duration_seconds')) \
               .order_by('dw')
    dow_map = {1:'Sun', 2:'Mon', 3:'Tue', 4:'Wed', 5:'Thu', 6:'Fri', 7:'Sat'}
    results = []
    for row in agg_qs:
        d = row['dw']
        label = dow_map.get(d, str(d))
        secs = row['avg_wait'] or 0.0
        results.append((label, secs/60.0))
    return results

def get_wait_distribution_by_hour_custom(start_time, end_time,
                                         exclude_outliers=False,
                                         base_qs=None):
    if base_qs is None:
        base_qs = PersonSession.objects.all()
    qs = base_qs.filter(enter_timestamp__gte=start_time, enter_timestamp__lte=end_time) \
                .exclude(exit_timestamp__isnull=True).filter(duration_seconds__gt=1)
    if exclude_outliers:
        qs = _exclude_outliers_qs(qs, 'duration_seconds')
    agg_qs = qs.annotate(hh=ExtractHour('enter_timestamp')) \
               .values('hh').annotate(avg_wait=Avg('duration_seconds')) \
               .order_by('hh')
    hour_map = {i:0.0 for i in range(24)}
    for row in agg_qs:
        h = row['hh']
        hour_map[h] = (row['avg_wait'] or 0.0)/60.0
    results = []
    for i in range(24):
        results.append((i, hour_map[i]))
    return results
