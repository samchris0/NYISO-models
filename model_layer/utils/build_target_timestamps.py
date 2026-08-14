from datetime import datetime

import pandas as pd

from model_layer.utils.time import as_ny_datetime

def build_target_timestamps(start_time_floor: datetime, interval_minutes: int, forecast_intervals: int):
    start_time_floor = as_ny_datetime(start_time_floor)
    target_timestamps = pd.date_range(start=start_time_floor+pd.Timedelta(minutes=interval_minutes),
                                      periods=forecast_intervals, 
                                      freq=pd.Timedelta(minutes=interval_minutes))
    
    return target_timestamps
