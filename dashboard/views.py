import json
import csv
from datetime import datetime, timedelta
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from detection.models import PersonSession
from .utils import (
    get_overview_data,
    get_arrivals_by_hour_custom,
    get_wait_time_distribution_custom,
    get_top_longest_waits_custom,
    get_arrivals_by_day_of_week_custom,
    get_time_of_day_pattern_custom,
    get_wait_distribution_by_dow_custom,
    get_wait_distribution_by_hour_custom,
)
from .kalman import kalman_filter_update, predict_appointment_kalman

def dashboard_all_in_one(request):
    # 1) Toggles
    exclude_outliers = bool(request.GET.get('exclude_outliers',''))
    show_simulated = (request.GET.get('simulated','true').lower()=='true')

    # 2) Date range in UK format dd/mm/yyyy HH:MM
    start_str = request.GET.get('start','')
    end_str = request.GET.get('end','')
    is_custom_range = False

    def parse_uk_datetime(dt_string):
        try:
            local_tz = timezone.get_current_timezone()
            naive = datetime.strptime(dt_string.strip(), '%d/%m/%Y %H:%M')
            return timezone.make_aware(naive, local_tz)
        except ValueError:
            return None

    if start_str and end_str:
        st = parse_uk_datetime(start_str)
        et = parse_uk_datetime(end_str)
        if st and et and st < et:
            start_time, end_time = st, et
            is_custom_range = True
        else:
            end_time = timezone.now()
            start_time = end_time - timedelta(days=7)
    else:
        end_time = timezone.now()
        start_time = end_time - timedelta(days=7)

    # 3) base queryset
    if show_simulated:
        base_qs = PersonSession.objects.filter(track_id__startswith='sim_')
        current_data_text = "Currently displaying simulated data."
    else:
        base_qs = PersonSession.objects.exclude(track_id__startswith='sim_')
        current_data_text = "Currently displaying real data."

    # 4) Aggregators
    overview = get_overview_data(exclude_outliers, base_qs, start_time, end_time)
    total_arrivals = overview['total_arrivals']
    avg_wait_min = round(overview['avg_wait']/60,2)
    max_wait_min = round(overview['max_wait']/60,2)
    min_wait_min = round(overview['min_wait']/60,2)

    hour_qs = get_arrivals_by_hour_custom(start_time, end_time, exclude_outliers, base_qs)
    hour_labels, hour_counts = [], []
    for row in hour_qs:
        dt = row['h']
        if dt:
            label_str = dt.strftime('%d/%m/%Y %H:00')
        else:
            label_str = "Unknown"
        hour_labels.append(label_str)
        hour_counts.append(row['count'])

    dist_data = get_wait_time_distribution_custom(start_time, end_time, 300, exclude_outliers, base_qs)
    dist_labels, dist_counts = [], []
    for lbl, cnt in dist_data:
        dist_labels.append(lbl)
        dist_counts.append(cnt)

    top_sessions = get_top_longest_waits_custom(start_time, end_time, 10, base_qs)

    dow_data = get_arrivals_by_day_of_week_custom(start_time, end_time, base_qs)
    dow_labels, dow_counts_ = [], []
    for label, c in dow_data:
        dow_labels.append(label)
        dow_counts_.append(c)

    tod_data = get_time_of_day_pattern_custom(start_time, end_time, base_qs)
    tod_labels, tod_counts = [], []
    for hh, c in tod_data:
        tod_labels.append(str(hh))
        tod_counts.append(c)

    dow_wait_data = get_wait_distribution_by_dow_custom(start_time, end_time, base_qs)
    dow_wait_labels, dow_wait_values = [], []
    for label, avg_mins in dow_wait_data:
        dow_wait_labels.append(label)
        dow_wait_values.append(round(avg_mins,2))

    hod_wait_data = get_wait_distribution_by_hour_custom(start_time, end_time, base_qs)
    hod_wait_labels, hod_wait_values = [], []
    for hh, avg_mins in hod_wait_data:
        hod_wait_labels.append(str(hh))
        hod_wait_values.append(round(avg_mins,2))

    # 5) Predict Appointment (multi-step Kalman approach)
    predict_predicted_minutes = None
    predict_error_message = None
    predict_date = ""
    predict_time = ""
    if request.method=='POST' and request.POST.get('predict_form'):
        predict_date = request.POST.get('predict_date','')
        predict_time = request.POST.get('predict_time','')
        if predict_date and predict_time:
            try:
                dt_str = f"{predict_date.strip()} {predict_time.strip()}"
                local_tz = timezone.get_current_timezone()
                naive_dt = datetime.strptime(dt_str, '%d/%m/%Y %H:%M')
                appt_dt = timezone.make_aware(naive_dt, local_tz)

                # multi-step approach over historical durations
                final_est = predict_appointment_kalman(appt_dt, weeks_lookback=8)
                predict_predicted_minutes = round(final_est/60,2)
            except ValueError:
                predict_error_message = "Invalid date/time format. Use dd/mm/yyyy HH:MM."
        else:
            predict_error_message = "Please enter both date and time."

    # 6) Active sessions
    active_sessions = base_qs.filter(exit_timestamp__isnull=True)
    predicted_info = []
    for s in active_sessions:
        # For each active session, do the multi-step approach for day-of-week/hour-of-day
        final_est = predict_appointment_kalman(s.enter_timestamp, 8)
        remain = final_est - s.waiting_time
        if remain<0: remain=0
        predicted_info.append({
            'track_id': s.track_id,
            'enter_timestamp': s.enter_timestamp,
            'elapsed_sec': round(s.waiting_time,2),
            'remaining_sec': round(remain,2),
        })

    context = {
        'is_custom_range': is_custom_range,
        'exclude_outliers': exclude_outliers,
        'show_simulated': show_simulated,
        'current_data_text': current_data_text,

        'total_arrivals': total_arrivals,
        'avg_wait': avg_wait_min,
        'max_wait': max_wait_min,
        'min_wait': min_wait_min,
        'start_time': start_time,
        'end_time': end_time,

        # arrivals by hour
        'hour_labels_json': json.dumps(hour_labels),
        'hour_counts_json': json.dumps(hour_counts),

        # wait dist
        'dist_labels_json': json.dumps(dist_labels),
        'dist_counts_json': json.dumps(dist_counts),

        # top 10
        'top_sessions': top_sessions,

        # day-of-week arrivals
        'dow_labels_json': json.dumps(dow_labels),
        'dow_counts_json': json.dumps(dow_counts_),

        # hour-of-day arrivals
        'tod_labels_json': json.dumps(tod_labels),
        'tod_counts_json': json.dumps(tod_counts),

        # avg wait by day-of-week
        'dow_wait_labels_json': json.dumps(dow_wait_labels),
        'dow_wait_values_json': json.dumps(dow_wait_values),

        # avg wait by hour-of-day
        'hod_wait_labels_json': json.dumps(hod_wait_labels),
        'hod_wait_values_json': json.dumps(hod_wait_values),

        # predict form
        'predict_predicted_minutes': predict_predicted_minutes,
        'predict_error_message': predict_error_message,
        'predict_date': predict_date,
        'predict_time': predict_time,

        # active sessions
        'active_sessions': active_sessions,
        'predicted_info': predicted_info,
    }
    return render(request, 'dashboard/dashboard.html', context)


