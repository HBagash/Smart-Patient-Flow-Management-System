from django.urls import path
from . import views
from django.shortcuts import render

urlpatterns = [
    path('test/', views.test_detection, name='test_detection'),
    path('video/', views.video_feed, name='video_feed'),
    path('video_view/', views.video_view, name='video_view'),
]
