from datetime import timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseForbidden, HttpResponse

from .models import Appointment
from .forms import StaffAppointmentForm, UserAppointmentBookingForm, AutoGenerateAppointmentForm
from .utils import (
    generate_suggested_appointments,
    predict_appointment_duration,
    predict_overrun_delay_for_appointment  # New import
)
from .kalman import kalman_filter_update  # our simple Kalman filter

def is_staff_check(user):
    return user.is_staff

#
# STAFF VIEWS
#

@user_passes_test(is_staff_check)
def staff_appointment_list(request):
    """
    List all appointments for staff.
    For non-completed appointments, calculate a predicted overrun delay using historical data.
    For completed appointments, compute the actual delay.
    """
    appointments = Appointment.objects.order_by('-scheduled_start')
    for apt in appointments:
        if apt.status == 'completed' and apt.completed_at:
            scheduled_seconds = apt.duration_minutes * 60
            actual_duration = (apt.completed_at - apt.scheduled_start).total_seconds()
            # Actual delay is the amount by which the appointment went over its scheduled duration
            apt.actual_delay = max(0, int(actual_duration - scheduled_seconds))
        else:
            # For non-completed appointments, use the prediction logic
            apt.actual_delay = predict_overrun_delay_for_appointment(apt)
    return render(request, 'appointments/staff_list.html', {
        'appointments': appointments
    })


@user_passes_test(is_staff_check)
def staff_appointment_create(request):
    """
    Manually create a new appointment.
    The predicted_delay is not entered by staff—it is computed automatically.
    """
    if request.method == 'POST':
        form = StaffAppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            # Predict the intended appointment duration using historical data and refine with Kalman filter.
            naive_secs = predict_appointment_duration(appointment.scheduled_start, weeks_lookback=8)
            x_k, p_k = kalman_filter_update(
                measured_value=naive_secs,
                prev_estimate=600.0,
                prev_covariance=500.0,
                process_var=100.0,
                measurement_var=200.0
            )
            # Calculate predicted delay (in seconds) as the difference between the refined prediction 
            # and the slot’s intended duration (converted to seconds)
            appointment.predicted_delay = max(0, int(x_k - appointment.duration_minutes * 60))
            appointment.save()
            messages.success(request, "Appointment created successfully.")
            return redirect('staff_appointment_list')
    else:
        form = StaffAppointmentForm()
    return render(request, 'appointments/staff_form.html', {
        'form': form,
        'action': 'Create'
    })

@user_passes_test(is_staff_check)
def staff_appointment_edit(request, pk):
    """
    Edit an existing appointment.
    Recompute predicted_delay automatically.
    """
    apt = get_object_or_404(Appointment, pk=pk)
    if request.method == 'POST':
        form = StaffAppointmentForm(request.POST, instance=apt)
        if form.is_valid():
            appointment = form.save(commit=False)
            naive_secs = predict_appointment_duration(appointment.scheduled_start, weeks_lookback=8)
            x_k, p_k = kalman_filter_update(
                measured_value=naive_secs,
                prev_estimate=600.0,
                prev_covariance=500.0,
                process_var=100.0,
                measurement_var=200.0
            )
            appointment.predicted_delay = max(0, int(x_k - appointment.duration_minutes * 60))
            appointment.save()
            messages.success(request, "Appointment updated successfully.")
            return redirect('staff_appointment_list')
    else:
        form = StaffAppointmentForm(instance=apt)
    return render(request, 'appointments/staff_form.html', {
        'form': form,
        'action': 'Edit',
        'appointment': apt
    })

@user_passes_test(is_staff_check)
def staff_appointment_delete(request, pk):
    """
    Confirm and delete an appointment.
    """
    apt = get_object_or_404(Appointment, pk=pk)
    if request.method == 'POST':
        apt.delete()
        messages.success(request, "Appointment deleted.")
        return redirect('staff_appointment_list')
    return render(request, 'appointments/staff_delete_confirm.html', {'appointment': apt})

