from sqlalchemy import Column, String, Float, DateTime, Integer, ForeignKey, UniqueConstraint

from model_layer.db.database import Base

class Prediction(Base):
    __tablename__ = "prediction"

    id = Column(Integer, primary_key=True, autoincrement=True)

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

    __table_args__ = (
        UniqueConstraint(
            "version_id",
            "ptid",
            "target_timestamp",
            name="uq_prediction_identity",
        ),
    )
