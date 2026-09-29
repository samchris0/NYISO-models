from datetime import datetime

from model_layer.db.database import SessionLocal
from model_layer.db.tables.model_version import ModelVersion

def update_model_version(version_id: str, model_name: str, ptid: int, artifact_path: str, trained_at: datetime):
    with SessionLocal.begin() as db:
        current = (
            db.query(ModelVersion) #type: ignore
            .filter(
                ModelVersion.model_name == model_name,
                ModelVersion.ptid == ptid,
            )
            .with_for_update()
            .one_or_none()
        )

        if current is not None:
            current.active = False

        db.add(
            ModelVersion(
                version_id=version_id,
                model_name=model_name,
                ptid=ptid,
                artifact_path=artifact_path,
                trained_at=trained_at,
                active=True,
                updating=False,
            )
        )