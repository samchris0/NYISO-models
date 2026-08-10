"""Client functions used by the model layer to read data from nyiso-api."""

import os
from datetime import datetime

import pandas as pd
import requests


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
        "start": start.strftime("%Y-%m-%d %H:%M:%S"),
        "end": end.strftime("%Y-%m-%d %H:%M:%S"),
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

    # The current API stores and returns naive NYISO timestamps, so preserve
    # that convention rather than incorrectly labelling them as UTC.
    data["timestamp"] = pd.to_datetime(data["timestamp"])
    return data.sort_values("timestamp").reset_index(drop=True)
