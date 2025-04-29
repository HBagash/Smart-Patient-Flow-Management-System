import random
import math
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from detection.models import PersonSession, DetectionRecord

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class Command(BaseCommand):
    help = "Generate simulated PersonSession and DetectionRecord data."

    def add_arguments(self, parser):
        parser.add_argument(
            '--sessions',
            type=int,
            default=100,
            help='Number of person sessions to generate (default: 100).'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='Number of days in the simulation window (default: 1).'
        )

    def handle(self, *args, **options):
        num_sessions = options['sessions']
        num_days = options['days']

        self.stdout.write(
            f"Starting simulation of {num_sessions} sessions over {num_days} day(s)..."
        )

        generate_simulated_data(num_sessions, num_days)

        self.stdout.write(self.style.SUCCESS("Simulation complete!"))


def generate_simulated_data(num_sessions: int, num_days: int):
    end_time = timezone.now()
    start_time = end_time - timedelta(days=num_days)

    avg_sessions_per_day = num_sessions / num_days
    avg_per_hour = avg_sessions_per_day / 24.0

    simulated_sessions = []
    session_track_id = 0

    current_time = start_time
    while current_time < end_time:
        if avg_per_hour <= 0:
            arrivals_this_hour = 0
        else:
            if HAS_NUMPY:
                arrivals_this_hour = np.random.poisson(avg_per_hour)
            else:
                arrivals_this_hour = int(random.normalvariate(avg_per_hour, math.sqrt(avg_per_hour)))
                arrivals_this_hour = max(arrivals_this_hour, 0)

        for _ in range(arrivals_this_hour):
            minutes_offset = random.random() * 60.0
            arrival_time = current_time + timedelta(minutes=minutes_offset)

            avg_wait_seconds = 600.0
            duration = int(random.expovariate(1.0 / avg_wait_seconds))

            exit_time = arrival_time + timedelta(seconds=duration)

            session_track_id += 1
            ps = PersonSession(
                track_id=f"sim_{session_track_id}",
                enter_timestamp=arrival_time,
                exit_timestamp=exit_time,
                duration_seconds=duration,
                active=False
            )
            simulated_sessions.append(ps)

        current_time += timedelta(hours=1)

    PersonSession.objects.bulk_create(simulated_sessions)

    detection_records = []
    current_time = start_time
    while current_time < end_time:
        arrivals_this_hour = [
            s for s in simulated_sessions
            if current_time <= s.enter_timestamp < (current_time + timedelta(hours=1))
        ]
        hour_count = len(arrivals_this_hour) + random.randint(-2, 2)
        hour_count = max(0, hour_count)
        
        detection_records.append(
            DetectionRecord(
                timestamp=current_time,
                count=hour_count
            )
        )

        current_time += timedelta(hours=1)

    DetectionRecord.objects.bulk_create(detection_records)
