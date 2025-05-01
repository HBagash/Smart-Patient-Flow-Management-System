from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.test import TestCase
from datetime import timedelta
from dashboard.kalman import predict_appointment_kalman, kalman_filter_update
from dashboard.utils import (
    get_overview_data, _exclude_outliers_qs,
    get_wait_time_distribution_custom
)

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

class KalmanPredictionTests(TestCase):
    def setUp(self):
        now = timezone.now()
        for i in range(10):
            enter = now - timedelta(minutes=20 * (i + 1))
            exit = enter + timedelta(seconds=600 + i * 10)
            PersonSession.objects.create(
                track_id=f"test_{i}",
                enter_timestamp=enter,
                exit_timestamp=exit,
                duration_seconds=(exit - enter).total_seconds(),
                active=False
            )

    def test_kalman_prediction_value(self):
        future_dt = timezone.now() + timedelta(days=1)
        prediction = predict_appointment_kalman(future_dt)
        self.assertGreater(prediction, 0)

    def test_kalman_filter_update_logic(self):
        est, cov = kalman_filter_update(650, 600, 500)
        self.assertTrue(600 < est < 650)
        self.assertLess(cov, 500)

class DashboardUtilsTests(TestCase):
    def setUp(self):
        now = timezone.now()
        for i in range(10):
            enter = now - timedelta(hours=i + 1)
            exit = enter + timedelta(seconds=300 + i * 20)
            PersonSession.objects.create(
                track_id=f"test_{i}",
                enter_timestamp=enter,
                exit_timestamp=exit,
                duration_seconds=(exit - enter).total_seconds(),
                active=False
            )

    def test_overview_data(self):
        result = get_overview_data()
        self.assertIn("avg_wait", result)
        self.assertIn("max_wait", result)
        self.assertGreaterEqual(result["avg_wait"], 0)

    def test_exclude_outliers(self):
        qs = PersonSession.objects.exclude(exit_timestamp__isnull=True)
        filtered = _exclude_outliers_qs(qs, 'duration_seconds')
        self.assertTrue(filtered.count() <= qs.count())

    def test_wait_time_distribution(self):
        now = timezone.now()
        result = get_wait_time_distribution_custom(
            now - timedelta(days=1), now, bin_size=300
        )
        self.assertIsInstance(result, list)
