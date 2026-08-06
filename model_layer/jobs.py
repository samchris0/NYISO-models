from registry import MODEL_REGISTRY

def train_model(model_name: str, ptid: int, config: dict):
    model_class = MODEL_REGISTRY[model_name]
    model = model_class(ptid=ptid, hyperparameters=config.get("hyperparameters", {}))
    
    model.

    model.fit(data)
    save_model_version(model)

def predict_model():
    pass
    
def ingest_data():