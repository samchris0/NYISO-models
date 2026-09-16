from sqlalchemy import func, Column, String, DateTime, Integer, ForeignKey, UniqueConstraint, Text

from model_layer.db.database import Base

class PredictionJob(Base):
    __tablename__ = "prediction_job"

    id = Column(Integer, primary_key=True, autoincrement=True)

    run_id = Column(
        Integer,
        ForeignKey("forecast_run.id"),
        nullable=False,
        index=True,
    )

    version_id = Column(
        String,
        ForeignKey("model_version.version_id"),
        nullable=True,
    )

    # Time at which the model should run to make the next forecast
    scheduled_for = Column(DateTime(timezone=True), nullable=False)

    # Target forecast timestamp
    target_timestamp = Column(DateTime(timezone=True), nullable=False)

    """
    Status definitions
    pending: created and waiting for a worker.
    running: claimed by a worker.
    retryable: temporary failure; another attempt is allowed.
    succeeded: prediction was saved.
    late: the operational deadline passed without an on-time prediction, late predicton generated.
    failed: permanent failure or retry limit exceeded.
    """
    status = Column(
        String,
        nullable=False,
        server_default="pending",
    )

    # time when dispatcher creates job
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Time when worker picks up job
    started_at = Column(DateTime(timezone=True))

    # Time when succeeded, late, or failed achieved
    completed_at = Column(DateTime(timezone=True))

    attempt_count = Column(
        Integer,
        nullable=False,
        server_default="0",
    )

    next_attempt_at = Column(DateTime(timezone=True))
    last_error = Column(Text)

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "scheduled_for",
            "target_timestamp",
            name="uq_prediction_job_slot",
        ),
)
