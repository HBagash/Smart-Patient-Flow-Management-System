from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from queuing.models import NotificationRequest, Feedback
from dashboard.kalman import predict_appointment_kalman

class Command(BaseCommand):
    help = """Checks for any changes in the predicted wait times, simulates them if requested, 
              and then does cleanup after arrival_time + offset with a feedback email."""

    DEFAULT_CLEANUP_OFFSET_HOURS = 1

    def add_arguments(self, parser):
        parser.add_argument(
            '--simulate',
            type=str,
            default=None,
            help='Simulate a new category (LOW, MODERATE, or HIGH). Omit for real predictions.'
        )
        parser.add_argument(
            '--simulate-cleanup-secs',
            type=int,
            default=None,
            help='Override the 1-hour cleanup offset with an N-second offset for testing.'
        )
        parser.add_argument(
        '--instant-feedback',
        action='store_true',
        help='If set, feedback will immediately be sent off right after confirmation.'
        )

    def handle(self, *args, **options):
        now = timezone.now()
        simulate_category = options.get('simulate')
        simulate_cleanup_secs = options.get('simulate_cleanup_secs', None)
        instant_feedback = options.get('instant_feedback', False)

        if simulate_cleanup_secs is not None:
            cleanup_offset_hours = simulate_cleanup_secs / 3600.0
        else:
            cleanup_offset_hours = self.DEFAULT_CLEANUP_OFFSET_HOURS

        self.recheck_requests(now, simulate_category, instant_feedback)
        self.cleanup_old_requests(now, cleanup_offset_hours)

        self.stdout.write(self.style.SUCCESS(
            f"Notification re-check completed with cleanup offset = {cleanup_offset_hours} hr(s)."
        ))

    def recheck_requests(self, now, simulate_category, instant_feedback):
        today = now.date()
        future_reqs = NotificationRequest.objects.filter(
            date__gte=today,
            status__in=["pending", "sent"]
        )

        for req in future_reqs:
            dt_combined = datetime.combine(req.date, req.time_block)
            dt_aware = timezone.make_aware(dt_combined, timezone.get_current_timezone())

            if dt_aware > now:
                predicted_secs = predict_appointment_kalman(dt_aware, 8, exclude_outliers=True)
                new_category = req.categorize_wait(predicted_secs)

                if simulate_category:
                    new_category = simulate_category.upper().capitalize()

                old_category = req.last_predicted_category or "unknown"

                if new_category != old_category and old_category != "unknown":
                    self.send_followup_email(req, old_category, new_category, predicted_secs)

                req.last_predicted_wait_mins = predicted_secs / 60
                req.last_predicted_category = new_category
                req.save()

                if instant_feedback:
                    self.send_feedback_email(req)
                    req.delete()


    def send_followup_email(self, req, old_cat, new_cat, predicted_secs):
        if predicted_secs < 60:
            display_wait = f"{int(predicted_secs)} seconds"
        else:
            display_wait = f"{round(predicted_secs / 60, 2)} minutes"

        subject = f"Updated Waiting Time for {req.date} {req.time_block.strftime('%I:%M %p')}"
        msg = (
            f"Hello,\n\n"
            f"We've detected a change in the expected waiting time for your scheduled visit on "
            f"{req.date} at {req.time_block.strftime('%I:%M %p')}.\n\n"
            f"It was previously categorized as '{old_cat}', but now it's '{new_cat}'.\n"
            f"We now estimate about {display_wait} of waiting.\n\n"
            f"If you prefer less waiting, consider adjusting your arrival.\n\n"
            f"Thank you,\n"
            f"Smart Patient Flow System"
        )
        send_mail(
            subject,
            msg,
            settings.DEFAULT_FROM_EMAIL,
            [req.email],
            fail_silently=False
        )

    def cleanup_old_requests(self, now, cleanup_offset_hours):
        old_reqs = NotificationRequest.objects.filter(status__in=["pending","sent"])
        to_delete = []

        for req in old_reqs:
            dt_combined = datetime.combine(req.date, req.time_block)
            dt_aware = timezone.make_aware(dt_combined, timezone.get_current_timezone())

            if dt_aware + timedelta(hours=cleanup_offset_hours) < now:
                to_delete.append(req)

        for req in to_delete:
            self.send_feedback_email(req)
            req.delete()

    def send_feedback_email(self, req):
        fb = Feedback.objects.create(
            notification_preference="email"
        )
        feedback_link = f"http://127.0.0.1:8000/queuing/feedback/{fb.token}/"

        subject = f"Feedback Requested for Your Visit on {req.date}"
        msg = (
            f"Hello,\n\n"
            f"We hope your visit around {req.time_block.strftime('%I:%M %p')} went well.\n"
            f"We'd love to hear how your experience was.\n\n"
            f"Please click the link below to share your feedback (it only takes a minute!):\n"
            f"{feedback_link}\n\n"
            f"Thank you,\n"
            f"Smart Patient Flow System"
        )

        send_mail(
            subject,
            msg,
            settings.DEFAULT_FROM_EMAIL,
            [req.email],
            fail_silently=False
        )
