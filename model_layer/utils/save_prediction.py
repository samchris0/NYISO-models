from datetime import datetime

import pandas as pd
from sqlalchemy.dialects.postgresql import insert

from model_layer.db.database import SessionLocal
from model_layer.db.tables.prediction import Prediction
from model_layer.utils.time import as_ny_datetime

def save_prediction(version_id: str,
                    model_name: str,
                    ptid: int,
                    issued_at: datetime,
                    target_timestamps: pd.DatetimeIndex,
                    predicted_lbmps: pd.Series):
    
    rows = [
        {
            "version_id": version_id,
            "model_name": model_name,
            "ptid": ptid,
            "issued_at": as_ny_datetime(issued_at),
            "target_timestamp": as_ny_datetime(target_timestamp.to_pydatetime()),
            "predicted_lbmp": float(predicted_lbmp),
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
        db.execute(statement)
