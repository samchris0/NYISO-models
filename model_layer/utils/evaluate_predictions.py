from datetime import datetime, timedelta
import math

from sqlalchemy import update

from model_layer.db.database import SessionLocal
from model_layer.db.tables.prediction import Prediction
from model_layer.utils.time import now_ny


def evaluate_predictions(actuals: dict[tuple[int, datetime], float], 
                         predictions: list[Prediction]) -> int:
    evaluated_at = now_ny()
    updates = []
    update_count = 0

    for prediction in predictions:
        key = (
            prediction.ptid,
            prediction.target_timestamp,
        )
        actual = actuals.get(key)

        if actual is None or not math.isfinite(float(actual)):
            updates.append(
                {
                    "id": prediction.id,
                    "evaluation_attempts": prediction.evaluation_attempts+1,
                    "next_evaluation_attempt": (
                        evaluated_at+timedelta(minutes=20)
                    ),
                }
            )
            continue            

        actual = float(actual) #type: ignore
        predicted = float(prediction.predicted_lbmp)
        error = actual - predicted

        updates.append(
            {
                "id": prediction.id,
                "actual_lbmp": actual,
                "evaluated_at": evaluated_at,
                "absolute_error": abs(error),
                "squared_error": error**2,
            }
        )
        update_count+=1

    if not updates:
        return 0

    with SessionLocal.begin() as db:
        db.bulk_update_mappings(
            Prediction,
            updates,
        )

    return update_count