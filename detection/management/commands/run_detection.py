from django.core.management.base import BaseCommand
from detection.detection_module import detection_loop

class Command(BaseCommand):
    help = 'Runs the YOLOv8 detection module'

    def handle(self, *args, **options):
        self.stdout.write("Starting Detection...")
        detection_loop()
        self.stdout.write("Detection has stopped.")