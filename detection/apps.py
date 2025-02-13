from django.apps import AppConfig
import threading
from django.conf import settings
import os

class DetectionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'detection'
    detection_thread = None

    def ready(self):
        # Avoid multiple runs
        if os.environ.get('RUN_MAIN', None) != 'true':
            return

        # Import detection when ready
        from .detection_module import detection_loop
        if self.detection_thread is None or not self.detection_thread.is_alive():
            self.detection_thread = threading.Thread(target=detection_loop, daemon=True)
            self.detection_thread.start()