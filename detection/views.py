from django.shortcuts import render
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .detection_module import capture_screen, perform_detection_on_frame, generate_video_stream
from . import detection_module
from django.contrib.admin.views.decorators import staff_member_required
from .models import PersonSession
import json
import mss

@staff_member_required(login_url='login')
def video_feed(request):
    return StreamingHttpResponse(
        generate_video_stream(),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )

@staff_member_required(login_url='login')
def video_view(request):
    return render(request, 'detection/video.html')

@csrf_exempt
@staff_member_required(login_url='login')
def update_detection_zones_multiple(request):
    
    if request.method == "POST":
        try:
            rects_str = request.POST.get("rects")
            rects_list = json.loads(rects_str)
            origWidth = int(request.POST.get("origWidth"))
            origHeight = int(request.POST.get("origHeight"))
            zones = []
            for rect in rects_list:
                x1, y1, x2, y2 = rect
                zones.append({"coords": (x1, y1, x2, y2)})
            detection_module.DETECTION_ZONES = {
                "squares": zones,
                "origWidth": origWidth,
                "origHeight": origHeight,
            }
            return JsonResponse({"status": "success", "zones": zones})
        except Exception as e:
            return JsonResponse({"status": "error", "error": str(e)})
    else:
        return JsonResponse({"status": "error", "error": "POST request required"})

@csrf_exempt
@staff_member_required(login_url='login')
def reset_detection_zone(request):
    if request.method == "POST":
        detection_module.DETECTION_ZONES = None
        return JsonResponse({"status": "success", "zone": None})
    else:
        return JsonResponse({"status": "error", "error": "POST request required"})
