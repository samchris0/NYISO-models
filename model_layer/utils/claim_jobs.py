from sqlalchemy import exists, or_, update

def claim_training_job(job_id: int) -> bool:
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
        .returning(TrainingJob.id)
        .execution_options(synchronize_session=False)
    )

    with SessionLocal.begin() as db:
        claimed_id = db.execute(statement).scalar_one_or_none()
    
    return claimed_id is not None

def claim_predicting_job(job_id: int)
    now = now_ny()

    run_is_eligible = exists().where(
        ForecastRun.id == TrainingJob.run_id,
        ForecastRun.enabled.is_(True),
        ForecastRun.status == "running"
    )

    statement = (
        update(PredictingJob)
        .where(
            PredictingJob.id == job_id,
            PredictingJob.status.in_(["pending","retryable"]),
            PredictingJob.scheduled_for <= now,
            or_(
                PredictingJob.next_attempt_at.is_(None),
                PredictingJob.next_attempt_at <= now
            ),
            run_is_eligible,
        )
        .values(
            status = "running",
            started_at = now,
            completed_at = None,
            next_attempt_at = None,
            attempt_count = PredictingJob.attempt_count + 1,
        )
        .returning(PredictingJob.id)
        .execution_options(synchronize_session=False)
    )

    with SessionLocal.begin() as db:
        claimed_id = db.execute(statement).scalar_one_or_none()
    
    return claimed_id is not None