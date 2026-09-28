from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import insert

from model_layer.db.tables.forecast_run import ForecastRun
from model_layer.db.tables.model_version import ModelVersion
from model_layer.db.tables.prediction_job import PredictionJob
from model_layer.db.tables.training_job import TrainingJob
from model_layer.utils.build_target_timestamps import build_target_timestamps
from model_layer.utils.time import NYISO_TIMEZONE

def build_cron_trigger(trigger):
    
    allowed_fields = {
            "type",
            "timezone",
            "minutes",
            "hours",
            "day_of_week",
            "day_of_month",
            "month_of_year",
        }
    
    unknown_fields = set(trigger) - allowed_fields
    if unknown_fields:
        raise ValueError(
            f"Unknown trigger fields: {sorted(unknown_fields)}"
        )

    if not trigger.get("timezone"):
        raise ValueError("Trigger timezone is required")
    
    cron = CronTrigger(
        timezone=ZoneInfo(trigger["timezone"]),
        minute=trigger.get("minutes", "0"),
        hour=trigger.get("hours", "*"),
        day_of_week=trigger.get("day_of_week", "*"),
        day=trigger.get("day_of_month", "*"),
        month=trigger.get("month_of_year", "*"),
        second=0,
    )

    return cron

def next_training_slot(trigger, scheduled_for):
    cron = build_cron_trigger(trigger)

    next_slot = cron.get_next_fire_time(
        previous_fire_time=scheduled_for,
        now=scheduled_for,
    )

    if next_slot is None:
        raise ValueError("Training trigger has no future matching timestamp")
    
    return next_slot.astimezone(ZoneInfo("America/New_York"))

def matching_timestamps(trigger: dict, start: datetime, end: datetime,) -> list[datetime] | None:
    """Return matching New York timestamps within [start, end)."""

    cron = build_cron_trigger(trigger)

    start_utc = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)

    if start_utc >= end_utc:
        return []

    timestamps = []
    next_time = cron.get_next_fire_time(
        previous_fire_time=None,
        now=start_utc,
    )

    while next_time is not None:
        slot = next_time.astimezone(timezone.utc)

        if slot >= end_utc:
            break

        timestamps.append(slot.astimezone(ZoneInfo("America/New_York")))

        next_time = cron.get_next_fire_time(
            previous_fire_time=next_time,
            now=slot,
        )

    return timestamps

def create_missing_jobs(db, run, job_type, scheduled_for):
    
    scheduled_for = scheduled_for.astimezone(
        NYISO_TIMEZONE
    )

    if job_type == "training":
        training = run.training_config
        days = training["training_window_days"]

        cutoff = scheduled_for
        start = cutoff-timedelta(days=days)

        statement = (
            insert(TrainingJob)
            .values(
                run_id = run.id,
                scheduled_for = scheduled_for,
                training_data_start = start,
                training_data_cutoff = cutoff,
                status = "pending",
            )
            .on_conflict_do_nothing(
                constraint="uq_training_job_run_slot"
            )
            .returning(TrainingJob.id)
        )
    
    elif job_type =="prediction":
        model = run.model_config
        prediction = run.prediction_config

        step = prediction["target_step_minutes"]
        count = prediction["forecast_intervals"]
        
        targets = build_target_timestamps(
            start_time_floor=scheduled_for,
            interval_minutes=step,
            forecast_intervals=count,
        )

        rows = [
            {
                "run_id": run.id,
                "scheduled_for": scheduled_for,
                "target_timestamp": target.to_pydatetime(),
                "status": "pending",
            }
            for target in targets
        ]

        statement = (
            insert(PredictionJob)
            .values(rows)
            .on_conflict_do_nothing(
                constraint="uq_prediction_job_slot"
            )
            .returning(PredictionJob.id)
        )

    else:
        raise ValueError(f"Unknown job type: {job_type!r}")

    return list(db.execute(statement).scalars())
