from django.urls import path
from . import views

urlpatterns = [
    path('notification-request/', views.notification_request_view, name='notification_request'),
    path('feedback/<uuid:token>/', views.feedback_form_view, name='feedback_form'),
    path('feedback-analytics/', views.feedback_analytics_view, name='feedback_analytics'),
]
