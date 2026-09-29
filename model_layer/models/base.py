# models/base.py
import os
import tempfile
from datetime import datetime
from uuid import UUID

from abc import ABC, abstractmethod
import joblib
import pandas as pd
from pathlib import Path

from model_layer.utils.update_model_version import update_model_version
from model_layer.utils.api_client import get_real_time_lbmp_zonal

class BaseModel(ABC):
    name: str  # set by subclass

    def __init__(self, name: str, ptid: int, hyperparams: dict):
        self.name = name
        self.ptid = ptid
        self.hyperparams = hyperparams
        self.model = None  # the actual fitted estimator lives here

    def fetch_training_data(self, training_window_days, *, start, cutoff) -> tuple[pd.Series, pd.Series]:
        """Pull whatever data this model needs from the API."""
        self.training_window_days = training_window_days

        data = get_real_time_lbmp_zonal(start, cutoff, self.ptid)

        data = data.loc[
            (data["timestamp"] > start)
            & (data["timestamp"] <= cutoff)
        ]

        if data.empty or not data["timestamp"].eq(cutoff).any():
            raise ValueError("No observations in the training window")
        
        return data["timestamp"], data["lbmp"]

    @abstractmethod
    def train(self, X, y):
        """Fit self.model on data. Must set self.model."""
        ...

    @abstractmethod
    def predict(self, target_timestamps: pd.DatetimeIndex,
                features: pd.DataFrame | None = None) -> pd.Series:
        """Return an array of predicted values."""
        ...

    def prepare_prediction_features(self, target_timestamps, scheduled_for):
        return None

    def save(self, destination: Path, trained_at: datetime):
        
        artifact = {
            "model_name": self.name,
            "ptid": self.ptid,
            "hyperparameters": self.hyperparams,
            "trained_at": trained_at,
            "state": self.model,
        }

        destination.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            dir=destination.parent,
            suffix=".joblib",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

        try:
            # save artifact to temporary file so it can not be accessed until it is fully saved
            joblib.dump(artifact,temporary_path)
            
            # move to correct path when done
            os.replace(temporary_path,destination)
            
            #Deprecated function, model_version is now updated in the job function
            """
            # update active models database
            update_model_version(
                version_id = str(version),
                model_name = self.name,
                ptid = self.ptid,
                artifact_path = str(destination),
                trained_at = trained_at
            )
            """
            
        except Exception as exc:
            destination.unlink(missing_ok=True)
            raise RuntimeError(
                "Model artifact registration failed"
            ) from exc
        
        finally:
            temporary_path.unlink(missing_ok=True)

    def load(self, path: Path):
        artifact = joblib.load(path)

        if artifact["model_name"] != self.name:
            raise ValueError("Artifact model type does not match")
        if artifact["ptid"] != self.ptid:
            raise ValueError("Artifact PTID does not match")

        self.model = artifact["state"]
        self.hyperparams = artifact["hyperparameters"]
