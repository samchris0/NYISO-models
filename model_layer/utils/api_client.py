"""Client functions used by the model layer to read data from nyiso-api."""

import os
from datetime import datetime, timedelta, time

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
    data = []

    current = as_ny_datetime(start)
    last_date = as_ny_datetime(end)

    if current > last_date:
        raise ValueError("start must be on or before end")

    while True:
        
        next_month = current + timedelta(days=30)
        chunk_end = min(last_date, next_month)

        params = {
            # Preserve the New York UTC offset at the HTTP boundary.
            "start": current.isoformat(),
            "end": chunk_end.isoformat(),
            "ptid": str(ptid),
        }

        response = requests.get(url, params=params, timeout=timeout_seconds)
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError(f"Expected a list from {url}; received {payload!r}")

        new_data = pd.DataFrame(payload)
        data.append(new_data)

        if chunk_end == last_date:
            break

        current = chunk_end 

    data = pd.concat(data, ignore_index=True)

    if data.empty:
        return data

    timestamps = pd.to_datetime(
    data["timestamp"],
    utc=True,
)

    data["timestamp"] = timestamps.dt.tz_convert(
        NYISO_TIMEZONE
    )
   
    return (
        data.drop_duplicates(subset=["timestamp"])
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

def ingest_real_time_lbmp_zonal(    
    start: datetime,
    end: datetime,
    *,
    timeout_seconds: int = 60,
    ):

    base_url = os.getenv("NYISO_API_BASE_URL", NYISO_API_BASE_URL).rstrip("/")
    url = f"{base_url}/lbmp/real-time/zonal"

    current = as_ny_datetime(start).date()
    last_date = as_ny_datetime(end).date()

    if current > last_date:
        raise ValueError("start must be on or before end")

    while current <= last_date:
        next_month = (current.replace(day=1) + timedelta(days=32)).replace(day=1)
        chunk_end = min(last_date, next_month - timedelta(days=1))

        payload = {
            "start": datetime.combine(
                current, time.min, tzinfo=NYISO_TIMEZONE
            ).isoformat(),
            "end": datetime.combine(
                chunk_end, time.min, tzinfo=NYISO_TIMEZONE
            ).isoformat()
        }

        response = requests.post(
            url,
            json=payload,
            timeout=timeout_seconds,
        )
        response.raise_for_status()

        current = chunk_end + timedelta(days=1)