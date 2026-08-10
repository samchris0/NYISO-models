from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import joblib

#create path creator function
ARTIFACT_ROOT_PATH = Path("model_layer/artifacts")

#create store function
def create_artifact_path(model_type: str, ptid: int) -> tuple[UUID, Path]:
    version = uuid4()

    artifact_path = ( 
        ARTIFACT_ROOT_PATH 
        / model_type 
        / f"ptid={str(ptid)}"
        / f"{version}.joblib"
    )

    return version, artifact_path
