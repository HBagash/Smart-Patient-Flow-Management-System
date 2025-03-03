from django import forms
from .models import Appointment

class StaffAppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = [
            'scheduled_start',
            'duration_minutes',
            'status',
            'patient_name',
            'patient_email',
        ]
        widgets = {
            'scheduled_start': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
            }),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'patient_name': forms.TextInput(attrs={'class': 'form-control'}),
            'patient_email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class UserAppointmentBookingForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['patient_name', 'patient_email']
        widgets = {
            'patient_name': forms.TextInput(attrs={'class': 'form-control'}),
            'patient_email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class AutoGenerateAppointmentForm(forms.Form):
    start_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        }),
        input_formats=['%Y-%m-%dT%H:%M'],
        help_text="Enter start date/time (e.g., 2025-02-01T09:00)"
    )
    end_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        }),
        input_formats=['%Y-%m-%dT%H:%M'],
        help_text="Enter end date/time (e.g., 2025-02-01T17:00)"
    )
    duration_minutes = forms.IntegerField(
        min_value=5,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Duration for each appointment slot in minutes"
    )
