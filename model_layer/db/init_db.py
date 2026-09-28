import time
from sqlalchemy.exc import OperationalError

from model_layer.db.database import engine, Base
import model_layer.db.tables

def init_db(retries=5, delay=2):
    for attempt in range(retries):
        try:
            # drop all tables, keep in development to allow for changes, remove in deployment
            Base.metadata.drop_all(bind=engine) #type: ignore
            Base.metadata.create_all(bind=engine) #type: ignore
            print("Database initialized.")
            return
        except OperationalError:
            print(f"DB not ready, retrying ({attempt+1}/{retries})...")
            time.sleep(delay)
    raise RuntimeError("Could not connect to the database.")

