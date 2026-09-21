from datetime import datetime

from model_layer.db.database import SessionLocal
from model_layer.db.tables.forecast_run import ForecastRun

def get_enabled_runs() -> list[ForecastRun]:
    with SessionLocal() as db:
        query = (
            db.query(ForecastRun) #type: ignore
            .filter(
                ForecastRun.enabled.is_(True),
                ForecastRun.status == "running",
            )
            .all()
        )

        return query