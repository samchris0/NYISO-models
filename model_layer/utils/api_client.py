"""Client functions used by the model layer to read data from nyiso-api."""

import os
from datetime import datetime

import pandas as pd
import requests

from model_layer.utils.time import NYISO_TIMEZONE, as_ny_datetime


NYISO_API_BASE_URL="http://nyiso-api:5000"


def get_real_time_lbmp_zonal(
    start: datetime,
    end: datetime,
    ptid: int,
    *,
    timeout_seconds: int = 30,
) -> pd.DataFrame:
    """Return real-time zonal LBMP observations for one PTID."""

    base_url = os.getenv("NYISO_API_BASE_URL", NYISO_API_BASE_URL).rstrip("/")
    url = f"{base_url}/lbmp/real-time/zonal"

    params = {
        # Preserve the New York UTC offset at the HTTP boundary.
        "start": as_ny_datetime(start).isoformat(timespec="seconds"),
        "end": as_ny_datetime(end).isoformat(timespec="seconds"),
        "ptid": str(ptid),
    }

    response = requests.get(url, params=params, timeout=timeout_seconds)
    response.raise_for_status()

    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError(f"Expected a list from {url}; received {payload!r}")

    data = pd.DataFrame(payload)
    if data.empty:
        return data

    timestamps = pd.to_datetime(
    data["timestamp"],
    utc=True,
)

    data["timestamp"] = timestamps.dt.tz_convert(
        NYISO_TIMEZONE
    )
   
    return data.sort_values("timestamp").reset_index(drop=True)
