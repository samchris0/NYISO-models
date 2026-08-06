import models
from models import *

MODEL_REGISTRY = {'auto_arima':AutoARIMA,
                  'seasonal_naive':SeasonalNaive}