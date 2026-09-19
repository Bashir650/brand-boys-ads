"""Creates the SQLite (or configured DATABASE_URL) tables. Run once before the
first pipeline run: `python scripts/init_db.py`
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import models  # noqa: F401  (registers models on Base before create_all)
from src.db.base import Base, engine


def main():
    Path("data").mkdir(exist_ok=True)
    Base.metadata.create_all(engine)
    print("Database tables created.")


if __name__ == "__main__":
    main()
