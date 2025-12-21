from django.apps import AppConfig
import subprocess
import sys

class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'

    def ready(self):
        import app.signals 
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "app.gemini.ocr_worker",
                "__warmup__",
                "NUL",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )