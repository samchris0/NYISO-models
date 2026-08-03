# models/base.py
from abc import ABC, abstractmethod
import joblib
from pathlib import Path

class BaseModel(ABC):
    name: str  # set by subclass

    def __init__(self, hyperparams: dict):
        self.hyperparams = hyperparams
        self.model = None  # the actual fitted estimator lives here

    @abstractmethod
    def fetch_training_data(self):
        """Pull whatever data this model needs from the API."""
        ...

    @abstractmethod
    def train(self, data):
        """Fit self.model on data. Must set self.model."""
        ...

    @abstractmethod
    def fetch_predict_input(self):
        """Pull latest data needed to make a prediction right now."""
        ...

    @abstractmethod
    def predict(self, input_data):
        """Return a single predicted value (or dict of values)."""
        ...

    def save(self, path: Path):
        joblib.dump(self.model, path)

    def load(self, path: Path):
        self.model = joblib.load(path)