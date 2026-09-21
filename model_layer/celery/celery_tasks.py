import requests
from datetime import datetime, timedelta

from sqlalchemy.exc import OperationalError
from sqlalchemy import or_

from model_layer.celery.celery_app import app
from model_layer.db.database import SessionLocal
from model_layer.db.tables.forecast_run import ForecastRun
from model_layer.db.tables.training_job import TrainingJob
from model_layer.celery.jobs import train_model, predict_model, evaluate_pending_predictions, ingest_lbmp_zonal, create_jobs
from model_layer.utils.claim_jobs import claim_training_job, claim_predicting_job
from model_layer.utils.model_store import create_artifact_path
from model_layer.utils.time import now_ny
from model_layer.registry import MODEL_REGISTRY

@app.task(
    name="tasks.ingest_realtime_lbmp_zonal",
    autoretry_for=(
        requests.RequestException,
        OperationalError,
    ),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def ingest_realtime_lbmp_zonal_task():
    ingest_lbmp_zonal()


@app.task(
    name = "tasks.create_jobs",
    autoretry_for = (
         OperationalError,
    ),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def create_jobs_task(horizon = timedelta(minutes=30)):
    create_jobs(horizon)

@app.task(
    name="tasks.train"
)
def train_task(job_id: int):
    
    attempt_count = claim_training_job(job_id)

    if attempt_count is None:
        return
    
    train_model(job_id, attempt_count)

@app.task(name="tasks.dispatch_training_jobs")
def dispatch_training_jobs(batch_size=10):
    now = now_ny()

    with SessionLocal() as db:

        rows = (
            db.query(ForecastRun.id, TrainingJob.id) #type: ignore
            .join(ForecastRun, ForecastRun.id == TrainingJob.run_id)
            .filter(
                ForecastRun.enabled.is_(True),
                ForecastRun.status == "running",
                TrainingJob.status.in_(["pending","retryable"]),
                TrainingJob.scheduled_for <= now,
                or_(
                    TrainingJob.next_attempt_at.is_(None),
                    TrainingJob.next_attempt_at <= now
                )

            )
            .order_by(TrainingJob.scheduled_for, TrainingJob.id)
            .limit(batch_size)
            .all()
        )

    for run_id, job_id in rows:
        train_task.delay(job_id)


#################### EVALUATE BELOW THIS LINE ####################



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

@app.task(
    name="tasks.evaluate",
    autoretry_for=(
        requests.RequestException,
        OperationalError,
    ),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def evaluate_task(batch_size: int = 500) -> int:
    return evaluate_pending_predictions(batch_size=batch_size)
