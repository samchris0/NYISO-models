from datetime import datetime

from model_layer.db.database import SessionLocal
from model_layer.db.tables.prediction import Prediction
from model_layer.utils.time import now_ny

def get_pending_predictions(available_before: datetime, limit: int) -> list[Prediction]:
    now = now_ny()
    
    with SessionLocal() as db:
        query = (
            db.query(Prediction) #type: ignore
            .filter(
                Prediction.target_timestamp < available_before,
                Prediction.evaluated_at.is_(None),
                Prediction.evaluation_attempts < 5,
                Prediction.next_evaluation_attempt < now,
            )
            .order_by(Prediction.target_timestamp)
            .limit(limit)
            .all()
        )

        return query