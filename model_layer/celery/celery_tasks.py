import requests
from datetime import datetime

from sqlalchemy.exc import OperationalError

from model_layer.celery.celery_app import app
from model_layer.celery.jobs import train_model, predict_model
from model_layer.utils.model_store import create_artifact_path
from model_layer.registry import MODEL_REGISTRY

@app.task(
    name = "tasks.train",
    autoretry_for=(requests.RequestException, OperationalError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,     
)
def train_task(config: dict):
    train_model(config)

@app.task(
    name="tasks.predict",
    autoretry_for=(requests.RequestException, OperationalError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def predict_task(config: dict):
    predict_model(config)

@app.task(
    name = "tasks.update"
)
def update_task(config: dict):
    pass

