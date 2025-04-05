from django.shortcuts import render, get_object_or_404
from django import forms
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import datetime
from .models import NotificationRequest, Feedback
from dashboard.kalman import predict_appointment_kalman

class NotificationRequestForm(forms.ModelForm):
    class Meta:
        model = NotificationRequest
        fields = ['email', 'date', 'time_block']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'time_block': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        }

def notification_request_view(request):
    if request.method == 'POST':
        form = NotificationRequestForm(request.POST)
        if form.is_valid():
            instance = form.save()

            chosen_date = instance.date
            chosen_time = instance.time_block
            combined = datetime.combine(chosen_date, chosen_time)
            local_tz = timezone.get_current_timezone()
            combined_aware = timezone.make_aware(combined, local_tz)

            # Exclude outliers in predicted wait
            predicted_wait_secs = predict_appointment_kalman(
                combined_aware, weeks_lookback=8, exclude_outliers=True
            )

            # For display: seconds if <60, else minutes
            if predicted_wait_secs < 60:
                display_wait = f"{int(predicted_wait_secs)} seconds"
            else:
                display_wait = f"{round(predicted_wait_secs/60, 2)} minutes"

            # Store category/wait in instance
            new_category = instance.categorize_wait(predicted_wait_secs)
            instance.last_predicted_category = new_category
            instance.last_predicted_wait_mins = predicted_wait_secs/60.0
            instance.save()

            # Color-coded for the success page
            if new_category.lower() == "low":
                status_color = "green"
                status_label = "Low wait time"
            elif new_category.lower() == "moderate":
                status_color = "orange"
                status_label = "Moderate wait time"
            else:
                status_color = "red"
                status_label = "High wait time"

            # Send the confirmation if not already sent
            if not instance.confirmation_sent:
                subject = f"Confirmation for {chosen_date} {chosen_time.strftime('%I:%M %p')}"
                email_msg = (
                    f"Hello,\n\n"
                    f"Thank you for requesting a notification for {chosen_date} at "
                    f"{chosen_time.strftime('%I:%M %p')}.\n\n"
                    f"Our current estimate is around {display_wait} ({status_label}).\n"
                    f"We will let you know if this changes significantly.\n\n"
                    f"Thanks,\n"
                    f"Smart Patient Flow System"
                )
                send_mail(
                    subject,
                    email_msg,
                    settings.DEFAULT_FROM_EMAIL,
                    [instance.email],
                    fail_silently=False
                )
                instance.confirmation_sent = True
                instance.save()

            context = {
                'instance': instance,
                'display_wait': display_wait,
                'status_color': status_color,
                'status_label': status_label,
            }
            return render(request, 'queuing/notification_success.html', context)
    else:
        form = NotificationRequestForm()
    return render(request, 'queuing/notification_request.html', {'form': form})

class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = [
            'rating_notification_usefulness',
            'rating_ease_of_use',
            'rating_overall_experience',
            'rating_recommendation',
        ]
        widgets = {
            'rating_notification_usefulness': forms.NumberInput(attrs={
                'type': 'number',
                'step': '1',
                'min': '1',
                'max': '10',
                'class': 'form-control'
            }),
            'rating_ease_of_use': forms.NumberInput(attrs={
                'type': 'number',
                'step': '1',
                'min': '1',
                'max': '10',
                'class': 'form-control'
            }),
            'rating_overall_experience': forms.NumberInput(attrs={
                'type': 'number',
                'step': '1',
                'min': '1',
                'max': '10',
                'class': 'form-control'
            }),
            'rating_recommendation': forms.NumberInput(attrs={
                'type': 'number',
                'step': '1',
                'min': '1',
                'max': '10',
                'class': 'form-control'
            }),
        }


def feedback_form_view(request, token):
    fb = get_object_or_404(Feedback, token=token)
    if request.method == 'POST':
        form = FeedbackForm(request.POST, instance=fb)
        if form.is_valid():
            # Mark as submitted
            fb.submitted = True
            form.save()
            return render(request, 'queuing/feedback_thanks.html')
    else:
        form = FeedbackForm(instance=fb)
    return render(request, 'queuing/feedback_form.html', {'form': form})



from django.db.models import Avg
from django.http import JsonResponse
import json
from .models import Feedback

def feedback_analytics_view(request):
    feedbacks = Feedback.objects.filter(submitted=True)
    total_count = feedbacks.count()

    avg_notification_usefulness = feedbacks.aggregate(
        avg=Avg('rating_notification_usefulness')
    )['avg'] or 0
    avg_ease_of_use = feedbacks.aggregate(
        avg=Avg('rating_ease_of_use')
    )['avg'] or 0
    avg_overall = feedbacks.aggregate(
        avg=Avg('rating_overall_experience')
    )['avg'] or 0
    avg_recommendation = feedbacks.aggregate(
        avg=Avg('rating_recommendation')
    )['avg'] or 0

    dist_notif = []
    dist_ease = []
    dist_overall = []
    dist_recommend = []
    for i in range(1, 11):
        dist_notif.append(feedbacks.filter(rating_notification_usefulness=i).count())
        dist_ease.append(feedbacks.filter(rating_ease_of_use=i).count())
        dist_overall.append(feedbacks.filter(rating_overall_experience=i).count())
        dist_recommend.append(feedbacks.filter(rating_recommendation=i).count())

    context = {
        'total_count': total_count,
        'avg_notification_usefulness': round(avg_notification_usefulness, 2),
        'avg_ease_of_use': round(avg_ease_of_use, 2),
        'avg_overall': round(avg_overall, 2),
        'avg_recommendation': round(avg_recommendation, 2),
        'dist_notif_json': json.dumps(dist_notif),
        'dist_ease_json': json.dumps(dist_ease),
        'dist_overall_json': json.dumps(dist_overall),
        'dist_recommend_json': json.dumps(dist_recommend),
    }
    return render(request, 'queuing/feedback_analytics.html', context)
