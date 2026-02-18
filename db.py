from sqlmodel import create_engine, Session
from sqlmodel import SQLModel
import threading
import os

DB_FILE = os.path.join(os.path.dirname(__file__), "ridepool.db")
DATABASE_URL = f"sqlite:///{DB_FILE}"

# Application-level locks keyed by a simple name (e.g., matching)
locks = {}
locks_lock = threading.Lock()


def get_lock(name: str):
    with locks_lock:
        if name not in locks:
            locks[name] = threading.Lock()
        return locks[name]


engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    return Session(engine)
