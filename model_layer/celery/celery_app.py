import os

from celery import Celery
from kombu import Queue

from model_layer.celery.schedule_loader import build_beat_schedule

app = Celery(
    'nyiso_models',
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    include=["model_layer.celery.celery_tasks"],
)

app.conf.task_queues = (
    Queue("training"),
    Queue("predicting"),
    Queue("updating"),
)

app.conf.task_routes = {
    "tasks.train": {
        "queue": "training",
    },
    "tasks.predict": {
        "queue": "predicting",
    },
    "tasks.update": {
        "queue": "updating",
    },
}

app.conf.timezone = 'America/New_York' #type: ignore
app.conf.beat_schedule = build_beat_schedule('model_layer/models.yaml')