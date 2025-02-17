from django.shortcuts import render
from detection.models import DetectionRecord
from datetime import datetime, timedelta
import numpy as np

def dashboard(request):
    # Time window: last 24 hours
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=24)

    records = DetectionRecord.objects.filter(timestamp__gte=start_time, timestamp__lte=end_time)

    if records.exists():
        counts = np.array([record.count for record in records])
        L = np.mean(counts)  # Average number of people in queue
    else:
        L = 0

    # Service rate (mu) in people per minute
    mu = 10

    # Solve for lambda using L = lambda / (mu - lambda), if L > 0
    if L > 0:
        lam = (L * mu) / (1 + L)
    else:
        lam = 0

    # Compute waiting time
    if lam < mu and lam > 0:
        waiting_time = 1 / (mu - lam)  # in minutes
        waiting_time_display = round(waiting_time, 2)
    elif lam == 0:
        waiting_time_display = 0
    else:
        waiting_time_display = "System unstable (λ ≥ μ)"

    context = {
        'average_count': round(L, 2),
        'arrival_rate': round(lam, 2),
        'service_rate': mu,
        'waiting_time': waiting_time_display,
        'record_count': records.count(),
    }
    return render(request, 'dashboard/dashboard.html', context)
