from django.contrib import admin
from .models import Appointment

# Register your models here.

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('id','scheduled_start','duration_minutes','status','patient_name','predicted_delay')
    list_filter = ('status',)
    search_fields = ('patient_name','patient_email')