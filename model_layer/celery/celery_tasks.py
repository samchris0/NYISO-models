import requests
from datetime import datetime, timedelta

from sqlalchemy.exc import OperationalError
from sqlalchemy import or_

from model_layer.celery.celery_app import app
from model_layer.db.database import SessionLocal
from model_layer.db.tables import *
from model_layer.celery.jobs.create_jobs import create_jobs
from model_layer.celery.jobs.ingest_lbmp_zonal import ingest_lbmp_zonal
from model_layer.celery.jobs.predict_model import predict_model
from model_layer.celery.jobs.train_model import train_model
from model_layer.utils.claim_jobs import claim_training_job, claim_predicting_job
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
    max_retries=3,
)
def ingest_realtime_lbmp_zonal_task():
    ingest_lbmp_zonal()


@app.task(
    name = "tasks.create_jobs",
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
def dispatch_training_jobs(batch_size=5):
    now = now_ny()

    with SessionLocal() as db:

        rows = (
            db.query(TrainingJob.id) #type: ignore
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

    for (job_id,) in rows:
        train_task.delay(job_id) #type: ignore

@app.task(name="tasks.dispatch_prediction_jobs")
def dispatch_prediction_jobs(batch_size=50):
    now = now_ny()

    with SessionLocal() as db:
        
        rows = (
            db.query(PredictionJob.id) #type: ignore
            .join(ForecastRun, ForecastRun.id==PredictionJob.run_id)
            .filter(ForecastRun.enabled.is_(True),
                    ForecastRun.status == "running",
                    PredictionJob.scheduled_for <= now,
                    PredictionJob.status.in_(["pending","retryable"]),
                    or_(
                        PredictionJob.next_attempt_at.is_(None),
                        PredictionJob.next_attempt_at <= now
                    )
                )
            .order_by(PredictionJob.scheduled_for, PredictionJob.id)
            .limit(batch_size)
            .all()
        )

        for (job_id,) in rows:
            predict_task.delay(job_id) #type: ignore


@app.task(
    name="tasks.predict",
)
def predict_task(job_id: int):
    
    attempt_count = claim_predicting_job(job_id)

    if attempt_count is None:
        return
    
    predict_model(job_id, attempt_count)


#################### EVALUATE BELOW THIS LINE ####################





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