@user_passes_test(is_staff_check)
def staff_generate_appointments(request):
    """
    Automatically generate appointment slots based on a custom date/time range.
    """
    if request.method == 'POST':
        form = AutoGenerateAppointmentForm(request.POST)
        if form.is_valid():
            start_time = form.cleaned_data['start_time']
            end_time = form.cleaned_data['end_time']
            intended_duration = form.cleaned_data['duration_minutes']
            predicted_secs = predict_appointment_duration(start_time, weeks_lookback=8)
            predicted_duration_min = predicted_secs / 60.0
            delay_factor = max(0, predicted_duration_min - intended_duration)
            slot_interval = intended_duration + delay_factor

            created_slots = []
            current_time = start_time
            while current_time + timedelta(minutes=intended_duration) <= end_time:
                apt = Appointment(
                    scheduled_start=current_time,
                    duration_minutes=intended_duration,
                    status='available'
                )
                apt.predicted_delay = max(0, int(predicted_secs - intended_duration * 60))
                created_slots.append(apt)
                current_time += timedelta(minutes=slot_interval)
            Appointment.objects.bulk_create(created_slots)
            messages.success(request, f"Generated {len(created_slots)} appointment slots automatically.")
            return redirect('staff_appointment_list')
    else:
        form = AutoGenerateAppointmentForm()
    return render(request, 'appointments/suggested_appointments.html', {'form': form})

@user_passes_test(is_staff_check)
def staff_bulk_delete(request):
    """
    Bulk delete selected appointments.
    """
    if request.method == "POST":
        selected_ids = request.POST.getlist("selected_appointments")
        if selected_ids:
            Appointment.objects.filter(pk__in=selected_ids).delete()
            messages.success(request, f"Deleted {len(selected_ids)} appointments.")
        else:
            messages.error(request, "No appointments were selected for deletion.")
        return redirect('staff_appointment_list')
    return HttpResponseForbidden("Invalid request method.")

@user_passes_test(is_staff_check)
def staff_mark_completed(request, pk):
    """
    Mark an appointment as completed.
    When marked as completed, the current time is stored in `completed_at`.
    """
    apt = get_object_or_404(Appointment, pk=pk)
    if request.method == 'POST':
        if apt.status != 'completed':
            apt.status = 'completed'
            # completed_at will be set automatically in the model’s save() method.
            apt.save()
            messages.success(request, f"Appointment {apt.pk} marked as completed.")
        return redirect('staff_appointment_list')
    return render(request, 'appointments/staff_mark_completed_confirm.html', {'appointment': apt})

#
# USER VIEWS
#

@login_required
def user_appointment_list(request):
    """
    List available appointments (status 'available') for booking.
    """
    now = timezone.now()
    appointments = Appointment.objects.filter(
        status='available',
        scheduled_start__gte=now
    ).order_by('scheduled_start')
    return render(request, 'appointments/user_list.html', {'appointments': appointments})

@login_required
def user_appointment_book(request, pk):
    """
    Allow a user to book an appointment slot.
    """
    apt = get_object_or_404(Appointment, pk=pk)
    if apt.status != 'available':
        return HttpResponseForbidden("This appointment is no longer available.")
    from .forms import UserAppointmentBookingForm
    if request.method == 'POST':
        form = UserAppointmentBookingForm(request.POST, instance=apt)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.status = 'booked'
            booking.save()
            messages.success(request, "Appointment booked successfully.")
            return redirect('user_appointment_success', pk=booking.pk)
    else:
        form = UserAppointmentBookingForm(instance=apt)
    return render(request, 'appointments/user_book.html', {
        'form': form,
        'appointment': apt
    })

@login_required
def user_appointment_success(request, pk):
    """
    Display a booking confirmation.
    """
    apt = get_object_or_404(Appointment, pk=pk)
    return render(request, 'appointments/user_success.html', {'appointment': apt})

def predict_appointment_view(request):
    """
    A separate (or integrated) page to demonstrate appointment prediction.
    """
    return HttpResponse("Predict Appointment page - integration pending.")
