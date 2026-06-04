"""
Celery application configuration for background jobs.
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aquaculture.settings")

app = Celery("aquaculture")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
