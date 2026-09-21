from sqlalchemy import func, Column, String, DateTime, Integer, ForeignKey, JSON, UniqueConstraint, Boolean

from model_layer.db.database import Base

class ForecastRun(Base):
    __tablename__ = "forecast_run"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # human readable label
    name = Column(String, nullable=False, unique=True)

    """
    two options
    live: live forecasting model for every 5 minutes
    historical: backtesting for a given time period
    """
    mode = Column(
        String,
        nullable=False
    )

    enabled = Column(Boolean, nullable=False, default=True, server_default="true")

    """
    options include:
    pending
    running
    completed
    failed
    """
    status = Column(
        String,
        nullable=False,
        server_default="running",
    )
        
    # Time stamp to start forecast from
    start_timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    # Time stamp to end forecast, should be null for indefinite runs
    end_timestamp = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # configuration json read from models.yaml
    model_config = Column(JSON, nullable=False)
    training_config = Column(JSON, nullable=False)
    prediction_config = Column(JSON, nullable=False)

    # record when the run starts
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )