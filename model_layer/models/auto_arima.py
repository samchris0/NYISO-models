from datetime import datetime, time, timedelta
import pandas as pd

from pmdarima.arima import AutoARIMA

from model_layer.utils.api_client import get_real_time_lbmp_zonal
from model_layer.models.base import BaseModel
from model_layer.utils.time import floor_to_five_minutes, now_ny

class ARIMA(BaseModel):
    type = "auto_arima"

    def train(self, X, y):
        period = self.hyperparams.get("period_days",1)*288
        data = pd.Series(
            data=y.to_numpy(),
            index=pd.to_datetime(X),
            name="lbmp",
        )

        data = data.sort_index()

        model = AutoARIMA(m=period, trace=True)
        self.model = model

        model.fit(y)

    def predict(
        self,
        target_timestamps: pd.DatetimeIndex,
        features: pd.DataFrame | None = None,
    ) -> pd.Series:
        if self.model is None:
            raise RuntimeError(
                "SeasonalNaive has not been trained. Call train() or load() first."
            )
        
        values = self.model.predict(
            n_periods=len(target_timestamps),
        )

        return pd.Series(
            values,
            index=target_timestamps,
            name="predicted_lbmp",
        )
    
    def update(self, new_time_step):
        
        data = get_real_time_lbmp_zonal(new_time_step,new_time_step,self.ptid)
        
        if not data.empty:
            new_y = data["lbmp"].to_numpy()
        else:
            raise RuntimeError(
                "No data update"
            )
        
        self.model.update(new_y) #type: ignore




        
