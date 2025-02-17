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

    def __str__(self):
        return f"Track {self.track_id} (Entered: {self.enter_timestamp})"
