from sqlalchemy.orm import sessionmaker

from src.db.base import engine

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_session():
    return SessionLocal()
