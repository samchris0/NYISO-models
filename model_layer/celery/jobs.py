from datetime import datetime

from model_layer.utils.build_target_timestamps import build_target_timestamps
from model_layer.utils.model_store import create_artifact_path
from model_layer.utils.get_active_model import get_active_model
from model_layer.utils.save_prediction import save_prediction
from model_layer.utils.time import floor_to_five_minutes, now_ny
from model_layer.registry import MODEL_REGISTRY

def train_model(config: dict):
    model_type = config["model_type"]
    ptid = config["ptid"]
    model_name = config["name"]

    model_class = MODEL_REGISTRY[model_type]
    model = model_class(name=model_name, ptid=ptid, hyperparams=config.get("hyperparameters", {}))

    training_days = config.get("training_window_days")

    X, y = model.fetch_training_data(training_days)

    # train model
    model.train(X,y)

    # add metadata: time train start/stop, etc.
    trained_at = now_ny()

    print(f"Trained model: {config['name']} succesfully")

    version, artifact_path = create_artifact_path(model_name, ptid)
    print(f"Created artifact path: {artifact_path}")

    # save model to joblib path and update active model table
    model.save(artifact_path,version,trained_at)
    print("Saved artifact to disk and metadate to postgres")

def predict_model(config: dict):
    start_time_floor = floor_to_five_minutes(now_ny())

    model_type = config["model_type"]
    ptid = config["ptid"]
    model_name = config["name"]

    active_model = get_active_model(model_name=model_name,ptid=ptid)

    if active_model is None:
        raise RuntimeError(
            f"No active model for {model_name}, PTID {ptid}"
        )
    
    active_artifact, active_model_version_id = active_model

    model_class = MODEL_REGISTRY[model_type]
    model = model_class(name=model_name, ptid=ptid, hyperparams={})

    model.load(active_artifact)

    interval_minutes = config["interval_minutes"]
    forecast_intervals = config["forecast_intervals"]

    target_timestamps = build_target_timestamps(start_time_floor, interval_minutes, forecast_intervals)

    # generate features if needed
    features = model.prepare_prediction_features(target_timestamps)

    # make predictions
    predictions = model.predict(target_timestamps, features)

    # validate predictions
    if len(predictions) != len(target_timestamps):
        raise ValueError(
            "Model returned a different number of predictions "
            "than requested target timestamps"
        )

    if not predictions.index.equals(target_timestamps):
        raise ValueError(
            "Prediction index does not match target timestamps"
        )

    if predictions.isna().any():
        raise ValueError("Model returned missing predictions")

    # record time of predictions
    issued_at = now_ny()

    # save predictions
    save_prediction(version_id=active_model_version_id,
                    model_name=model_name,
                    ptid=ptid,
                    issued_at=issued_at,
                    target_timestamps=target_timestamps, #type: ignore
                    predicted_lbmps=predictions) #type: ignore

def update_model():
    pass
