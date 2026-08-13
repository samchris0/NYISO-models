from sqlalchemy import Column, String, Float, DateTime, Integer, Boolean, Index

from model_layer.db.database import Base

class Prediction(Base):
    __tablename__ = "prediction"

    id = 

    model_version_id = Column(String, nullable=False)
    model_name = Column(String, nullable=False)
    ptid = Column(Integer, nullable=False)

    issued_at = Column(DateTime,nullable=False)
    target_timestamp = Column(DateTime, nullable=False)
    predicted_lbmp = Column(Float, nullable=False)

    actual_lbmp = Column(Float, nullable=True)
    evaluated_at = Column(DateTime, nullable=True)
    absolute_error = Column(Float, nullable=True)
    squared_error = Column(Float, nullable=True)