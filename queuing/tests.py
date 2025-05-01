from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import TestCase
from datetime import date, time
from queuing.models import Feedback, NotificationRequest

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

class FeedbackFormTests(TestCase):
    def setUp(self):
        self.fb = Feedback.objects.create(notification_preference="email")

    def test_feedback_form_submission_marks_submitted(self):
        url = reverse("feedback_form", kwargs={"token": self.fb.token})
        resp = self.client.post(url, {
            "rating_notification_usefulness": 9,
            "rating_ease_of_use": 8,
            "rating_overall_experience": 7,
            "rating_recommendation": 10
        })
        self.assertEqual(resp.status_code, 200)
        self.fb.refresh_from_db()
        self.assertTrue(self.fb.submitted)

class NotificationCategorisationTests(TestCase):
    def test_wait_categorisation(self):
        r = NotificationRequest(email="test@mail.com", date=date.today(), time_block=time(hour=10))
        self.assertEqual(r.categorize_wait(60), "Low")
        self.assertEqual(r.categorize_wait(300), "Moderate")
        self.assertEqual(r.categorize_wait(1200), "High")

