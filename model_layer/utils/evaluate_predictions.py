from datetime import datetime

from sqlalchemy import update

from model_layer.db.database import SessionLocal
from model_layer.db.tables.prediction import Prediction
from model_layer.utils.time import now_ny


def evaluate_predictions(actuals: dict[tuple[int, datetime], float], 
                         predictions: list[Prediction]) -> int:
    evaluated_at = now_ny()
    updates = []

    for prediction in predictions:
        key = (
            prediction.ptid,
            prediction.target_timestamp,
        )
        actual = actuals.get(key)

        if actual is None:
            continue

        actual = float(actual)
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

    if not updates:
        return 0

    with SessionLocal.begin() as db:
        db.bulk_update_mappings(
            Prediction,
            updates,
        )

    return len(updates)