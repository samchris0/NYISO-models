from sqlalchemy import Column, String, Float, DateTime, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func

from model_layer.db.database import Base

class Prediction(Base):
    __tablename__ = "prediction"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("prediction_job.id"), nullable=False)

    version_id = Column(String, ForeignKey("model_version.version_id"), nullable=False)
    model_name = Column(String, nullable=False)
    ptid = Column(Integer, nullable=False)

    issued_at = Column(DateTime(timezone=True), nullable=False)
    target_timestamp = Column(DateTime(timezone=True), nullable=False)
    predicted_lbmp = Column(Float, nullable=False)

    actual_lbmp = Column(Float, nullable=True)
    evaluated_at = Column(DateTime(timezone=True), nullable=True)
    absolute_error = Column(Float, nullable=True)
    squared_error = Column(Float, nullable=True)

    evaluation_attempts = Column(Integer, nullable=False, default=0)
    next_evaluation_attempt = Column(DateTime(timezone=True), nullable=False, default = func.now())

    __table_args__ = (
        UniqueConstraint(
            "job_id",
            name="uq_prediction_identity",
        ),
    )
