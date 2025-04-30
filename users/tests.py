from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import TestCase

User = get_user_model()


class AuthFlowTests(TestCase):
    def setUp(self):
        self.password = "Pass1234!"
        self.u = User.objects.create_user(
            username="demo", password=self.password, email="demo@mail.com", is_staff=True
        )

    def test_register_creates_user_and_logs_in(self):
        resp = self.client.post(
            reverse("register"),
            {
                "username": "newbie",
                "email":    "new@mail.com",
                "password1": "Pass1234!",
                "password2": "Pass1234!",
            },
            follow=True,
        )
        self.assertTrue(User.objects.filter(username="newbie").exists())
        self.assertTrue(resp.context["user"].is_authenticated)

    def test_login_and_logout(self):
        # login
        resp = self.client.post(
            reverse("login"),
            {"username": "demo", "password": self.password},
            follow=True,
        )
        self.assertTrue(resp.context["user"].is_authenticated)

        # logout
        resp2 = self.client.post(reverse("logout"), follow=True)
        self.assertFalse(resp2.context["user"].is_authenticated)
