from model_layer.db.database import SessionLocal
from model_layer.db.tables.model_version import ModelVersion

def update_model_version(version_id: str, model_type: str, ptid: int, artifact_path: str):
    with SessionLocal.begin() as db:
        current = (
            db.query(ModelVersion)
            .filter(
                ModelVersion.model_type == model_type,
                ModelVersion.ptid == ptid,
                ModelVersion.active.is_(True),
            )
            .with_for_update()
            .one_or_none()
        )

        if current is not None:
            current.active = False

        db.add(
            ModelVersion(
                version_id=version_id,
                model_type=model_type,
                ptid=ptid,
                artifact_path=artifact_path,
                active=True,
                updating=False,
            )
        )