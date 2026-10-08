from datetime import datetime, time, timedelta

import joblib
import numpy as np
import pandas as pd
from pathlib import Path

from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from model_layer.utils.api_client import get_real_time_lbmp_zonal
from model_layer.models.base import BaseModel
from model_layer.utils.time import now_ny, NYISO_TIMEZONE

class FourierRidge(BaseModel):
    type = "fourier_ridge"

    def create_fourier_features(self,X,t_anchor):

        timestamps = pd.DatetimeIndex(X).tz_convert(NYISO_TIMEZONE)
        trend = (timestamps-t_anchor).total_seconds()/86400

        daily_phase = (timestamps.hour * 60 + timestamps.minute) / 1440
        weekly_phase = (timestamps.dayofweek + daily_phase) / 7

        n_daily = self.hyperparams["daily_harmonics"]
        n_weekly = self.hyperparams["weekly_harmonics"]

        cycles = {
            'daily': {'phase': daily_phase, 'harmonics': n_daily},
            'weekly': {'phase': weekly_phase, 'harmonics': n_weekly}
        }

        X_dict = {'trend': trend}

        for name, config in cycles.items():
            phase = config["phase"]

            for h in range(1,config["harmonics"]+1):
                X_dict[f"{name}_sin_{h}"] = np.sin(2*np.pi*h*phase)
                X_dict[f"{name}_cos_{h}"] = np.cos(2*np.pi*h*phase)
        
        df = pd.DataFrame(X_dict)

        return df

    def train(self, X, y):
        alpha = self.hyperparams["alpha"]

        t_anchor = X.min()

        df = self.create_fourier_features(X, t_anchor)
        
        scaler = StandardScaler()
        df = scaler.fit_transform(df)

        model = Ridge(alpha=alpha)

        model.fit(df,y)

        self.model = {
                    "model":model,
                    "t_anchor":X.min(),
                    "scaler":scaler
        }


    def predict(self,
                target_timestamps: pd.DatetimeIndex,
                features: pd.DataFrame | None = None,
                ) -> pd.Series:
        
        if self.model is None:
            raise RuntimeError("Model has not yet been trained")

        model = self.model["model"]
        t_anchor = self.model["t_anchor"]
        scaler = self.model["scaler"]

        df = self.create_fourier_features(target_timestamps,t_anchor)
        df = scaler.transform(df)

        y = model.predict(df)

        return pd.Series(
            y,
            index=target_timestamps,
            name="predicted_lbmp",
        )
