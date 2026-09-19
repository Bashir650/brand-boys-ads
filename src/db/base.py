from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base

from src.config import settings

if settings.database_url.startswith("sqlite:///"):
    # Make sure the parent directory exists so SQLite doesn't fail with
    # "unable to open database file" on a fresh checkout/deploy that hasn't
    # run scripts/init_db.py yet.
    db_path = Path(settings.database_url.removeprefix("sqlite:///"))
    db_path.parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
Base = declarative_base()
