from datetime import datetime

from pathlib import Path

from model_layer.db.database import SessionLocal
from model_layer.db.tables.model_version import ModelVersion

def get_active_model(model_name: str, ptid: int):
    with SessionLocal.begin() as db:
        current = (
            db.query(ModelVersion) #type: ignore
            .filter(
                ModelVersion.model_name == model_name,
                ModelVersion.ptid == ptid,
            )
            .one_or_none()
        )

        if current is not None:
            return Path(current.artifact_path), current.version_id
        
        else:
            return None