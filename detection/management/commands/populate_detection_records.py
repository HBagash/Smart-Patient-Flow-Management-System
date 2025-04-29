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
        total_minutes = 7 * 24 * 60
        interval = 5

        for minutes in range(0, total_minutes, interval):
            timestamp = start_time + timedelta(minutes=minutes)
            minute_of_day = timestamp.hour * 60 + timestamp.minute

            sine_val = (math.sin((minute_of_day - 720) * 2 * math.pi / 1440) + 1) / 2

            base = 10
            amplitude = 30

            noise = random.gauss(0, 2)

            count = int(base + amplitude * sine_val + noise)
            count = max(0, count)

            if timestamp.weekday() >= 5:
                count = int(count * 0.7)

            DetectionRecord.objects.create(count=count, timestamp=timestamp)
            self.stdout.write(f"Created record at {timestamp} with count {count}")

        self.stdout.write("Done populating realistic detection records.")
