import requests
from sqlalchemy.exc import OperationalError

from model_layer.celery.celery_app import app
from model_layer.model_store import create_artifact_path
from model_layer.registry import MODEL_REGISTRY

@app.task(
    name = "tasks.train",
    autoretry_for=(requests.RequestException, OperationalError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,     
)
def train_task(config: dict):
    model_type = config["model_type"]
    ptid = config["ptid"]
    
    model_class = MODEL_REGISTRY[model_type]
    model = model_class(ptid=ptid, hyperparams=config.get("hyperparameters", {}))
    
    model_type = model.name

    training_days = config.get("training_window_days")

    X, y = model.fetch_training_data(training_days)
    
    # train model
    model.train(X,y)

    print(f"Trained model: {config['name']} succesfully")

    # add metadata: time train start/stop, etc.
    metadata = {}
    version, artifact_path = create_artifact_path(model_type, ptid)
    print(f"Created artifact path: {artifact_path}")

    # save model to joblib path and update active model table
    model.save(artifact_path,version,metadata)
    print("Saved artifact to disk and metadate to postgres")

@app.task(
    name = "tasks.predict",
)
def predict_task(config: dict):
    pass

@app.task(
    name = "tasks.update"
)
def update_task(config: dict):
    pass

