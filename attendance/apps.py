import os
import sys

from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'attendance'

    def ready(self):
        # No iniciar scheduler durante migrate, collectstatic u otros commands
        if len(sys.argv) > 1 and sys.argv[1] in ('migrate', 'collectstatic', 'makemigrations', 'shell', 'dbshell', 'createsuperuser'):
            return

        run_scheduler = os.environ.get('RUN_SCHEDULER', 'true').lower() == 'true'
        if run_scheduler:
            from attendance import jobs
            jobs.start()
