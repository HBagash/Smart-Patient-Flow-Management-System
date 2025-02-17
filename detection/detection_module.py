import time
import os
import numpy as np
import cv2
import mss
import torch
from datetime import datetime
from django.utils import timezone  # for timezone-aware datetimes

from ultralytics import YOLO

####################
# CONFIG & GLOBALS #
####################
REFRESH_INTERVAL = 0
CONFIDENCE_THRESHOLD = 0.35
TRACKER_CONFIG = 'bytetrack.yaml'  # or full path: './ultralytics/trackers/bytetrack.yaml'

model_path = os.path.join(os.path.dirname(__file__), "yolov8-heads.pt")
model = YOLO(model_path)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

def capture_screen(sct, monitor, target_width=640):
    """
    Capture the screen using MSS, resize it to target_width, return an OpenCV BGR frame.
    """
    screenshot = sct.grab(monitor)
    img = np.array(screenshot)
    frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    h, w = frame.shape[:2]
    scale = target_width / float(w)
    target_height = int(h * scale)
    #frame = cv2.resize(frame, (target_width, target_height))
    return frame

import time  # Import time module for measuring performance

def detect_and_track(frame):
    """
    Runs YOLOv8 tracking with ByteTrack, measuring the time taken for:
    - Preprocessing (capturing and resizing the frame)
    - Inference (object detection using YOLOv8)
    - Tracking (ByteTrack updating object IDs)
    - Total processing time
    """
    total_start = time.time()  # Start total processing timer

    # Step 1: Preprocessing Timer
    preprocess_start = time.time()
    input_frame = frame.copy()  # Avoid modifying original frame
    preprocess_end = time.time()
    preprocess_time = (preprocess_end - preprocess_start) * 1000  # Convert to ms

    # Step 2: Inference (YOLOv8 Detection)
    inference_start = time.time()
    results = model.track(
        source=input_frame,
        conf=CONFIDENCE_THRESHOLD,
        iou=0.5,
        tracker=TRACKER_CONFIG,
        persist=True,
        show=False
    )
    inference_end = time.time()
    inference_time = (inference_end - inference_start) * 1000  # Convert to ms

    if not results:
        return frame, []

    # Step 3: Tracking (ByteTrack Processing)
    tracking_start = time.time()
    final_result = results[-1]
    tracks = getattr(final_result, 'boxes', [])
    
    annotated_frame = frame.copy()
    track_list = []

    for box in tracks:
        track_id = box.id
        if track_id is None:
            continue
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        conf = float(box.conf[0].item())

        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"ID:{track_id} {conf:.2f}"
        cv2.putText(annotated_frame, label, (x1, max(y1 - 10, 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        track_list.append({
            'track_id': str(track_id),
            'bbox': (x1, y1, x2, y2),
            'confidence': conf
        })
    
    tracking_end = time.time()
    tracking_time = (tracking_end - tracking_start) * 1000  # Convert to ms

    # Step 4: Calculate Total Processing Time
    total_end = time.time()
    total_time = (total_end - total_start) * 1000  # Convert to ms

    # Print performance metrics
    print(f"[TIMING] Preprocessing: {preprocess_time:.2f}ms | "
          f"Inference: {inference_time:.2f}ms | "
          f"Tracking: {tracking_time:.2f}ms | "
          f"Total: {total_time:.2f}ms")

    return annotated_frame, track_list


def detection_loop():
    """
    Continuously captures frames, performs ByteTrack-based detection/tracking,
    and updates PersonSession records in the DB.
    """
    from .models import PersonSession
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        print(f"[INFO] Capturing from monitor: {monitor}")

        known_ids = set()
        
        while True:
            frame = capture_screen(sct, monitor, target_width=640)
            annotated_frame, track_list = detect_and_track(frame)
            
            current_ids = set()
            for t in track_list:
                track_id = t['track_id']
                current_ids.add(track_id)
                open_session = PersonSession.objects.filter(
                    track_id=track_id, exit_timestamp__isnull=True
                ).first()
                if open_session is None:
                    PersonSession.objects.create(
                        track_id=track_id,
                        enter_timestamp=timezone.now()
                    )
                    print(f"[INFO] New PersonSession for ID: {track_id}")
            
            disappeared = known_ids - current_ids
            for track_id in disappeared:
                session = PersonSession.objects.filter(
                    track_id=track_id, exit_timestamp__isnull=True
                ).first()
                if session:
                    session.exit_timestamp = timezone.now()
                    session.duration_seconds = (
                        session.exit_timestamp - session.enter_timestamp
                    ).total_seconds()
                    session.save()
                    print(f"[INFO] ID {track_id} left. Duration: {session.duration_seconds:.2f} sec")
            
            known_ids = current_ids
            time.sleep(REFRESH_INTERVAL)

def generate_video_stream():
    """
    MJPEG stream generator. Captures frames and uses ByteTrack.
    """
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        print(f"[INFO] Streaming from monitor: {monitor}")
        while True:
            frame = capture_screen(sct, monitor, target_width=640)
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
    Helper for single-frame detection: returns (annotated_frame, number_of_tracks).
    """
    annotated_frame, track_list = detect_and_track(frame)
    head_count = len(track_list)
    return annotated_frame, head_count
