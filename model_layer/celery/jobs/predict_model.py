from datetime import timedelta
from dotenv import load_dotenv

import pandas as pd
from sqlalchemy import update, and_

from model_layer.db.database import SessionLocal
from model_layer.db.tables.forecast_run import ForecastRun
from model_layer.db.tables.model_version import ModelVersion
from model_layer.db.tables.prediction_job import PredictionJob

from model_layer.utils.time import now_ny
from model_layer.utils.save_prediction import save_prediction
from model_layer.registry import MODEL_REGISTRY

def predict_model(job_id: int, attempt_count: int):

    MAX_ATTEMPTS = 5

    try: 
        with SessionLocal() as db: 

            result = (
                db.query(PredictionJob, ForecastRun) #type: ignore
                .join(ForecastRun, ForecastRun.id == PredictionJob.run_id)
                .filter(
                    PredictionJob.id == job_id
                )
                .one_or_none()
            )

            if result is None:
                raise ValueError(f"Training job {job_id} does not exist")
            
            job, run = result
            
            model_config = dict(run.model_config)
            run_id = run.id
            model_name = run.name

            version_id = job.version_id

            target_timestamp = pd.DatetimeIndex([job.target_timestamp])

        with SessionLocal() as db:
            
            current_version = (
                db.query(ModelVersion) #type: ignore
                .filter(
                    ModelVersion.version_id == version_id,
                    ModelVersion.run_id == run_id,
                )
                .one_or_none()
            )

            if current_version:

                active_artifact = current_version.artifact_path
                version_id = current_version.version_id
            
            else:
                raise ValueError("No valid model trained for this time")
        
        model_type = model_config["model_type"]
        ptid = model_config["ptid"]

        model_class = MODEL_REGISTRY[model_type]
        model = model_class(name=model_name, ptid=ptid, hyperparams=model_config.get("hyperparameters", {}))
        
        model.load(active_artifact)
        features = model.prepare_prediction_features(target_timestamp)

        predictions = model.predict(target_timestamp, features)
    
        # validate predictions
        if len(predictions) != len(target_timestamp):
            raise ValueError(
                "Model returned a different number of predictions "
                "than requested target timestamps"
            )

        if not predictions.index.equals(target_timestamp):
            raise ValueError(
                "Prediction index does not match target timestamps"
            )

        if predictions.isna().any():
            raise ValueError("Model returned missing predictions")

        # record time of predictions
        issued_at = now_ny()

        save_prediction(version_id=version_id,
                model_name=model_name,
                ptid=ptid,
                issued_at=issued_at,
                target_timestamps=target_timestamp, #type: ignore
                predicted_lbmps=predictions,
                job_id=job_id,
                run_id=run_id,
                attempt_count=attempt_count)
        
    except Exception as exc:
        failed_at = now_ny()
        exhausted = attempt_count >= MAX_ATTEMPTS

        with SessionLocal.begin() as db:
            db.execute(
                update(PredictionJob)
                .where(
                    PredictionJob.id == job_id,
                    PredictionJob.status == "running",
                    PredictionJob.attempt_count == attempt_count,
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

