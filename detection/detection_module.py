import time
import os
import numpy as np
import cv2
import mss
import torch
from datetime import datetime
from django.utils import timezone  # for timezone-aware datetimes

from ultralytics import YOLO

# Import our custom tracker from deep_sort_realtime wrapper
from .custom_tracker import Tracker

# Instantiate the tracker globally
tracker = Tracker()

####################
# CONFIG & GLOBALS #
####################
REFRESH_INTERVAL = 0.1
CONFIDENCE_THRESHOLD = 0.4

# YOLO model setup
model_path = os.path.join(os.path.dirname(__file__), "yolov8-heads.pt")
model = YOLO(model_path)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

def capture_screen(sct, monitor):
    """
    Capture the screen using MSS and return an OpenCV BGR frame.
    """
    screenshot = sct.grab(monitor)
    img = np.array(screenshot)
    frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return frame

def detect_and_track(frame):
    """
    Run YOLO on the frame, convert detections, update the tracker,
    and draw bounding boxes with track IDs.
    Returns (annotated_frame, tracks).
    """
    # 1) YOLO inference
    results = model(frame, conf=CONFIDENCE_THRESHOLD, iou=0.5)
    detections = results[0]

    # 2) Build detection list in format: [x1, y1, x2, y2, conf]
    detection_list = []
    for box in detections.boxes:
        xyxy = box.xyxy[0].cpu().numpy()  # [x1, y1, x2, y2]
        conf = float(box.conf[0].cpu().numpy())
        if conf >= CONFIDENCE_THRESHOLD:
            x1, y1, x2, y2 = map(float, xyxy)
            detection_list.append([x1, y1, x2, y2, conf])
    
    # 3) Update tracker using our custom tracker
    tracks = tracker.update(frame, detection_list)

    # 4) Draw bounding boxes with IDs on a copy of the frame
    annotated_frame = frame.copy()
    for track_id, bbox in tracks:
        x1, y1, x2, y2 = map(int, bbox)
        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(annotated_frame, f"ID: {track_id}", (x1, max(y1-10, 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    return annotated_frame, tracks

def detection_loop():
    """
    Continuously captures frames, performs detection and tracking,
    and updates PersonSession records.
    """
    from .models import PersonSession
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        print(f"[INFO] Capturing from monitor: {monitor}")
        known_ids = set()
        while True:
            frame = capture_screen(sct, monitor)
            annotated_frame, tracks = detect_and_track(frame)

            current_ids = set()
            for track in tracks:
                track_id = str(track[0])
                current_ids.add(track_id)
                open_session = PersonSession.objects.filter(
                    track_id=track_id,
                    exit_timestamp__isnull=True
                ).first()
                if open_session is None:
                    PersonSession.objects.create(
                        track_id=track_id,
                        enter_timestamp=timezone.now()
                    )
            # Update sessions for disappeared tracks
            disappeared = known_ids - current_ids
            for track_id in disappeared:
                session = PersonSession.objects.filter(
                    track_id=track_id,
                    exit_timestamp__isnull=True
                ).first()
                if session:
                    session.exit_timestamp = timezone.now()
                    session.duration_seconds = (
                        session.exit_timestamp - session.enter_timestamp
                    ).total_seconds()
                    session.save()
                    print(f"[INFO] Track {track_id} exited. Duration: {session.duration_seconds:.2f} sec")
            known_ids = current_ids
            time.sleep(REFRESH_INTERVAL)

def generate_video_stream():
    """
    Generator that yields JPEG-encoded frames for streaming.
    """
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        print(f"[INFO] Streaming from monitor: {monitor}")
        while True:
            frame = capture_screen(sct, monitor)
            annotated_frame, _ = detect_and_track(frame)
            ret, jpeg = cv2.imencode('.jpg', annotated_frame)
            if not ret:
                continue
            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n'
            )
            time.sleep(REFRESH_INTERVAL)

def perform_detection_on_frame(frame):
    """
    Wrapper that returns the annotated frame and head count (number of tracks).
    """
    annotated_frame, tracks = detect_and_track(frame)
    head_count = len(tracks)
    return annotated_frame, head_count
