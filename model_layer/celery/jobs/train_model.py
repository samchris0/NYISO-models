from datetime import timedelta
from dotenv import load_dotenv

from sqlalchemy import update

from model_layer.db.database import SessionLocal
from model_layer.db.tables.forecast_run import ForecastRun
from model_layer.db.tables.model_version import ModelVersion
from model_layer.db.tables.training_job import TrainingJob

from model_layer.utils.model_store import create_artifact_path
from model_layer.utils.time import now_ny
from model_layer.registry import MODEL_REGISTRY

load_dotenv()

def train_model(job_id: int, attempt_count: int):
    
    MAX_ATTEMPTS = 5

    try: 
        with SessionLocal() as db: 

            result = (
                db.query(TrainingJob, ForecastRun) #type: ignore
                .join(ForecastRun, ForecastRun.id == TrainingJob.run_id)
                .filter(
                    TrainingJob.id == job_id
                )
                .one_or_none()
            )

            if result is None:
                raise ValueError(f"Training job {job_id} does not exist")
            
            job, run = result
            
            model_config = dict(run.model_config)
            training_config = dict(run.training_config)
            run_id = run.id

            scheduled_for = job.scheduled_for
            training_start = job.training_data_start
            training_cutoff = job.training_data_cutoff

        # Close db connection
        model_type = model_config["model_type"]
        ptid = model_config["ptid"]
        model_name = run.name

        model_class = MODEL_REGISTRY[model_type]
        model = model_class(name=model_name, ptid=ptid, hyperparams=model_config.get("hyperparameters", {}))

        training_days = training_config["training_window_days"]

        X, y = model.fetch_training_data(training_days, 
                                            start= training_start, 
                                            cutoff = training_cutoff)

        # train model
        model.train(X,y)

        # add metadata: time train start/stop, etc.
        completed_at = now_ny()

        version_id, artifact_path = create_artifact_path(model_name, ptid)

        # save model to joblib path and update active model table
        model.save(artifact_path,completed_at)

        with SessionLocal.begin() as db:
            db.query(ForecastRun).filter( #type: ignore
                ForecastRun.id == run_id
            ).with_for_update().one()
            
            job = (
                db.query(TrainingJob) #type: ignore
                .filter(
                    TrainingJob.id == job_id,
                    TrainingJob.run_id == run_id,
                )
                .with_for_update()
                .one()
            )

            if job.status != "running" or job.attempt_count != attempt_count:
                raise RuntimeError(f"Training jobs in race condition")

            versions = (
                        db.query(ModelVersion) #type: ignore
                        .filter(
                                ModelVersion.run_id.run_id == run_id,
                                ModelVersion.model_name == model_name,
                                ModelVersion.ptid == ptid,
                                )
            )
            
            previous_version = (
                versions.filter(ModelVersion.effective_start < scheduled_for)
                .order_by(ModelVersion.effective_start.desc())
                .first()
            )

            next_version = (
                versions.filter(ModelVersion.effective_start > scheduled_for)
                .order_by(ModelVersion.effective_start.asc())
                .first()
            )

            if previous_version is not None:
                previous_version.effective_end = scheduled_for


            db.add(
                ModelVersion( 
                    version_id=str(version_id), #type: ignore
                    run_id=run_id, #type: ignore
                    training_job_id=job_id, #type: ignore
                    model_type=model_type, #type: ignore
                    model_name=model_name, #type: ignore
                    ptid=ptid, #type: ignore
                    artifact_path=str(artifact_path), #type: ignore
                    trained_at=completed_at, #type: ignore
                    effective_start=scheduled_for, #type: ignore
                    effective_end=( #type: ignore
                            next_version.scheduled_for 
                            if next_version is not None
                            else None
                    ), 
                ),
            )

            job.status = "succeeded"
            job.completed_at = now_ny()
            job.next_attempt_at = None
            job.last_error = None

    except Exception as exc:
        failed_at = now_ny()
        exhausted = attempt_count >= MAX_ATTEMPTS

        with SessionLocal.begin() as db:
            db.execute(
                update(TrainingJob)
                .where(
                    TrainingJob.id == job_id,
                    TrainingJob.status == "running",
                    TrainingJob.attempt_count == attempt_count,
                )
                .values(
                    status="failed" if exhausted else "retryable",
                    last_error=str(exc),
                    next_attempt_at = (
                        None if exhausted
                        else failed_at+timedelta(minutes=5)
                    ),
                    completed_at = (
                        None if not exhausted
                        else failed_at
                    )
                )
                .execution_options(synchronize_session=False)
            )
        
        raise