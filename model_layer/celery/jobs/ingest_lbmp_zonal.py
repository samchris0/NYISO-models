import os
import requests
from dotenv import load_dotenv

from model_layer.utils.time import now_ny

load_dotenv()

def ingest_lbmp_zonal():
    base_url = os.getenv(
            "NYISO_API_BASE_URL",
            "http://nyiso-api:5050",
    ).rstrip("/")
    url = f"{base_url}/lbmp/real-time/zonal"

    today_start = now_ny().replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    today = today_start.isoformat(timespec="seconds")

    response = requests.post(
        url,
        json={
            "start": today,
            "end": today,
        },
        timeout=120,
    )
    response.raise_for_status()

    return response.json()