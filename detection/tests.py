from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class DetectionViewTests(TestCase):
    def setUp(self):
        self.pw = "LongPW123!"
        self.staff = User.objects.create_user("staffer", password=self.pw, is_staff=True)
        self.normal = User.objects.create_user("visitor", password=self.pw)

    def test_staff_can_view_live_video(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("video_view"))
        self.assertEqual(r.status_code, 200)

    def test_non_staff_redirected(self):
        self.client.force_login(self.normal)
        r = self.client.get(reverse("video_view"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r.url)
