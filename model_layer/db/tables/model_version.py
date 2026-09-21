from sqlalchemy import Column, String, Float, DateTime, Integer, Boolean, Index, ForeignKey
from sqlalchemy.sql import func

from model_layer.db.database import Base

class ModelVersion(Base):
    __tablename__ = "model_version"

    version_id = Column(String, primary_key=True)
    
    run_id = Column(
        Integer,
        ForeignKey("forecast_run.id"),
        nullable=False,
        index=True,
    )

    training_job_id = Column(
        Integer,
        ForeignKey("training_job.id"),
        nullable=False,
        unique=True,
    )

    model_type = Column(String, nullable=False)
    model_name = Column(String, nullable=False)
    ptid = Column(Integer, nullable=False)
    
    artifact_path = Column(String, nullable=False)
    
    # time of latest training completed
    trained_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    effective_start = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    effective_end = Column(
        DateTime(timezone=True),
        nullable=True
    )


