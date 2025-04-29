from django.db import models
from django.utils import timezone
import uuid

class NotificationRequest(models.Model):
    email = models.EmailField()
    date = models.DateField()
    time_block = models.TimeField()
    status = models.CharField(max_length=20, default="pending")
    created_at = models.DateTimeField(default=timezone.now)
    last_predicted_wait_mins = models.FloatField(null=True, blank=True)
    last_predicted_category = models.CharField(max_length=10, default='unknown')
    confirmation_sent = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.email} - {self.date} @ {self.time_block} [{self.status}]"

    def categorize_wait(self, wait_in_seconds):
        if wait_in_seconds < 120:
            return "Low"
        elif wait_in_seconds < 600:
            return "Moderate"
        else:
            return "High"


class Feedback(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    notification_preference = models.CharField(max_length=10)  # "email" or "sms"

    rating_notification_usefulness = models.PositiveSmallIntegerField(null=True, blank=True)
    rating_ease_of_use = models.PositiveSmallIntegerField(null=True, blank=True)
    rating_overall_experience = models.PositiveSmallIntegerField(null=True, blank=True)
    rating_recommendation = models.PositiveSmallIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)

    #mark whether the user actually submitted the form
    submitted = models.BooleanField(default=False)

    def __str__(self):
        return f"Feedback {self.pk} - Pref: {self.notification_preference}"
