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
            
            completed_job = (
                db.query(TrainingJob) #type: ignore
                .filter(
                    TrainingJob.id == job_id,
                    TrainingJob.run_id == run_id,
                )
                .with_for_update()
                .one()
            )

            if completed_job.status != "running" or completed_job.attempt_count != attempt_count:
                raise RuntimeError(f"This attempt no longer owns the job")

            current = (
                        db.query(ModelVersion, TrainingJob) #type: ignore
                        .join(
                            TrainingJob,
                            ModelVersion.training_job_id == TrainingJob.id
                        )
                        .filter(
                            ModelVersion.run_id == run_id,
                            ModelVersion.model_name == model_name,
                            ModelVersion.ptid == ptid,
                            ModelVersion.effective_start.is_not(None),
                            ModelVersion.effective_end.is_(None),
                            )
                        .one_or_none()
            )
            
            if current is None:
                current_version = None
                promote_model_version = True
            else:
                current_version, current_version_job = current
                promote_model_version = (
                    current_version is None 
                    or completed_job.training_data_cutoff > current_version_job.training_data_cutoff
                )

            activation_time = now_ny() if promote_model_version else None

            if promote_model_version and current_version is not None:
                current_version.effective_end = activation_time

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
                    effective_start=activation_time #type: ignore
                    ), 
            ),
            
            completed_job.status = "succeeded"
            completed_job.completed_at = now_ny()
            completed_job.next_attempt_at = None
            completed_job.last_error = None

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