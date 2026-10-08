from datetime import datetime, time, timedelta

import joblib
import numpy as np
import pandas as pd
from pathlib import Path

from model_layer.utils.api_client import get_real_time_lbmp_zonal
from model_layer.models.base import BaseModel
from model_layer.utils.time import now_ny

class SeasonalNaive(BaseModel):
    type = "seasonal_naive"

    def train(self, X, y):
        seasonal_period = self.training_window_days*288 #number of days times 288 for 5 min intervals

        history = pd.Series(
            data=y.to_numpy(),
            index=pd.to_datetime(X),
            name="lbmp",
        )

        history = history.sort_index()

        self.model = {
            "seasonal_period":seasonal_period,
            "frequency":"5min",
            "trained_through": X.max(),
            "history": history
        }

    def fetch_predict_input(self):
        "Not needed for naive model"
        pass

    def predict(self, target_timestamps: pd.DatetimeIndex,
        features: pd.DataFrame | None = None) -> pd.Series:

        if self.model is None:
            raise RuntimeError(
                "SeasonalNaive has not been trained. Call train() or load() first."
            )

        seasonal_period = self.model["seasonal_period"]
        history = self.model["history"]

        source_timestamps = target_timestamps - timedelta(days=seasonal_period/288)

        values = history.reindex(
            source_timestamps,
            method="ffill",
        )

        if values.isna().any():
            missing = source_timestamps[values.isna()]
            raise RuntimeError(
                f"Missing historical observations for {missing.tolist()}"
            )

        return pd.Series(
            values.to_numpy(),
            index=target_timestamps,
            name="predicted_lbmp",
        )
        