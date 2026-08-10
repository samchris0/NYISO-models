from datetime import datetime, time, timedelta
import pandas as pd

from pmdarima.arima import AutoARIMA

from model_layer.api_client import get_real_time_lbmp_zonal
from model_layer.models.base import BaseModel

class ARIMA(BaseModel):
    name = "auto_arima"

    def fetch_training_data(self, training_window_days):
        now = datetime.now()

        # Floor to the closest 5-minute interval
        stop_time = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0)
        start_time = stop_time-timedelta(days=training_window_days)

        data = get_real_time_lbmp_zonal(start_time,stop_time,self.ptid)

        X = data["timestamp"]
        y = data["lbmp"]

        return X, y

    def train(self, X, y):

        data = pd.Series(
            data=y.to_numpy(),
            index=pd.to_datetime(X),
            name="lbmp",
        )

        data = data.sort_index()

        model = AutoARIMA(m=288, trace=True)
        self.model = model

        model.fit(y)

    def predict(self, input_datetime):
        if self.model is None:
            raise RuntimeError(
                "SeasonalNaive has not been trained. Call train() or load() first."
            )
        
        values = self.model.predict(n_periods=len(input_datetime))
        
        return values
    
    def update(self, new_time_step):
        
        data = get_real_time_lbmp_zonal(new_time_step,new_time_step,self.ptid)
        
        if not data.empty:
            new_y = data["lbmp"].to_numpy()
        else:
            raise RuntimeError(
                "No data update"
            )
        
        self.model.update(new_y) #type: ignore




        
