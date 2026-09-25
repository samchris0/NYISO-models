import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import update

from model_layer.db.database import SessionLocal
from model_layer.db.tables.forecast_run import ForecastRun
from model_layer.db.tables.model_version import ModelVersion
from model_layer.db.tables.prediction_job import PredictionJob
from model_layer.db.tables.training_job import TrainingJob

from model_layer.utils.build_target_timestamps import build_target_timestamps
from model_layer.utils.evaluate_predictions import evaluate_predictions
from model_layer.utils.create_jobs import matching_timestamps, create_missing_jobs
from model_layer.utils.get_enabled_runs import get_enabled_runs
from model_layer.utils.get_evaluation_dates import fetch_actuals
from model_layer.utils.get_pending_predictions import get_pending_predictions
from model_layer.utils.model_store import create_artifact_path
from model_layer.utils.get_active_model import get_active_model
from model_layer.utils.save_prediction import save_prediction
from model_layer.utils.time import floor_to_five_minutes, now_ny
from model_layer.registry import MODEL_REGISTRY

load_dotenv()

def train_model(job_id: int, attempt_count: int):
    
    MAX_ATTEMPTS = 5

    try: 
        with SessionLocal() as db: 

            result = (
                db.query(TrainingJob, ForecastRun) #type: ignore
                .join(ForecastRun, ForecastRun.id == TrainingJob.run_id)
                .filter(
                    TrainingJob.id == job_id
                )
                .one_or_none()
            )

            if result is None:
                raise ValueError(f"Training job {job_id} does not exist")
            
            job, run = result
            
            model_config = dict(run.model_config)
            training_config = dict(run.training_config)
            run_id = run.id

            scheduled_for = job.scheduled_for
            training_start = job.training_data_start
            training_cutoff = job.training_data_cutoff

        # Close db connection
        model_type = model_config["model_type"]
        ptid = model_config["ptid"]
        model_name = run.name

        model_class = MODEL_REGISTRY[model_type]
        model = model_class(name=model_name, ptid=ptid, hyperparams=model_config.get("hyperparameters", {}))

        training_days = training_config["training_window_days"]

        X, y = model.fetch_training_data(training_days, 
                                            start= training_start, 
                                            cutoff = training_cutoff)

        # train model
        model.train(X,y)

        # add metadata: time train start/stop, etc.
        completed_at = now_ny()

        version_id, artifact_path = create_artifact_path(model_name, ptid)

        # save model to joblib path and update active model table
        model.save(artifact_path,completed_at)

        with SessionLocal.begin() as db:
            db.query(ForecastRun).filter( #type: ignore
                ForecastRun.id == run_id
            ).with_for_update().one()
            
            job = (
                db.query(TrainingJob) #type: ignore
                .filter(
                    TrainingJob.id == job_id,
                    TrainingJob.run_id == run_id,
                )
                .with_for_update()
                .one()
            )

            if job.status != "running" or job.attempt_count != attempt_count:
                raise RuntimeError(f"Training jobs in race condition")

            versions = db.query(ModelVersion).filter( #type: ignore
                ModelVersion.run_id == run_id,
                ModelVersion.model_name == model_name,
                ModelVersion.ptid == ptid,
            )

            previous_version = (
                versions.filter(ModelVersion.effective_start < scheduled_for)
                .order_by(ModelVersion.effective_start.desc())
                .first()
            )

            next_version = (
                versions.filter(ModelVersion.effective_start > scheduled_for)
                .order_by(ModelVersion.effective_start.asc())
                .first()
            )

            if previous_version is not None:
                previous_version.effective_end = scheduled_for

            db.add(
                ModelVersion(
                    version_id=str(version_id),
                    run_id=run_id,
                    training_job_id=job_id,
                    model_type=model_type,
                    model_name=model_name,
                    ptid=ptid,
                    artifact_path=str(artifact_path),
                    trained_at=completed_at,
                    effective_start=scheduled_for,
                    effective_end=(
                        next_version.effective_start
                        if next_version is not None
                        else None
                    ),
                )
            )

            job.status = "succeeded"
            job.completed_at = now_ny()
            job.next_attempt_at = None
            job.last_error = None

    except Exception as exc:
        failed_at = now_ny()
        exhausted = attempt_count >= MAX_ATTEMPTS

        with SessionLocal.begin() as db:
            db.execute(
                update(TrainingJob)
                .where(
                    TrainingJob.id == job_id,
                    TrainingJob.status == "running",
                    TrainingJob.attempt_count == attempt_count,
                )
                .values(
                    status="failed" if exhausted else "retryable",
                    last_error=str(exc),
                    next_attempt_at = (
                        None if exhausted
                        else failed_at+timedelta(minutes=5)
                    ),
                    completed_at = (
                        None if not exhausted
                        else failed_at
                    )
                )
                .execution_options(synchronize_session=False)
            )
        
        raise


