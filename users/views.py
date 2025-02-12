from django.shortcuts import render

# Create your views here.

def login_view(request):
    return render(request, 'users/login.html')

def register_view(request):
    return render(request, 'users/register.html')