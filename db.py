from sqlmodel import create_engine, Session
from sqlmodel import SQLModel
import threading
import os

DB_FILE = os.path.join(os.path.dirname(__file__), "ridepool.db")
_default_url = f"sqlite:///{DB_FILE}"
DATABASE_URL = os.environ.get("DATABASE_URL", _default_url)

# SQLite needs check_same_thread=False; Postgres does not
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# Application-level locks keyed by a simple name (e.g., matching)
locks = {}
locks_lock = threading.Lock()


def get_lock(name: str):
    with locks_lock:
        if name not in locks:
            locks[name] = threading.Lock()
        return locks[name]


engine = create_engine(DATABASE_URL, echo=False, connect_args=_connect_args)


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    return Session(engine)
