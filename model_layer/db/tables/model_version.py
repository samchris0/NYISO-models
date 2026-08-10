from sqlalchemy import Column, String, Float, DateTime, Integer, Boolean

from model_layer.db.database import Base

class ModelVersion(Base):
    __tablename__ = "model_version"

    version_id = Column(String, primary_key=True)
    active = Column(Boolean, nullable=False)
    training = Column(Boolean, nullable=False)
    model_type = Column(String, nullable=False)
    ptid = Column(Integer, nullable=False)
    artifact_path = Column(String, nullable=False)