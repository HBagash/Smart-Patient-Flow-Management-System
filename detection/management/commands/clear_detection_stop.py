from django.core.management.base import BaseCommand
import os
from django.conf import settings

class Command(BaseCommand):
    help = "Destroys the stop flag so detection can be restarted."

    def handle(self, *args, **options):
        stop_file = os.path.join(settings.BASE_DIR, "detection_stop.flag")
        if os.path.exists(stop_file):
            os.remove(stop_file)
            self.stdout.write("Stop flag removed.")
        else:
            self.stdout.write("No stop flag found.")
