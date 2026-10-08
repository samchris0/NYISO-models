from model_layer.models import *

MODEL_REGISTRY = {'auto_arima': ARIMA,
                  'seasonal_naive':SeasonalNaive,
                  'seasonal_median':SeasonalMedian,
                  'fourier_ridge':FourierRidge}