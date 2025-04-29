from django.urls import path
from . import views

urlpatterns = [
    path('video/', views.video_feed, name='video_feed'),
    path('video_view/', views.video_view, name='video_view'),
    path('update_zones_multiple/', views.update_detection_zones_multiple, name='update_detection_zones_multiple'),
    path('reset_zone/', views.reset_detection_zone, name='reset_detection_zone'),
]
