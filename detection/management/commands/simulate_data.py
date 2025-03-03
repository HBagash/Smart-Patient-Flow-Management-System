import random
import math
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime
from detection.models import PersonSession, DetectionRecord

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# Import the Appointment model from your appointments app
from appointments.models import Appointment

class Command(BaseCommand):
    help = "Generate simulated PersonSession, DetectionRecord, and Appointment data."

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
    # Set up simulation time window.
    end_time = timezone.now()
    start_time = end_time - timedelta(days=num_days)

    # --- SIMULATE PERSON SESSIONS ---
    avg_sessions_per_day = num_sessions / num_days
    avg_per_hour = avg_sessions_per_day / 24.0

    simulated_sessions = []
    session_track_id = 0

    current_time = start_time
    while current_time < end_time:
        # Calculate arrivals per hour (using a Poisson process if numpy is available)
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

    # --- SIMULATE DETECTION RECORDS ---
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

    # --- SIMULATE APPOINTMENTS ---
    simulated_appointments = []
    appointment_track_id = 0

    # For realistic simulation, we assume the doctor's schedule is per day.
    # For each day in the simulation window, simulate up to a maximum number of appointments.
    # For this example, assume:
    #   - The doctor's schedule starts at 9:00 AM.
    #   - Each appointment is intended to last 30 minutes.
    #   - At most 10 appointments per day.
    intended_duration = 30  # minutes (as set by the doctor)
    max_appointments_per_day = 10

    # Loop over each day in the simulation window.
    current_day = start_time.date()
    end_day = end_time.date()
    while current_day <= end_day:
        # Set doctor's scheduled start time at 9:00 AM local time.
        day_start = datetime.combine(current_day, datetime.min.time())
        day_start = timezone.make_aware(day_start)
        scheduled_start_time = day_start.replace(hour=9, minute=0, second=0)

        # Get all PersonSessions for this day (simulate the queue).
        sessions_today = sorted(
            [s for s in simulated_sessions if s.enter_timestamp.date() == current_day],
            key=lambda s: s.enter_timestamp
        )

        # The number of appointments is the lesser of the number of sessions and the maximum appointments.
        num_appointments = min(max_appointments_per_day, len(sessions_today))
        previous_actual_end = None

        for i in range(num_appointments):
            appointment_track_id += 1
            person = sessions_today[i]
            # Scheduled start is fixed by the doctor's schedule.
            scheduled_start = scheduled_start_time + timedelta(minutes=i * intended_duration)
            # Actual start is the maximum of scheduled start, previous appointment's actual end, and the person's arrival time.
            if i == 0:
                # First appointment: very short waiting time (0-1 minute delay)
                delay = timedelta(seconds=random.randint(0, 60))
            else:
                # Subsequent appointments may experience an additional delay if previous appointment ran long.
                delay = timedelta(seconds=random.randint(30, 120))
            if previous_actual_end is None:
                actual_start = max(scheduled_start, person.enter_timestamp) + delay
            else:
                actual_start = max(scheduled_start, previous_actual_end, person.enter_timestamp) + delay

            # Simulate actual appointment duration:
            mean_duration_seconds = intended_duration * 60
            std_duration_seconds = 5 * 60  # 5 minutes std deviation
            actual_duration_seconds = int(random.normalvariate(mean_duration_seconds, std_duration_seconds))
            # Ensure a minimum actual duration (e.g. at least 80% of intended duration)
            min_duration = int(0.8 * mean_duration_seconds)
            actual_duration_seconds = max(actual_duration_seconds, min_duration)
            completed_at = actual_start + timedelta(seconds=actual_duration_seconds)
            predicted_delay = max(0, actual_duration_seconds - mean_duration_seconds)

            simulated_appointments.append(
                Appointment(
                    scheduled_start=scheduled_start,
                    duration_minutes=intended_duration,
                    status='completed',
                    completed_at=completed_at,
                    predicted_delay=predicted_delay,
                    patient_name=f"Sim Patient {appointment_track_id}",
                    patient_email=f"sim{appointment_track_id}@example.com"
                )
            )
            previous_actual_end = completed_at

        current_day = current_day + timedelta(days=1)

    Appointment.objects.bulk_create(simulated_appointments)
