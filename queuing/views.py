from django.shortcuts import render

# Create your views here.

def estimate_wait_time(request):
    num_people = 4

    wait_time = num_people * 5

    context = {
        'wait_time': wait_time,
        'num_people': num_people,
    }
    return render(request, 'queuing/estimate.html', context)
