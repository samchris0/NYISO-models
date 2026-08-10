from model_layer.model_store import create_artifact_path
from model_layer.registry import MODEL_REGISTRY


def train_model(config: dict):
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

def predict_model():
    

    pass

def update_model():
    
    pass
    