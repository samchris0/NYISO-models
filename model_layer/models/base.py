# models/base.py
from abc import ABC, abstractmethod
import joblib
from pathlib import Path

class BaseModel(ABC):
    name: str  # set by subclass

    def __init__(self, ptid: int, hyperparams: dict):
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
    def predict(self, input_data):
        """Return an array of predicted values."""
        ...

    def save(self, path: Path):
        joblib.dump(self.model, path)

    def load(self, path: Path):
        self.model = joblib.load(path)