from datetime import datetime

import pandas as pd
from sqlalchemy.dialects.postgresql import insert

from model_layer.db.tables.prediction_job import PredictionJob
from model_layer.db.database import SessionLocal
from model_layer.db.tables.prediction import Prediction
from model_layer.utils.time import as_ny_datetime, now_ny

def save_prediction(version_id: str,
                    model_name: str,
                    ptid: int,
                    issued_at: datetime,
                    target_timestamps: pd.DatetimeIndex,
                    predicted_lbmps: pd.Series,
                    job_id: int,
                    run_id: int,
                    attempt_count: int):
    
    rows = [
        {
            "version_id": version_id,
            "model_name": model_name,
            "ptid": ptid,
            "issued_at": as_ny_datetime(issued_at),
            "target_timestamp": as_ny_datetime(target_timestamp.to_pydatetime()),
            "predicted_lbmp": float(predicted_lbmp),
            "job_id":job_id
        }
        for target_timestamp, predicted_lbmp in zip(
            target_timestamps,
            predicted_lbmps,
        )
    ]

    if not rows:
        return

    statement = (
        insert(Prediction)
        .values(rows)
        .on_conflict_do_nothing(
            constraint="uq_prediction_identity",
        )
    )

    with SessionLocal.begin() as db:
        
        job = (
            db.query(PredictionJob) #type: ignore
            .filter(
                PredictionJob.id == job_id,
                PredictionJob.run_id == run_id,
            )
            .with_for_update()
            .one()
        )

        if (
            job.status != "running"
            or job.attempt_count != attempt_count
        ):
            raise RuntimeError("This attempt no longer owns the job")
        
        if job.version_id != version_id:
            raise RuntimeError("Prediction version differs from the assigned version")
        db.execute(statement)
        
        job.status = "succeeded"
        job.completed_at = now_ny()
        job.next_attempt_at = None
        job.last_error = None