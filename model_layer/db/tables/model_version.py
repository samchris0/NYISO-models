from sqlalchemy import Column, String, Float, DateTime, Integer, Boolean, Index
from sqlalchemy.sql import func

from model_layer.db.database import Base

class ModelVersion(Base):
    __tablename__ = "model_version"

    version_id = Column(String, primary_key=True)
    active = Column(Boolean, nullable=False)
    model_type = Column(String, nullable=False)
    ptid = Column(Integer, nullable=False)
    artifact_path = Column(String, nullable=False)
    
    updating = Column(    
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index(
            "uq_active_model_per_type_ptid",
            "model_type",
            "ptid",
            unique=True,
            postgresql_where=active.is_(True),
        ),
    )