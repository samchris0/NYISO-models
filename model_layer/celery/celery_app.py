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
    Queue("ingesting"),
    Queue("create_jobs"),
    Queue("training"),
    Queue("predicting"),
    Queue("updating"),
    Queue("evaluating"),
)

app.conf.task_routes = {
    "tasks.ingest_realtime_lbmp_zonal" : {
        "queue": "ingesting"
    },
    "tasks.create_jobs" : {
        "queue": "create_jobs"
    },
    "tasks.dispatch_training_jobs" : {
        "queue": "create_jobs"
    },
    "tasks.dispatch_prediction_jobs" : {
        "queue": "create_jobs"
    },
    "tasks.train": {
        "queue": "training",
    },
    "tasks.predict": {
        "queue": "predicting",
    },
    "tasks.update": {
        "queue": "updating",
    },
    "tasks.evaluate": {
        "queue": "evaluating"
    },
}

app.conf.timezone = 'America/New_York' #type: ignore
app.conf.beat_schedule = build_beat_schedule('model_layer/tasks.yaml')