from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
import numpy as np
import cv2
from detection.models import PersonSession
from django.utils import timezone
from datetime import timedelta
from detection.detection_module import compute_iou, extract_appearance_feature

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

class DetectionUtilsTests(TestCase):
    def test_compute_iou_overlap(self):
        box1 = [10, 10, 100, 100]
        box2 = [20, 20, 80, 80]
        iou = compute_iou(box1, box2)
        self.assertGreater(iou, 0.0)
        self.assertLessEqual(iou, 1.0)

    def test_compute_iou_no_overlap(self):
        box1 = [10, 10, 50, 50]
        box2 = [60, 60, 100, 100]
        iou = compute_iou(box1, box2)
        self.assertEqual(iou, 0.0)

    def test_extract_appearance_feature_valid(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.rectangle(img, (30, 30), (70, 70), (0, 255, 0), -1)
        feat = extract_appearance_feature(img, (30, 30, 70, 70))
        self.assertIsInstance(feat, list)
        self.assertGreater(len(feat), 0)

    def test_extract_appearance_feature_empty(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        feat = extract_appearance_feature(img, (0, 0, 0, 0))
        self.assertIsNone(feat)

class PersonSessionTests(TestCase):
    def test_waiting_time_calculates_correctly(self):
        now = timezone.now()
        session = PersonSession.objects.create(
            track_id="abc",
            enter_timestamp=now - timedelta(minutes=10),
            exit_timestamp=now
        )
        self.assertAlmostEqual(session.waiting_time, 600, delta=2)

class ZoneResetTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username="admin", password="admin123", is_staff=True)
        self.client.login(username="admin", password="admin123")

    def test_reset_zone_post(self):
        resp = self.client.post(reverse("reset_detection_zone"))
        self.assertEqual(resp.status_code, 200)
        self.assertJSONEqual(resp.content, {"status": "success", "zone": None})

