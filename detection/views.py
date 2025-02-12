from django.shortcuts import render

# Create your views here.
# Will be adding it later with YOLOV8
def test_detection(request):
    return render(request, 'detection/test.html', {'message': 'YOLOv8 test view'})