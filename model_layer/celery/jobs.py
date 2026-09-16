import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

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

def train_model(job_id: int):
    
    with LocalSession() as db: 

        statement = (
            db.query(TrainingJob)
            .join(ForecastRun, ForecastRun.id == TrainingJob.run_id)
            .filter(
                TrainingJob.id == job_id
            )
            .one_or_none()
        )

        job = db.execute(statement)
    
    if job:
        
        model_config = job["model_config"]

        model_type = model_config["model_type"]
        ptid = model_config["ptid"]
        model_name = job["name"]

        model_class = MODEL_REGISTRY[model_type]
        model = model_class(name=model_name, ptid=ptid, hyperparams=model_config.get("hyperparameters", {}))

        training_days = job["training"].get("training_window_days")

        try:
            X, y = model.fetch_training_data(training_days)

            # train model
            model.train(X,y)

            # add metadata: time train start/stop, etc.
            completed_at = now_ny()

            version, artifact_path = create_artifact_path(model_name, ptid)

            # save model to joblib path and update active model table
            model.save(artifact_path,version,trained_at)

            training_job_statement = (
                update(TrainingJob)
                .where(
                    TrainingJob.id == job_id,
                )
                .values(
                    status = "succeeded",
                    completed_at = completed_at,
                )
            )

            model_version_statement = (
                insert(ModelVersion)
                .values(
                    status = "succeeded",
                    completed_at = completed_at,
                )
            )



        except error:


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

def evaluate_pending_predictions(batch_size: int = 1000) -> int:
    pending_predictions = get_pending_predictions(
        available_before=now_ny() - timedelta(minutes=10),
        limit=batch_size,
    )

    if not pending_predictions:
        return 0

    actuals = fetch_actuals(pending_predictions)

    num_evaluated = evaluate_predictions(actuals,pending_predictions)
    
    return num_evaluated

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
            trigger = run.configuration[job_type]["trigger"]

            new_slots = matching_timestamps(
                trigger,
                start=window_start,
                end=window_end
            )

            for scheduled_for in new_slots:
                create_missing_jobs(run, job_type, scheduled_for)