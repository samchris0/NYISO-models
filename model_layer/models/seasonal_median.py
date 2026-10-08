from datetime import datetime, time, timedelta

import joblib
import numpy as np
import pandas as pd
from pathlib import Path

from model_layer.utils.api_client import get_real_time_lbmp_zonal
from model_layer.models.base import BaseModel
from model_layer.utils.time import now_ny

class SeasonalMedian(BaseModel):
    type = "seasonal_median"

    def train(self,X,y):
        
        data = pd.DataFrame({
            "timestamp": X,
            "lbmp": y.to_numpy(dtype=float),
        })

        data["slot"] = (
            data["timestamp"]
            .dt.tz_convert("UTC")
            .dt.round("5min")
            .dt.tz_convert("America/New_York")
        )

    
        prices = data.groupby("slot", as_index=False)["lbmp"].mean()

        prices["time"] = prices["slot"].dt.time
        prices["weekend"] = prices["slot"].dt.weekday.isin([5, 6])
        
        seasonal_medians = prices.groupby(["time","weekend"])["lbmp"].median()

        lookup_table = seasonal_medians.to_dict()

        self.model = {
            "frequency":"5min",
            "trained_through": data["timestamp"].max(),
            "lookup_table": lookup_table
        }

    def predict(self, target_timestamps: pd.DatetimeIndex,
                features: pd.DataFrame | None = None) -> pd.Series:

        if self.model is None:
            raise RuntimeError("Model has not been trained or loaded")

        if target_timestamps.tz is None:
            raise ValueError("Target timestamps must be timezone-aware")

        slots = (
            target_timestamps
            .tz_convert("UTC")
            .round("5min")
            .tz_convert("America/New_York")
        )

        lookup = self.model["lookup_table"]
        predictions = []

        for slot in slots:
            key = (slot.time(), slot.weekday() >= 5)

            if key not in lookup:
                raise ValueError(
                    f"No seasonal median for time={key[0]}, "
                    f"weekend={key[1]}"
                )

            predictions.append(lookup[key])

        return pd.Series(
            predictions,
            index=target_timestamps,
            name="predicted_lbmp",
            dtype=float,
        )