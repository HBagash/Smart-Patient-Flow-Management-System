import json
import csv
from datetime import datetime, timedelta
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from detection.models import PersonSession
from detection.detection_module import generate_video_stream
from django.contrib.admin.views.decorators import staff_member_required

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
from .kalman import predict_appointment_kalman

def parse_uk_datetime(dt_string):
    try:
        local_tz = timezone.get_current_timezone()
        naive = datetime.strptime(dt_string.strip(), '%d/%m/%Y %H:%M')
        return timezone.make_aware(naive, local_tz)
    except ValueError:
        return None

@staff_member_required(login_url='login')
def dashboard_all_in_one(request):
    #Outliers
    exclude_flag = request.GET.get('exclude_outliers', '1')
    exclude_outliers = (exclude_flag == '1')

    #Simulated
    show_simulated = (request.GET.get('simulated','false').lower() == 'true')

    #Date range
    start_str = request.GET.get('start','')
    end_str = request.GET.get('end','')
    is_custom_range = False

    st = parse_uk_datetime(start_str) if start_str else None
    et = parse_uk_datetime(end_str)   if end_str   else None

    if st and et and st < et:
        start_time, end_time = st, et
        is_custom_range = True
    else:
        end_time = timezone.now()
        start_time = end_time - timedelta(days=7)

    #base queryset
    if show_simulated:
        base_qs = PersonSession.objects.filter(track_id__startswith='sim_')
        current_data_text = "Currently displaying simulated data."
    else:
        base_qs = PersonSession.objects.exclude(track_id__startswith='sim_')
        current_data_text = "Currently displaying real data."

    overview = get_overview_data(
        exclude_outliers=exclude_outliers,
        base_qs=base_qs,
        custom_start=start_time,
        custom_end=end_time
    )
    total_arrivals = overview['total_arrivals']
    avg_wait_min = round(overview['avg_wait']/60,2)
    max_wait_min = round(overview['max_wait']/60,2)
    min_wait_min = round(overview['min_wait']/60,2)

    hour_qs = get_arrivals_by_hour_custom(
        start_time, end_time,
        exclude_outliers=exclude_outliers,
        base_qs=base_qs
    )
    hour_labels, hour_counts = [], []
    for row in hour_qs:
        dt = row['h']
        label_str = dt.strftime('%d/%m/%Y %H:00') if dt else "Unknown"
        hour_labels.append(label_str)
        hour_counts.append(row['count'])

    dist_data = get_wait_time_distribution_custom(
        start_time, end_time, bin_size=300,
        exclude_outliers=exclude_outliers,
        base_qs=base_qs
    )
    dist_labels, dist_counts = [], []
    for lbl, cnt in dist_data:
        dist_labels.append(lbl)
        dist_counts.append(cnt)

    top_sessions = get_top_longest_waits_custom(
        start_time, end_time, top_n=10,
        base_qs=base_qs,
        exclude_outliers=exclude_outliers
    )

    dow_data = get_arrivals_by_day_of_week_custom(
        start_time, end_time,
        exclude_outliers=exclude_outliers,
        base_qs=base_qs
    )
    if dow_data:
        dow_labels, dow_counts_ = zip(*dow_data)
    else:
        dow_labels, dow_counts_ = [], []

    tod_data = get_time_of_day_pattern_custom(
        start_time, end_time,
        exclude_outliers=exclude_outliers,
        base_qs=base_qs
    )
    tod_labels, tod_counts = [], []
    for hh, c in tod_data:
        tod_labels.append(str(hh))
        tod_counts.append(c)

    dow_wait_data = get_wait_distribution_by_dow_custom(
        start_time, end_time,
        exclude_outliers=exclude_outliers,
        base_qs=base_qs
    )
    dow_wait_labels, dow_wait_values = [], []
    for label, avg_mins in dow_wait_data:
        dow_wait_labels.append(label)
        dow_wait_values.append(round(avg_mins,2))

    hod_wait_data = get_wait_distribution_by_hour_custom(
        start_time, end_time,
        exclude_outliers=exclude_outliers,
        base_qs=base_qs
    )
    hod_wait_labels, hod_wait_values = [], []
    for hh, avg_mins in hod_wait_data:
        hod_wait_labels.append(str(hh))
        hod_wait_values.append(round(avg_mins,2))

    predict_predicted_minutes = None
    predict_error_message = None
    predict_date = ""
    predict_time = ""
    if request.method=='POST' and request.POST.get('predict_form'):
        predict_date = request.POST.get('predict_date','')
        predict_time = request.POST.get('predict_time','')
        if predict_date and predict_time:
            parsed_dt = parse_uk_datetime(f"{predict_date.strip()} {predict_time.strip()}")
            if parsed_dt:
                final_est = predict_appointment_kalman(parsed_dt, weeks_lookback=8)
                predict_predicted_minutes = round(final_est/60,2)
            else:
                predict_error_message = "Invalid date/time format. Use dd/mm/yyyy HH:MM."
        else:
            predict_error_message = "Please enter both date and time."

    active_sessions = base_qs.filter(exit_timestamp__isnull=True)
    predicted_info = []
    for s in active_sessions:
        final_est = predict_appointment_kalman(s.enter_timestamp, 8)
        remain = final_est - s.waiting_time
        if remain < 0:
            remain = 0
        is_late = "Yes" if s.waiting_time > final_est else "No"
        predicted_info.append({
            'track_id': s.track_id,
            'enter_timestamp': s.enter_timestamp,
            'elapsed_sec': round(s.waiting_time,2),
            'remaining_sec': round(remain,2),
            'is_late': is_late
        })

    if exclude_outliers:
        analytics_outlier_label = "(Excluding Outliers)"
    else:
        analytics_outlier_label = "(Including Outliers)"

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
        'hour_labels_json': json.dumps(hour_labels),
        'hour_counts_json': json.dumps(hour_counts),
        'dist_labels_json': json.dumps(dist_labels),
        'dist_counts_json': json.dumps(dist_counts),
        'top_sessions': top_sessions,
        'dow_labels_json': json.dumps(list(dow_labels)),
        'dow_counts_json': json.dumps(list(dow_counts_)),
        'tod_labels_json': json.dumps(tod_labels),
        'tod_counts_json': json.dumps(tod_counts),
        'dow_wait_labels_json': json.dumps(dow_wait_labels),
        'dow_wait_values_json': json.dumps(dow_wait_values),
        'hod_wait_labels_json': json.dumps(hod_wait_labels),
        'hod_wait_values_json': json.dumps(hod_wait_values),
        'predict_predicted_minutes': predict_predicted_minutes,
        'predict_error_message': predict_error_message,
        'predict_date': predict_date,
        'predict_time': predict_time,
        'active_sessions': active_sessions,
        'predicted_info': predicted_info,
        'analytics_outlier_label': analytics_outlier_label,
    }
    return render(request, 'dashboard/dashboard.html', context)

