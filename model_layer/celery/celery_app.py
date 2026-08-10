from celery import Celery

app = Celery(
    'myproject',

    # change localhost to redis initialization in docker compose
    broker='redis://localhost:6379/0',
)
