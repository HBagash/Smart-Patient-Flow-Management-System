import time
import os
import numpy as np
import cv2
import mss
import torch
from ultralytics import YOLO

# Parameters
REFRESH_INTERVAL = 0.1
CONFIDENCE_THRESHOLD = 0.4
IOU_THRESHOLD = 0.5

DETECTION_ZONES = None

model_path = os.path.join(os.path.dirname(__file__), "yolov8-heads.pt")
model = YOLO(model_path)
device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
model.to(device)

def capture_screen(sct, monitor):
    """
    1) Capture the entire screen (BGRA).
    2) If DETECTION_ZONES is defined, black out everything except the given squares.
    """
    screenshot = sct.grab(monitor)
    img = np.array(screenshot)

    global DETECTION_ZONES
    if DETECTION_ZONES and "squares" in DETECTION_ZONES:
        mask = np.zeros_like(img)

        for zone in DETECTION_ZONES["squares"]:
            x1, y1, x2, y2 = zone["coords"]
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(x2, img.shape[1])
            y2 = min(y2, img.shape[0])

            mask[y1:y2, x1:x2] = img[y1:y2, x1:x2]

        img = mask

    # Convert from BGRA to BGR for OpenCV
    frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return frame

def perform_detection_on_frame(frame):
    """
    Run the YOLO model on frame. Draw bounding boxes. Return (frame_with_boxes, head_count).
    """
    results = model(frame, conf=CONFIDENCE_THRESHOLD, iou=0.25)
    head_count = 0
    detected_boxes = []

    if results and hasattr(results[0], "boxes") and results[0].boxes is not None:
        print("\n[DEBUG] Detected objects:")
        for result in results:
            for box in result.boxes:
                coords = box.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = map(int, coords)
                confidence = box.conf.item()
                cls = int(box.cls.item())

                print(f" - Class {cls} ({model.names[cls]}), Confidence {confidence:.2f}")

                duplicate = any(
                    compute_iou((x1, y1, x2, y2), prev) > IOU_THRESHOLD
                    for prev in detected_boxes
                )
                if duplicate:
                    continue

                detected_boxes.append((x1, y1, x2, y2))
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                label = f"{model.names[cls]}: {confidence:.2f}"
                cv2.putText(
                    frame,
                    label,
                    (x1, max(y1 - 10, 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2,
                )

                if cls == 1 and confidence >= CONFIDENCE_THRESHOLD:
                    head_count += 1

    print(f"[DEBUG] Head count detected: {head_count}")
    return frame, head_count

def compute_iou(box1, box2):
    x1_1, y1_1, x2_1, y2_1 = box1
    x1_2, y1_2, x2_2, y2_2 = box2

    inter_x1 = max(x1_1, x1_2)
    inter_y1 = max(y1_1, y1_2)
    inter_x2 = min(x2_1, x2_2)
    inter_y2 = min(y2_1, y2_2)

    inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
    box1_area = (x2_1 - x1_1) * (y2_1 - y1_1)
    box2_area = (x2_2 - x1_2) * (y2_2 - y1_2)
    union_area = box1_area + box2_area - inter_area
    return inter_area / union_area if union_area != 0 else 0

def detection_loop():
    """
    A background loop that continuously captures the screen and runs detection
    (e.g., for logging or other tasks). You can keep this separate from
    the streaming function if you want real-time logs or other actions.
    """
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        print(f"[INFO] Capturing from monitor: {monitor}")
        while True:
            frame = capture_screen(sct, monitor)
            processed_frame, count = perform_detection_on_frame(frame)
            print(f"[DEBUG] Detected {count} heads in the frame. (detection_loop)")
            time.sleep(REFRESH_INTERVAL)

def generate_video_stream():
    """
    A generator function that yields JPEG-encoded frames for streaming in the browser.
    """
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        print(f"[INFO] Streaming from monitor: {monitor}")
        while True:
            frame = capture_screen(sct, monitor)
            processed_frame, _ = perform_detection_on_frame(frame)
            ret, jpeg = cv2.imencode('.jpg', processed_frame)
            if not ret:
                continue
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n\r\n"
            )
            time.sleep(REFRESH_INTERVAL)