def predict_model(config: dict):
    start_time_floor = floor_to_five_minutes(now_ny())

    model_type = config["model_type"]
    ptid = config["ptid"]
    model_name = config["name"]

    active_model = get_active_model(model_name=model_name,ptid=ptid)

    if active_model is None:
        raise RuntimeError(
            f"No active model for {model_name}, PTID {ptid}"
        )
    
    active_artifact, active_model_version_id = active_model

    model_class = MODEL_REGISTRY[model_type]
    model = model_class(name=model_name, ptid=ptid, hyperparams={})

    model.load(active_artifact)

    interval_minutes = config["interval_minutes"]
    forecast_intervals = config["forecast_intervals"]

    target_timestamps = build_target_timestamps(start_time_floor, interval_minutes, forecast_intervals)

    # generate features if needed
    features = model.prepare_prediction_features(target_timestamps)

    # make predictions
    predictions = model.predict(target_timestamps, features)
    
    # validate predictions
    if len(predictions) != len(target_timestamps):
        raise ValueError(
            "Model returned a different number of predictions "
            "than requested target timestamps"
        )

    if not predictions.index.equals(target_timestamps):
        raise ValueError(
            "Prediction index does not match target timestamps"
        )

    if predictions.isna().any():
        raise ValueError("Model returned missing predictions")

    # record time of predictions
    issued_at = now_ny()

    # save predictions
    save_prediction(version_id=active_model_version_id,
                    model_name=model_name,
                    ptid=ptid,
                    issued_at=issued_at,
                    target_timestamps=target_timestamps, #type: ignore
                    predicted_lbmps=predictions) #type: ignore

def update_model():
    pass



def ingest_lbmp_zonal():
    base_url = os.getenv(
            "NYISO_API_BASE_URL",
            "http://nyiso-api:5050",
    ).rstrip("/")
    url = f"{base_url}/lbmp/real-time/zonal"

    today_start = now_ny().replace(
    hour=0,
    minute=0,
    second=0,
    microsecond=0,
)

    today = today_start.isoformat(timespec="seconds")

    response = requests.post(
        url,
        json={
            "start": today,
            "end": today,
        },
        timeout=120,
    )
    response.raise_for_status()

    return response.json()

def create_jobs(horizon: timedelta):
    now = now_ny()
    generate_to = now+horizon

    for run in get_enabled_runs():
        window_start = max(now, run.start_timestamp)
        window_end = min(generate_to, run.end_timestamp) if run.end_timestamp else generate_to

        for job_type in ("training", "prediction"):
            
            if job_type == "training":
                trigger = run.training_config["trigger"]
            else:
                trigger = run.prediction_config["trigger"]

            new_slots = matching_timestamps(
                trigger,
                start=window_start,
                end=window_end
            )

            if new_slots:
                with SessionLocal.begin() as db:
                    for scheduled_for in new_slots:
                        create_missing_jobs(db, run, job_type, scheduled_for)