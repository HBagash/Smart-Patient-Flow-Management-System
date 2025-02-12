from django.urls import path
from . import views

urlpatterns = [
    path('estimate/', views.estimate_wait_time, name='estimate_wait_time'),
]
