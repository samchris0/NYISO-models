from sqlalchemy import exists, or_, update

from model_layer.db.database import SessionLocal
from model_layer.db.tables.forecast_run import ForecastRun
from model_layer.db.tables.model_version import ModelVersion
from model_layer.db.tables.prediction_job import PredictionJob
from model_layer.db.tables.training_job import TrainingJob
from model_layer.utils.time import now_ny

def claim_training_job(job_id: int) -> int | None:
    now = now_ny()

    run_is_eligible = exists().where(
        ForecastRun.id == TrainingJob.run_id,
        ForecastRun.enabled.is_(True),
        ForecastRun.status == "running"
    )

    statement = (
        update(TrainingJob)
        .where(
            TrainingJob.id == job_id,
            TrainingJob.status.in_(["pending","retryable"]),
            TrainingJob.scheduled_for <= now,
            or_(
                TrainingJob.next_attempt_at.is_(None),
                TrainingJob.next_attempt_at <= now
            ),
            run_is_eligible,
        )
        .values(
            status = "running",
            started_at = now,
            completed_at = None,
            next_attempt_at = None,
            attempt_count = TrainingJob.attempt_count + 1,
        )
        .returning(TrainingJob.attempt_count)
        .execution_options(synchronize_session=False)
    )

    with SessionLocal.begin() as db:
        attempt_count = db.execute(statement).scalar_one_or_none()
    
    return attempt_count

def claim_predicting_job(job_id: int):
    now = now_ny()

    run_is_eligible = exists().where(
        ForecastRun.id == PredictionJob.run_id,
        ForecastRun.enabled.is_(True),
        ForecastRun.status == "running"
    )

    statement = (
        update(PredictionJob)
        .where(
            PredictionJob.id == job_id,
            PredictionJob.status.in_(["pending","retryable"]),
            PredictionJob.scheduled_for <= now,
            or_(
                PredictionJob.next_attempt_at.is_(None),
                PredictionJob.next_attempt_at <= now
            ),
            run_is_eligible,
        )
        .values(
            status = "running",
            started_at = now,
            completed_at = None,
            next_attempt_at = None,
            attempt_count = PredictionJob.attempt_count + 1,
        )
        .returning(PredictionJob.attempt_count)
        .execution_options(synchronize_session=False)
    )

    with SessionLocal.begin() as db:
        attempt_count = db.execute(statement).scalar_one_or_none()
    
    return attempt_count