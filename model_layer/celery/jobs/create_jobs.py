from datetime import datetime, timedelta
from dotenv import load_dotenv

from model_layer.db.database import SessionLocal

from model_layer.utils.create_jobs import matching_timestamps, create_missing_jobs
from model_layer.utils.get_enabled_runs import get_enabled_runs

from model_layer.utils.time import now_ny

load_dotenv()

def create_jobs(horizon: timedelta):
    now = now_ny()
    generate_to = now+horizon

    for run in get_enabled_runs():
        window_start = max(now, run.start_timestamp)
        window_end = min(generate_to, run.end_timestamp) if run.end_timestamp else generate_to

        for job_type in ("training", "prediction"):
            
            if job_type == "training":
                trigger = run.training_config["trigger"]
            else:
                trigger = run.prediction_config["trigger"]

            new_slots = matching_timestamps(
                trigger,
                start=window_start,
                end=window_end
            )

            if new_slots:
                with SessionLocal.begin() as db:
                    for scheduled_for in new_slots:
                        create_missing_jobs(db, run, job_type, scheduled_for)