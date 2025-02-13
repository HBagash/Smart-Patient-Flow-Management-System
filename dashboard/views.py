from django.shortcuts import render

# Create your views here.

def dashboard_home(request):
    # Fake data for now during testing
    context = {
        'appointments': 5,
        'average_wait_time': 12,
        'feedback_count': 3,
    }
    return render(request, 'dashboard/home.html', context)