from django.core.management.base import BaseCommand
from detection.models import DetectionRecord
from datetime import datetime, timedelta
import random, math

class Command(BaseCommand):
    help = "Populates the database with realistic detection records for testing the queuing model."

    def handle(self, *args, **options):
        self.stdout.write("Starting to populate detection records...")

        now = datetime.now()
        start_time = now - timedelta(days=7)
        total_minutes = 7 * 24 * 60  # total minutes in 7 days
        interval = 5  # interval in minutes

        for minutes in range(0, total_minutes, interval):
            timestamp = start_time + timedelta(minutes=minutes)
            # Compute the minute of the day (0-1439)
            minute_of_day = timestamp.hour * 60 + timestamp.minute

            # Simulate a daily sine-wave pattern:
            # - Peak (highest count) at noon (720 minutes) and trough at midnight.
            # Normalize sine from -1 to 1 into a 0 to 1 scale.
            sine_val = (math.sin((minute_of_day - 720) * 2 * math.pi / 1440) + 1) / 2

            # Base count and amplitude
            base = 10      # minimum count during off-peak hours
            amplitude = 30 # additional count at peak

            # Add Gaussian noise with a small standard deviation
            noise = random.gauss(0, 2)

            count = int(base + amplitude * sine_val + noise)
            count = max(0, count)  # Ensure non-negative

            # Adjust weekend counts: lower activity on Saturday (5) and Sunday (6)
            if timestamp.weekday() >= 5:
                count = int(count * 0.7)

            DetectionRecord.objects.create(count=count, timestamp=timestamp)
            self.stdout.write(f"Created record at {timestamp} with count {count}")

        self.stdout.write("Done populating realistic detection records.")
