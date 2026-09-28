"""Celery worker process entrypoint."""

from celery import Celery

celery_app = Celery("probeinterview")
