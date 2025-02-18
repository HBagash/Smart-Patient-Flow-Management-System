import time
import os
import numpy as np
import cv2
import mss
import torch
from datetime import datetime
from django.utils import timezone
from ultralytics import YOLO

REFRESH_INTERVAL = 0
CONFIDENCE_THRESHOLD = 0.35
TRACKER_CONFIG = 'bytetrack.yaml'
MODEL_PATH = os.path.join(os.path.dirname(__file__), "yolov8x.pt")

model = YOLO(MODEL_PATH)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

_contiguous_id_map = {}
_next_contiguous_id = 1

def get_contiguous_id(raw_id):
    global _next_contiguous_id
    if raw_id not in _contiguous_id_map:
        _contiguous_id_map[raw_id] = str(_next_contiguous_id)
        _next_contiguous_id += 1
    return _contiguous_id_map[raw_id]

def capture_screen(sct, monitor, target_width=640):
    screenshot = sct.grab(monitor)
    img = np.array(screenshot)
    return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

def extract_appearance_feature(frame, bbox):
    x1, y1, x2, y2 = map(int, bbox)
    roi = frame[y1:y2, x1:x2]
    if roi.size == 0:
        return None
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, [8,8,8], [0,180,0,256,0,256])
    cv2.normalize(hist, hist)
    return hist.flatten().tolist()

def compute_iou(boxA, boxB):
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    interW = max(0, xB - xA)
    interH = max(0, yB - yA)
    interArea = interW * interH
    areaA = (boxA[2]-boxA[0]) * (boxA[3]-boxA[1])
    areaB = (boxB[2]-boxB[0]) * (boxB[3]-boxB[1])
    return interArea / float(areaA + areaB - interArea + 1e-6)

def detect_and_track(frame, iou_thresh=0.3):
    total_start = time.time()
    raw_frame = frame.copy()

    raw_results = model(raw_frame, conf=CONFIDENCE_THRESHOLD, iou=0.5)
    raw_boxes = []
    for box in raw_results[0].boxes:
        if hasattr(box, 'cls') and int(box.cls[0].item()) == 0:
            coords = list(map(int, box.xyxy[0].tolist()))
            conf = float(box.conf[0].item())
            raw_boxes.append({'bbox': coords, 'confidence': conf})

    annotated = raw_frame.copy()
    for det in raw_boxes:
        x1, y1, x2, y2 = det['bbox']
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 0, 0), 2)

    track_results = model.track(
        source=raw_frame,
        conf=CONFIDENCE_THRESHOLD,
        iou=0.5,
        tracker=TRACKER_CONFIG,
        persist=True,
        show=False
    )
    if not track_results:
        print("[WARNING] No tracking results.")
        return annotated, []
    
    final_result = track_results[-1]
    tracker_boxes = []
    for box in getattr(final_result, 'boxes', []):
        if box.id is None:
            continue
        if hasattr(box, 'cls') and int(box.cls[0].item()) != 0:
            continue
        coords = list(map(int, box.xyxy[0].tolist()))
        conf = float(box.conf[0].item())
        tracker_boxes.append({'raw_id': str(box.id), 'bbox': coords, 'confidence': conf})

    track_list = []
    for det in raw_boxes:
        best_match = None
        best_iou = 0
        for trk in tracker_boxes:
            iou_val = compute_iou(det['bbox'], trk['bbox'])
            if iou_val > best_iou:
                best_iou = iou_val
                best_match = trk
        if best_match and best_iou > iou_thresh:
            norm_id = get_contiguous_id(best_match['raw_id'])
        else:

            new_raw = f"new_{len(_contiguous_id_map)+1}"
            norm_id = get_contiguous_id(new_raw)
        det['track_id'] = norm_id
        track_list.append(det)

        x1, y1, x2, y2 = det['bbox']
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(annotated, f"ID:{norm_id} {det['confidence']:.2f}", (x1, max(y1-10,10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)

    total_end = time.time()
    print(f"[TIMING] Total: {(total_end - total_start)*1000:.2f}ms")
    return annotated, track_list

def detection_loop():
    from .models import PersonSession
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        print(f"[INFO] Capturing from monitor: {monitor}")
        while True:
            frame = capture_screen(sct, monitor, target_width=640)
            annotated_frame, track_list = detect_and_track(frame)
            current_ids = set()
            for t in track_list:
                norm_id = t['track_id']
                bbox = t['bbox']
                current_ids.add(norm_id)
                if not PersonSession.objects.filter(track_id=norm_id, exit_timestamp__isnull=True).exists():
                    feature = extract_appearance_feature(frame, bbox)
                    PersonSession.objects.create(
                        track_id=norm_id,
                        enter_timestamp=timezone.now(),
                        appearance_feature=feature
                    )
                    print(f"[INFO] New PersonSession for ID: {norm_id}")
                    
            for norm_id in set().union(*[ {s.track_id} for s in PersonSession.objects.filter(exit_timestamp__isnull=True) ]) - current_ids:
                session = PersonSession.objects.filter(track_id=norm_id, exit_timestamp__isnull=True).first()
                if session:
                    session.exit_timestamp = timezone.now()
                    session.duration_seconds = (session.exit_timestamp - session.enter_timestamp).total_seconds()
                    session.save()
                    print(f"[INFO] ID {norm_id} left. Duration: {session.duration_seconds:.2f} sec")
            time.sleep(REFRESH_INTERVAL)

def generate_video_stream():
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        print(f"[INFO] Streaming from monitor: {monitor}")
        while True:
            frame = capture_screen(sct, monitor, target_width=640)
            annotated_frame, _ = detect_and_track(frame)
            ret, jpeg = cv2.imencode('.jpg', annotated_frame)
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')
            time.sleep(REFRESH_INTERVAL)

def perform_detection_on_frame(frame):
    annotated_frame, track_list = detect_and_track(frame)
    return annotated_frame, len(track_list)
