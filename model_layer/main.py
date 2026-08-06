# run with a scheduler, every hour 
import os
from dotenv import load_dotenv

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from config import load_config
from jobs import train_model, predict_model, update_model




""""
load_dotenv()
jobstores = {"default": SQLAlchemyJobStore(url=os.getenv("DATABASE_URL"))}  # persists jobs across restarts
scheduler = BackgroundScheduler(jobstores=jobstores, timezone="UTC")

def make_trigger(spec: dict):
    if spec["type"] == "interval":
        return IntervalTrigger(**{k: v for k, v in spec.items() if k != "type"})
    if spec["type"] == "cron":
        return CronTrigger(**{k: v for k, v in spec.items() if k != "type"})

for model_config in load_config("models.yaml")["models"]:
    if not model_config["enabled"]:
        continue
    
    for ptid in model_config["ptids"]:

        scheduler.add_job(
            train_model, 
            trigger = model_config["train_schedule"],
            args=[model_config["name"]], 
            id=f"train_{model_config['name']}",
            max_instances=1, 
            coalesce=True, 
            misfire_grace_time=300,
        )

        scheduler.add_job(
            predict_model,
            trigger = model_config["predict_schedule"],
            args=[model_config["name"]], 
            id=f"train_{model_config['name']}",
            max_instances=1, 
            coalesce=True, 
            misfire_grace_time=60,
        )

        if model_config["update"]:
            scheduler.add_job(
                update_model,
                trigger = model_config
            )

scheduler.start()

# ptids = [61757,61754,61760,61753,61844,61758,61762,61756,61759,61761,61755,61845,61846,61847,61752]
"""