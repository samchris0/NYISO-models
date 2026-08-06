import numpy as np
import pandas as pd

from datetime import datetime, time, timedelta

from api_client import get_real_time_lbmp_zonal
from base import BaseModel

class SeasonalNaive(BaseModel):
    name = "seasonal_naive"

    def __init__(self, ptid: int, hyperparams: dict):
        self.ptid = ptid
        self.hyperparams = hyperparams
        self.model = None

    def fetch_training_data(self, training_window_days):
        self.training_window_days = training_window_days
        
        stop_time = datetime.combine(datetime.today(), time.min)
        start_time = stop_time-timedelta(days=training_window_days)

        data = get_real_time_lbmp_zonal(start_time,stop_time,self.ptid)

        self.X = data["timestamp"]
        self.y = data["lbmp"]

        return self.X, self.y
    
    def train(self, X=None, y=None):
        seasonal_period = self.training_window_days*288 #number of days times 288 for 5 min intervals

        if X is None:
            X = self.X
        if y is None:
            y = self.y

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

