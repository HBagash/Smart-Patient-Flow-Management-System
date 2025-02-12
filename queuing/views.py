from django.shortcuts import render

# Create your views here.
def estimate_wait_time(request):
    # Will be using a default value for now just for testing purposes
    wait_time = 15  # waiting times in mins
    return render(request, 'queuing/estimate.html', {'wait_time': wait_time})