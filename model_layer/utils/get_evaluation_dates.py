from collections import defaultdict
from datetime import date, datetime

from model_layer.db.tables.prediction import Prediction
from model_layer.utils.api_client import get_real_time_lbmp_zonal
from model_layer.utils.time import as_ny_datetime

def get_evaluation_dates(pending_predictions: list[Prediction],
                         ) -> dict[tuple[int, date], list[Prediction]]:

    groups = defaultdict(list)

    for prediction in pending_predictions:
        target = as_ny_datetime(
            prediction.target_timestamp
        )

        key = (prediction.ptid, target)
        groups[key].append(prediction)

    return dict(groups)

def fetch_actuals(
        predictions: list[Prediction],
    ) -> dict[tuple[int, datetime], float]:

    groups = get_evaluation_dates(predictions)
    actuals = {}

    for (ptid, _), group in groups.items():
        
        targets = [
            as_ny_datetime(prediction.target_timestamp)
            for prediction in group
        ]

        start = min(targets)
        end = max(targets)

        data = get_real_time_lbmp_zonal(
            start=start,
            end=end,
            ptid=ptid
        )

        for row in data.itertuples():
            timestamp = row.timestamp.to_pydatetime()
            actuals[(ptid, timestamp)] = row.lbmp

    return actuals