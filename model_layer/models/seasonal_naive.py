from datetime import datetime, time, timedelta

import joblib
import numpy as np
import pandas as pd
from pathlib import Path

from model_layer.api_client import get_real_time_lbmp_zonal
from model_layer.models.base import BaseModel

class SeasonalNaive(BaseModel):
    type = "seasonal_naive"

    def fetch_training_data(self, training_window_days):
        self.training_window_days = training_window_days
        
        stop_time = datetime.combine(datetime.today(), time.min)
        start_time = stop_time-timedelta(days=training_window_days)

        data = get_real_time_lbmp_zonal(start_time,stop_time,self.ptid)

        X = data["timestamp"]
        y = data["lbmp"]

        return X, y
    
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

    def predict(self, input_datetime):
        "input_datetimes should be the target timestamp here"

        if self.model is None:
            raise RuntimeError(
                "SeasonalNaive has not been trained. Call train() or load() first."
            )
        
        seasonal_period = self.model["seasonal_period"]
        history = self.model["history"]

        source_timestamp = input_datetime - timedelta(days=seasonal_period/288)
        if source_timestamp in history.index:
            values = history.loc[source_timestamp].to_numpy()
            return values
        else:
            raise RuntimeError(
                "Incorrect time index provided to model for prediction"
            )
        
        

