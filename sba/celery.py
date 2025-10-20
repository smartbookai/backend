import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sba.settings")
app = Celery("sba_app")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
app.conf.result_expires = 3 * 24 * 60 * 60  # 3 days