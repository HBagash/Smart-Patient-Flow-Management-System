from django.db import models
from django.utils import timezone

class DetectionRecord(models.Model):
    timestamp = models.DateTimeField(default=timezone.now)
    count = models.IntegerField(default=0)

    def __str__(self):
        return f"DetectionRecord: {self.count} at {self.timestamp}"


class PersonSession(models.Model):
    track_id = models.CharField(max_length=50)
    enter_timestamp = models.DateTimeField(default=timezone.now)
    exit_timestamp = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    active = models.BooleanField(default=True)
    appearance_feature = models.JSONField(null=True, blank=True)  # e.g. a color histogram

    def __str__(self):
        return f"PersonSession {self.track_id} (Entered: {self.enter_timestamp}, Active: {self.active})"

    @property
    def waiting_time(self):
        if self.exit_timestamp:
            return (self.exit_timestamp - self.enter_timestamp).total_seconds()
        else:
            return (timezone.now() - self.enter_timestamp).total_seconds()

    def save(self, *args, **kwargs):
        if self.exit_timestamp and not self.duration_seconds:
            self.duration_seconds = (self.exit_timestamp - self.enter_timestamp).total_seconds()
            self.active = False
        super().save(*args, **kwargs)
