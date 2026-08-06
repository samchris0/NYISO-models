from models import *

MODEL_REGISTRY = {'auto_arima': ARIMA,
                  'seasonal_naive':SeasonalNaive}