from django.shortcuts import render
from ultralytics import YOLO
import os

def test_detection(request):
    # Load the yolov8 model
    model = YOLO('yolov8n.pt')

    image_path = os.path.join('static', 'images', 'sample.jpg')
    results = model(image_path)

    num_detections = len(results[0].boxes) if results and results[0].boxes is not None else 0

    context = {
        'num_detections': num_detections,
    }
    return render(request, 'detection/test.html', context)
