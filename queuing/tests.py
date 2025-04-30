from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import TestCase

User = get_user_model()


class QueuingViewsTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staffer", password="pass1234", is_staff=True
        )
        self.client.login(username="staffer", password="pass1234")

    def test_feedback_analytics_renders(self):
        r = self.client.get(reverse("feedback_analytics"))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "queuing/feedback_analytics.html")

    def test_export_csv_has_headers(self):
        r = self.client.get(reverse("dashboard_export_csv"))
        self.assertEqual(r.status_code, 200)
        first_line = r.content.decode().splitlines()[0]
        self.assertEqual(first_line, "DASHBOARD CSV")
