from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_all_in_one, name='dashboard_home'),
    path('active-sessions-api/', views.active_sessions_api, name='active_sessions_api'),
    path('video-stream/', views.video_feed_dashboard, name='dashboard_video_feed'),
    path('export-csv/', views.export_dashboard_csv, name='dashboard_export_csv'),
]
