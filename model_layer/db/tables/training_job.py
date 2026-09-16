from sqlalchemy import func, Column, String, DateTime, Integer, ForeignKey, UniqueConstraint, Text

from model_layer.db.database import Base

class TrainingJob(Base):
    __tablename__ = "training_job"

    id = Column(Integer, primary_key=True, autoincrement=True)

    run_id = Column(
        Integer,
        ForeignKey("forecast_run.id"),
        nullable=False,
        index=True,
    )

    scheduled_for = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    training_data_start = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    training_data_cutoff = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    """
    pending: waiting for execution.
    running: claimed by a training worker.
    retryable: temporary API, data, or database failure.
    succeeded: artifact and model-version row were created.
    failed: unrecoverable or retry limit exceeded.
    """
    status = Column(
        String,
        nullable=False,
        server_default="pending",
    )

    attempt_count = Column(
        Integer,
        nullable=False,
        server_default="0",
    )
 
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    next_attempt_at = Column(DateTime(timezone=True))
    last_error = Column(Text)

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "scheduled_for",
            name="uq_training_job_run_slot",
        ),
    )