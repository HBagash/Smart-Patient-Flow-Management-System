from django.urls import path
from . import views

urlpatterns = [
    path('test/', views.test_detection, name='test_detection'),
]
