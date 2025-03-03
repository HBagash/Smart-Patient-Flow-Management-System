from django.db import models
from django.utils import timezone

class Appointment(models.Model):
    """
    Stores information about an appointment slot.
    """
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('booked', 'Booked'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    scheduled_start = models.DateTimeField(
        help_text="The date/time the appointment is scheduled to begin."
    )
    duration_minutes = models.PositiveIntegerField(
        default=15,
        help_text="Expected length of the appointment in minutes."
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='available'
    )
    patient_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Patient's name if booked."
    )
    patient_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Patient's email if booked (for notifications)."
    )
    predicted_delay = models.IntegerField(
        blank=True,
        null=True,
        help_text="Auto-calculated delay in seconds above the slot duration."
    )
    # New field to store the actual completion time.
    completed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="The time the appointment was completed."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # If the appointment is marked as completed and no completed_at is set, record the current time.
        if self.status == 'completed' and self.completed_at is None:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        start_str = self.scheduled_start.strftime("%Y-%m-%d %H:%M")
        return f"Appointment {self.pk} ({self.status}) at {start_str}"

    @property
    def scheduled_end(self):
        return self.scheduled_start + timezone.timedelta(minutes=self.duration_minutes)
