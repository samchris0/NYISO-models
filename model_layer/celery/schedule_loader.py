from datetime import timedelta
import yaml
from celery.schedules import crontab


def build_beat_schedule(yaml_path):

    with open(yaml_path) as f:
        config = yaml.safe_load(f)
    
    beat_schedule = {}

    for global_task in config["global_tasks"]:
        
        if global_task['type'] == 'interval':
            schedule = timedelta(
                days=global_task.get("days", 0),
                hours=global_task.get("hours", 0),
                minutes=global_task.get("minutes", 0),
                seconds=global_task.get("seconds", 0),
            )
        
        elif global_task['type'] == 'cron':
            schedule = crontab(
                minute=global_task.get('minutes', '*'),
                hour=global_task.get('hours', '*'),
                day_of_week=global_task.get('day_of_week', '*'),
                day_of_month=global_task.get('day_of_month', '*'),
                month_of_year=global_task.get('month_of_year', '*'),
            )
        
        else:
            raise ValueError(
                "Unknown schedule type"
            )

        name = global_task["name"]
        task = global_task["task_name"]
        args = global_task.get("args", [])
        kwargs = global_task.get("kwargs", {})

        beat_schedule[name] = {
            'task': task,
            'schedule': schedule, #type:ignore
            "args": args,
            "kwargs": kwargs,
        }

    return beat_schedule

"""
def build_beat_schedule(yaml_path):
    
    with open(yaml_path) as f:
        config = yaml.safe_load(f)

    beat_schedule = {}
    for models in config["models"]:
        
        if models["enabled"] is False:
            continue
        
        model_config = models["config"]

        for entry in models['tasks']:
            
            if entry['type'] == 'interval':
                schedule = timedelta(
                    days=entry.get("days", 0),
                    hours=entry.get("hours", 0),
                    minutes=entry.get("minutes", 0),
                    seconds=entry.get("seconds", 0),
                )
            
            elif entry['type'] == 'cron':
                schedule = crontab(
                    minute=entry.get('minutes', '*'),
                    hour=entry.get('hours', '*'),
                    day_of_week=entry.get('day_of_week', '*'),
                    day_of_month=entry.get('day_of_month', '*'),
                    month_of_year=entry.get('month_of_year', '*'),
                )
            
            else:
                raise ValueError(
                    "Unknown schedule type"
                )

            task = entry['task_name']
            name = f"{model_config['name']}-{task}"
            
            beat_schedule[name] = {
                'task': task,
                'schedule': schedule, #type:ignore
                'args': [model_config]
            }
    
    for global_task in config["global_tasks"]:
        
        if global_task['type'] == 'interval':
            schedule = timedelta(
                days=global_task.get("days", 0),
                hours=global_task.get("hours", 0),
                minutes=global_task.get("minutes", 0),
                seconds=global_task.get("seconds", 0),
            )
        
        elif global_task['type'] == 'cron':
            schedule = crontab(
                minute=global_task.get('minutes', '*'),
                hour=global_task.get('hours', '*'),
                day_of_week=global_task.get('day_of_week', '*'),
                day_of_month=global_task.get('day_of_month', '*'),
                month_of_year=global_task.get('month_of_year', '*'),
            )
        
        else:
            raise ValueError(
                "Unknown schedule type"
            )

        name = global_task["name"]
        task = global_task["task_name"]
        args = global_task.get("args", [])
        kwargs = global_task.get("kwargs", {})

        beat_schedule[name] = {
            'task': task,
            'schedule': schedule, #type:ignore
            "args": args,
            "kwargs": kwargs,
        }

    return beat_schedule
"""