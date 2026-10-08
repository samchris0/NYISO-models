from pathlib import Path
from datetime import timedelta

import pandas as pd

from sqlalchemy import or_

from model_layer.celery.jobs.train_model import train_model
from model_layer.celery.jobs.predict_model import predict_model
from model_layer.db.database import SessionLocal
from model_layer.db.tables import ForecastRun
from model_layer.db.tables import ModelVersion
from model_layer.db.tables import Prediction
from model_layer.db.tables import PredictionJob
from model_layer.db.tables import TrainingJob
from model_layer.init_forecasting import initialize_forecast_runs
from model_layer.utils.api_client import ingest_real_time_lbmp_zonal
from model_layer.utils.claim_jobs import claim_predicting_job, claim_training_job
from model_layer.utils.create_jobs import matching_timestamps, create_missing_jobs
from model_layer.utils.get_evaluation_dates import fetch_actuals
from model_layer.utils.evaluate_predictions import evaluate_predictions

def main():
    backtest_yaml = Path("model_layer/backtest_runs.yaml")
    initialize_forecast_runs(backtest_yaml)
    
    with SessionLocal.begin() as db:

        rows = (
            db.query(ForecastRun.id) #type: ignore
            .filter(
                ForecastRun.enabled.is_(True),
                ForecastRun.mode == "historical",
                ForecastRun.status.in_(["pending", "running"]),
            )
            .all()
        )
        run_ids = [run_id for (run_id,) in rows]
    
    for run_id in run_ids:
        
        with SessionLocal.begin() as db:
            run = (
                db.query(ForecastRun) #type: ignore
                .filter(ForecastRun.id == run_id)
                .one()
            )

            run.status = "running"
            
            run_id = run.id
            start = run.start_timestamp
            stop = run.end_timestamp
            training_config = dict(run.training_config)
            prediction_config = dict(run.prediction_config)
            current_version_id = None

        ingest_real_time_lbmp_zonal(
            start=start-timedelta(days=training_config["training_window_days"]),
            end = stop+timedelta(minutes=
                                 prediction_config["target_step_minutes"]*prediction_config["forecast_intervals"]),
        )

        prediction_events = matching_timestamps(prediction_config["trigger"], start, stop)
        training_events = matching_timestamps(training_config["trigger"], start, stop)

        if not prediction_events or not training_events:
            continue
        
        events =[{"event_type":"prediction",
                    "timestamp":time} for time in prediction_events]
        
        events.extend(
            [{"event_type":"training",
            "timestamp":time} for time in training_events]
        )

        df = pd.DataFrame(events)
        
        type_order = ['training', 'prediction']
        df["event_type"] = pd.Categorical(
            df['event_type'], 
            categories=type_order, 
            ordered=True
        )
        df = df.sort_values(by=['timestamp', 'event_type'], ascending=[True, True])

        for event in df.itertuples(index=False):
            timestamp = event.timestamp
            event_type = event.event_type

            if event_type == "training":
                with SessionLocal.begin() as job_db:
                    run = (
                        job_db.query(ForecastRun) #type:ignore
                        .filter(ForecastRun.id == run_id)
                        .one()
                    )

                    jobs = create_missing_jobs(job_db,run,"training",timestamp)

                    job = (
                        job_db.query(TrainingJob) #type: ignore
                        .filter(
                            TrainingJob.run_id == run_id,
                            TrainingJob.scheduled_for == timestamp,
                        )
                        .one()
                    )

                    job_id = job.id
                    job_status = job.status

                if job_status != "succeeded":
                    attempt_count = claim_training_job(job_id)
                    
                    if attempt_count is None:
                        raise RuntimeError(
                            f"Could not claim training job {job_id}"
                        )
                    
                    train_model(job_id,attempt_count)

                with SessionLocal() as version_db:
                    current_version_id = (
                        version_db.query(ModelVersion.version_id) #type ignore
                        .filter(ModelVersion.training_job_id == job_id) #type: ignore
                        .scalar()
                    )

                if current_version_id is None:
                    raise RuntimeError(
                        f"Training job {job_id} has no model version"
                    )
                    
            elif event_type == "prediction":
                if current_version_id is None:
                    raise RuntimeError(f"No active model version")

                job_ids_to_do = []

                with SessionLocal.begin() as job_db:
                
                    run = (
                        job_db.query(ForecastRun) #type: ignore
                        .filter(ForecastRun.id == run_id)
                        .one()
                    )

                    jobs = create_missing_jobs(job_db,run,"prediction",timestamp)

                    jobs = (
                        job_db.query(PredictionJob) #type: ignore
                        .filter(
                            PredictionJob.run_id == run_id,
                            PredictionJob.scheduled_for == timestamp,
                        )
                        .all()
                    )

                    for job in jobs:
                        
                        if job.status == "succeeded":
                            continue

                        if job.version_id is None:
                            job.version_id = current_version_id
                        
                        job_ids_to_do.append(job.id)

                for job_id in job_ids_to_do:
                    attempt_count = claim_predicting_job(job_id)
                    
                    if attempt_count is None:
                        raise RuntimeError(f"Could not claim prediction job {job_id}")
                    
                    predict_model(job_id,attempt_count)

        evaluate_backtest(run_id)

        with SessionLocal.begin() as db:
            completed_run = (
                db.query(ForecastRun) #type: ignore
                .filter(ForecastRun.id == run_id)
                .one()
            )
            completed_run.status = "completed"


def evaluate_backtest(run_id: int) -> int:
    with SessionLocal() as db:
        predictions = (
            db.query(Prediction) #type: ignore
            .join(
                PredictionJob,
                PredictionJob.id == Prediction.job_id,
            )
            .filter(
                PredictionJob.run_id == run_id,
                PredictionJob.status == "succeeded",
                Prediction.evaluated_at.is_(None)
            )
            .order_by(Prediction.target_timestamp, Prediction.id)
            .all()
        )

        if not predictions:
            return 0

        actuals = fetch_actuals(predictions)
        evaluated_count = evaluate_predictions(actuals, predictions)

        if evaluated_count != len(predictions):
            missing_count = len(predictions) - evaluated_count
            raise RuntimeError(
                f"Run {run_id}: {missing_count} predictions could not "
                "be evaluated because actuals were missing or non-finite"                
            )
        
        return evaluated_count

if __name__ == "__main__":
    main()