@csrf_exempt
@staff_member_required(login_url='login')
def active_sessions_api(request):
    final_est = 0
    exclude_flag = request.GET.get('exclude_outliers', '1')
    exclude_outliers = (exclude_flag == '1')

    active_sessions = PersonSession.objects.filter(exit_timestamp__isnull=True)
    data = []
    for s in active_sessions:
        final_est = predict_appointment_kalman(s.enter_timestamp, 8)
        remain = final_est - s.waiting_time
        if remain < 0:
            remain = 0
        is_late = "Yes" if s.waiting_time > final_est else "No"
        data.append({
            'track_id': s.track_id,
            'enter_timestamp': s.enter_timestamp.isoformat(),
            'elapsed_seconds': round(s.waiting_time,2),
            'predicted_remain': round(remain,2),
            'is_late': is_late
        })
    return JsonResponse({'active_sessions': data})

@staff_member_required(login_url='login')
def video_feed_dashboard(request):
    return StreamingHttpResponse(
        generate_video_stream(),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )

@staff_member_required(login_url='login')
def export_dashboard_csv(request):
    exclude_flag = request.GET.get('exclude_outliers', '1')
    exclude_outliers = (exclude_flag == '1')

    show_simulated = (request.GET.get('simulated','false').lower()=='true')
    start_str = request.GET.get('start','')
    end_str = request.GET.get('end','')

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

    overview = get_overview_data(
        exclude_outliers=exclude_outliers,
        base_qs=base_qs,
        custom_start=start_time,
        custom_end=end_time
    )
    arrivals_hourly = get_arrivals_by_hour_custom(
        start_time, end_time,
        exclude_outliers=exclude_outliers,
        base_qs=base_qs
    )
    wait_dist = get_wait_time_distribution_custom(
        start_time, end_time, 300,
        exclude_outliers=exclude_outliers,
        base_qs=base_qs
    )
    top_sessions = get_top_longest_waits_custom(
        start_time, end_time, 10,
        base_qs=base_qs,
        exclude_outliers=exclude_outliers
    )

    response = HttpResponse(content_type='text/csv')
    filename = "dashboard_data.csv"
    if exclude_outliers:
        filename = "dashboard_data_excluding_outliers.csv"
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

