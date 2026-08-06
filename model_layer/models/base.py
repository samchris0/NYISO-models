# models/base.py
import os
import tempfile
from uuid import UUID

from abc import ABC, abstractmethod
import joblib
from pathlib import Path

class BaseModel(ABC):
    name: str  # set by subclass

    def __init__(self, ptid: int, hyperparams: dict):
        self.ptid = ptid
        self.hyperparams = hyperparams
        self.model = None  # the actual fitted estimator lives here


    @abstractmethod
    def fetch_training_data(self,training_window_days):
        """Pull whatever data this model needs from the API."""
        ...

    @abstractmethod
    def train(self, X, y):
        """Fit self.model on data. Must set self.model."""
        ...

    @abstractmethod
    def predict(self, input_datetime):
        """Return an array of predicted values."""
        ...

    def save(self, destination: Path, version: UUID, metadata: dict):
        
        artifact = {
            "model_type": self.name,
            "ptid": self.ptid,
            "hyperparameters": self.hyperparams,
            "metadata": metadata,
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

            # update active models database
            update_model_version(
                version_id = version,
                model_type = self.name,
                ptid = self.ptid,
                artifact_path = str(destination)
            )
        
        except:
            # if table update fails, delete unregistered model
            destination.unlink(missing_ok=True)
            raise RuntimeError(
                "Model version table update failed"
            )
        
        finally:
            temporary_path.unlink(missing_ok=True)



    def load(self, path: Path):
        self.model = joblib.load(path)