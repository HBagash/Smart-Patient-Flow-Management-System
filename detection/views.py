from django.shortcuts import render
from django.http import StreamingHttpResponse
import cv2
import time

# Import functions from your detection module
from .detection_module import (
    capture_screen,
    perform_detection_on_frame,
    generate_video_stream,
)

# Import the model for storing detection records (if needed)
from .models import DetectionRecord

def latest_detection(request):
    """
    Retrieve the latest detection record and render it.
    """
    record = DetectionRecord.objects.order_by('-timestamp').first()
    context = {'record': record}
    return render(request, 'detection/latest.html', context)

def video_feed(request):
    """
    Streams processed video frames (with bounding boxes and labels)
    as an MJPEG stream.
    """
    return StreamingHttpResponse(
        generate_video_stream(),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )

def test_detection(request):
    """
    Performs a single detection on a captured frame and displays the person count.
    """
    frame = capture_screen()
    processed_frame, person_count = perform_detection_on_frame(frame)
    context = {'count': person_count}
    return render(request, 'detection/test.html', context)

def video_view(request):
    """
    Renders an HTML page that embeds the live video feed.
    """
    return render(request, 'detection/video.html')
