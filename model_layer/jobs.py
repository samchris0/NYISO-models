from model_store import create_artifact_path
from registry import MODEL_REGISTRY


def train_model(model_name: str, ptid: int, config: dict):
    model_class = MODEL_REGISTRY[model_name]
    model = model_class(ptid=ptid, hyperparameters=config.get("hyperparameters", {}))
    
    model_type = model.name

    training_days = config.get("training_window_days")

    X, y = model.fetch_training_data(training_days)
    
    # train model
    model.train(X,y)

    # add metadata: time train start/stop, etc.
    metadata = {}
    version, artifact_path = create_artifact_path(model_type, ptid)

    # save model to joblib path and update active model table
    model.save(artifact_path,version,metadata)
    

def predict_model():
    

    pass

def update_model():
    
    pass
    