@csrf_exempt
def active_sessions_api(request):
    from .kalman import predict_appointment_kalman
    active_sessions = PersonSession.objects.filter(exit_timestamp__isnull=True)
    data = []
    for s in active_sessions:
        final_est = predict_appointment_kalman(s.enter_timestamp, 8)
        remain = final_est - s.waiting_time
        if remain<0: remain=0
        data.append({
            'track_id': s.track_id,
            'enter_timestamp': s.enter_timestamp.isoformat(),
            'elapsed_seconds': round(s.waiting_time,2),
            'predicted_remain': round(remain,2)
        })
    return JsonResponse({'active_sessions': data})

def export_dashboard_csv(request):
    exclude_outliers = bool(request.GET.get('exclude_outliers',''))
    show_simulated = (request.GET.get('simulated','true').lower()=='true')

    start_str = request.GET.get('start','')
    end_str = request.GET.get('end','')
    def parse_uk_datetime(dt_string):
        from datetime import datetime
        try:
            local_tz = timezone.get_current_timezone()
            naive = datetime.strptime(dt_string.strip(), '%d/%m/%Y %H:%M')
            return timezone.make_aware(naive, local_tz)
        except ValueError:
            return None

    if start_str and end_str:
        st = parse_uk_datetime(start_str)
        et = parse_uk_datetime(end_str)
        if st and et and st < et:
            start_time, end_time = st, et
        else:
            end_time = timezone.now()
            start_time = end_time - timedelta(days=7)
    else:
        end_time = timezone.now()
        start_time = end_time - timedelta(days=7)

    if show_simulated:
        base_qs = PersonSession.objects.filter(track_id__startswith='sim_')
    else:
        base_qs = PersonSession.objects.exclude(track_id__startswith='sim_')

    from .utils import (
        get_overview_data,
        get_arrivals_by_hour_custom,
        get_wait_time_distribution_custom,
        get_top_longest_waits_custom
    )

    overview = get_overview_data(exclude_outliers, base_qs, start_time, end_time)
    arrivals_hourly = get_arrivals_by_hour_custom(start_time, end_time, exclude_outliers, base_qs)
    wait_dist = get_wait_time_distribution_custom(start_time, end_time, 300, exclude_outliers, base_qs)
    top_sessions = get_top_longest_waits_custom(start_time, end_time, 10, base_qs)

    response = HttpResponse(content_type='text/csv')
    filename = "dashboard_data.csv"
    if exclude_outliers:
        filename = "dashboard_data_no_outliers.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(["--- DASHBOARD CSV ---"])
    writer.writerow(["Range", f"{start_time} to {end_time}"])
    writer.writerow(["Simulated", "True" if show_simulated else "False"])
    writer.writerow(["Exclude Outliers", "True" if exclude_outliers else "False"])
    writer.writerow([])
    writer.writerow(["Total Arrivals", overview['total_arrivals']])
    writer.writerow(["Avg Wait (sec)", overview['avg_wait']])
    writer.writerow(["Max Wait (sec)", overview['max_wait']])
    writer.writerow(["Min Wait (sec)", overview['min_wait']])
    writer.writerow([])

    writer.writerow(["--- ARRIVALS BY HOUR ---"])
    writer.writerow(["Hour", "Count"])
    for row in arrivals_hourly:
        hr_str = row['h'].strftime("%d/%m/%Y %H:00") if row['h'] else "None"
        writer.writerow([hr_str, row['count']])
    writer.writerow([])

    writer.writerow(["--- WAIT TIME DIST (5-min bins) ---"])
    writer.writerow(["Label", "Count"])
    for lbl, c in wait_dist:
        writer.writerow([lbl, c])
    writer.writerow([])

    writer.writerow(["--- TOP 10 LONGEST WAITS ---"])

    writer.writerow(["pk", "enter_timestamp", "exit_timestamp", "duration_seconds"])
    for s in top_sessions:
        writer.writerow([s.pk, s.enter_timestamp, s.exit_timestamp, s.duration_seconds])


    return response

def predict_appointment_view(request):
    return HttpResponse("Future Note to myself: Include this in the main dashboard.")
