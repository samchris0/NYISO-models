from datetime import timedelta

from model_layer.utils.evaluate_predictions import evaluate_predictions
from model_layer.utils.get_evaluation_dates import fetch_actuals
from model_layer.utils.get_pending_predictions import get_pending_predictions
from model_layer.utils.time import now_ny

def evaluate_pending_predictions(batch_size: int = 1000) -> int:
    pending_predictions = get_pending_predictions(
        available_before= now_ny() - timedelta(minutes=10),
        limit=batch_size,
    )
    
    if not pending_predictions:
        return 0

    actuals = fetch_actuals(pending_predictions)

    num_evaluated = evaluate_predictions(actuals,pending_predictions)
    
    return num_evaluated