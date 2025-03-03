from django.urls import path
from . import views

urlpatterns = [
    # Staff URLs
    path('staff/', views.staff_appointment_list, name='staff_appointment_list'),
    path('staff/create/', views.staff_appointment_create, name='staff_appointment_create'),
    path('staff/<int:pk>/edit/', views.staff_appointment_edit, name='staff_appointment_edit'),
    path('staff/<int:pk>/delete/', views.staff_appointment_delete, name='staff_appointment_delete'),
    path('staff/suggest/', views.staff_generate_appointments, name='staff_generate_appointments'),
    path('staff/bulk-delete/', views.staff_bulk_delete, name='staff_bulk_delete'),
    path('staff/<int:pk>/complete/', views.staff_mark_completed, name='staff_mark_completed'),
    
    # User URLs
    path('', views.user_appointment_list, name='user_appointment_list'),
    path('book/<int:pk>/', views.user_appointment_book, name='user_appointment_book'),
    path('success/<int:pk>/', views.user_appointment_success, name='user_appointment_success'),
    
    # Optional prediction page
    path('predict/', views.predict_appointment_view, name='predict_appointment_view'),
]
