import argparse
import yaml
from datetime import timedelta

from celery.schedules import crontab
from sqlalchemy.orm import Session

from model_layer.db.database import SessionLocal
from model_layer.db.tables.forecast_run import ForecastRun

def find_run_by_name(db: Session, name: str) -> ForecastRun | None:
    return (
        db.query(ForecastRun) #type: ignore
        .filter(ForecastRun.name == name)
        .one_or_none()
    )

def initialize_forecast_runs(forecast_run_path):

    with open(forecast_run_path) as f:
        config = yaml.safe_load(f)
    
    rows = []
    with SessionLocal.begin() as db:
        for forecast_run in config["forecast_runs"]:
            
            # Check if run exists and is enabled
            existing_run = find_run_by_name(db, forecast_run["name"])

            if existing_run is not None:
                existing_run.enabled = forecast_run["enabled"]
                continue

            if not forecast_run["enabled"]:
                continue 
            
            values = {
                    "name": forecast_run["name"],
                    "mode": forecast_run["mode"],

                    "end_timestamp": forecast_run.get("end_timestamp"),

                    "model_config": forecast_run["model_config"],
                    "training_config": forecast_run["training_config"],
                    "prediction_config": forecast_run["prediction_config"]
                }

            if forecast_run.get("start_timestamp") is not None:
                values["start_timestamp"] = forecast_run["start_timestamp"]
            
            db.add(ForecastRun(**values))

        
            
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("forecast_runs_path")
    args = parser.parse_args()

    initialize_forecast_runs(args.forecast_runs_path)  # You implement this function.

if __name__ == "__main__":
    main()