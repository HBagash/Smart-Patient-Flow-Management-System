from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.test import TestCase
from datetime import timedelta

from detection.models import PersonSession
from queuing.models import NotificationRequest, Feedback

User = get_user_model()


class DashboardSimpleTests(TestCase):
    def setUp(self):
        self.pw = "pass1234"
        self.staff = User.objects.create_user(
            username="staffer", password=self.pw, is_staff=True
        )
        self.client.login(username="staffer", password=self.pw)

    def test_dashboard_renders(self):
        res = self.client.get(reverse("dashboard_home"))
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "dashboard/dashboard.html")

    def test_dashboard_outlier_banner(self):
        res = self.client.get(reverse("dashboard_home"), {"exclude_outliers": "1"})
        self.assertContains(res, "excluding</strong> outliers", html=False)

    def test_active_sessions_api_returns_json(self):
        res = self.client.post(reverse("active_sessions_api"))
        self.assertEqual(res.status_code, 200)
        self.assertIn("active_sessions", res.json())

    def test_export_csv_header_line(self):
        res = self.client.get(reverse("dashboard_export_csv"))
        self.assertEqual(res.status_code, 200)
        first_line = res.content.decode().splitlines()[0]
        self.assertEqual(first_line, "DASHBOARD CSV")


class NotificationCommandQuickTest(TestCase):
    def setUp(self):
        self.pw = "pw"
        self.staff = User.objects.create_user(
            username="s", password=self.pw, is_staff=True
        )

        now = timezone.now()
        NotificationRequest.objects.create(
            email="test@mail.com",
            date=now.date(),
            time_block=(now + timedelta(minutes=30)).time(),
        )

    def test_instant_feedback_path(self):
        from django.core import management
        from django.core import mail

        mail.outbox = []

        management.call_command(
            "check_notifications", "--instant-feedback", verbosity=0
        )
        self.assertFalse(NotificationRequest.objects.exists())
        self.assertEqual(Feedback.objects.count(), 1)
