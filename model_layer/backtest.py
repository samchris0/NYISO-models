from pathlib import Path

import pandas as pd

from sqlalchemy import or_


from model_layer.celery.jobs.train_model import train_model
from model_layer.celery.jobs.predict_model import predict_model
from model_layer.db.database import SessionLocal
from model_layer.db.tables import ForecastRun
from model_layer.db.tables import ModelVersion
from model_layer.db.tables import PredictionJob
from model_layer.init_forecasting import initialize_forecast_runs
from model_layer.utils.claim_jobs import claim_predicting_job, claim_training_job
from model_layer.utils.create_jobs import matching_timestamps, create_missing_jobs




def main():
    backtest_yaml = Path("model_layer/backtest_runs.yaml")
    initialize_forecast_runs(backtest_yaml)
    
    with SessionLocal.begin() as db:

        runs = (
            db.query(
                ForecastRun,
            ) #type: ignore
            .filter(
                ForecastRun.enabled.is_(True),
                ForecastRun.mode == 'historical',
                or_(
                    ForecastRun.status == 'pending',
                    ForecastRun.status == 'running'
                ),
            )
            .all()
        )

        for run in runs:
            run_id = run.id
            name = run.name
            start = run.start_timestamp
            stop = run.end_timestamp
            model_config = run.model_config 
            training_config = run.training_config 
            prediction_config = run.prediction_config
            current_version_id = None

            prediction_events = matching_timestamps(prediction_config["trigger"], start, stop)
            training_events = matching_timestamps(training_config["trigger"], start, stop)

            if not prediction_events or not training_events:
                continue
            
            events =[{"type":"prediction",
                        "timestamp":time} for time in prediction_events]
            
            events.extend(
                [{"type":"training",
                "timestamp":time} for time in training_events]
            )

            df = pd.DataFrame(events)
            
            type_order = ['training', 'prediction']
            df["type"] = pd.Categorical(
                df['type'], 
                categories=type_order, 
                ordered=True
            )
            df = df.sort_values(by=['timestamp', 'type'], ascending=[True, True])

            for event in df.itertuples(index=False, name=None):
                timestamp = event.timestamp
                event_type = event.type
                
                with SessionLocal.begin() as job_db:
                    
                    if type == "training":
                        jobs = create_missing_jobs(job_db,run,"training",timestamp)
                        
                        for job_id in jobs:
                            attempt_count = claim_training_job(job_id)
                            train_model(job_id,attempt_count)

                            current_version_id = (
                                job_db.query(ModelVersion.version_id) #type: ignore
                                .filter(ModelVersion.training_job_id == job_id)
                                .scalar()
                            )

                            if current_version_id is None:
                                raise RuntimeError(
                                    f"Training job {job_id} did not register a model version"
                                )
                    elif type == "prediction":
                        if current_version_id is None:
                            raise RuntimeError(f"No active model version")
                        
                        jobs = create_missing_jobs(job_db,run,"prediction",timestamp)

                        for job_id in jobs:
                            
                            job = (
                                job_db.query(PredictionJob) #type: ignore
                                .filter(PredictionJob.id == job_id)
                                .one()
                            )
                            
                            job.version_id = current_version_id

                        for job_id in jobs:
                            attempt_count = claim_predicting_job(job_id)
                            
                            if attempt_count is None:
                                raise RuntimeError(f"Could not claim prediction job {job_id}")
                            
                            predict_model(job_id,attempt_count)



if __name__ == "__main__":
    main()