"""Executes every dashboard page against a database with no schema yet - the
exact state a brand-new deploy is in before the pipeline has ever run - and
asserts none of them raise. Catches the class of bug where a fresh Streamlit
Cloud/Render deploy crashes with "no such table" because nothing had called
Base.metadata.create_all() yet (see dashboard/utils.py's db_session()).

Uses Streamlit's own AppTest runner, which actually executes the script -
unlike an HTTP GET against a running server, which only fetches Streamlit's
static shell and never runs the page's Python code.
"""
import glob
import shutil

import pytest
from streamlit.testing.v1 import AppTest

from src.config import BASE_DIR
from src.db.base import Base, engine
from src.db.models import Competitor
from src.db.session import get_session

DB_PATH = BASE_DIR / "data" / "ads.db"
# AppTest.from_file resolves relative paths against this test file's own
# directory, not the CWD - use absolute paths to avoid that surprise.
PAGE_FILES = [str(BASE_DIR / "dashboard" / "app.py")] + sorted(
    glob.glob(str(BASE_DIR / "dashboard" / "pages" / "*.py"))
)


@pytest.fixture(autouse=True)
def _empty_database():
    """Temporarily moves any existing data/ads.db out of the way so each
    page runs against a schema-less database, then restores it afterward -
    never destroys real local/CI data."""
    backup = DB_PATH.with_suffix(".bak")
    moved = False
    if DB_PATH.exists():
        shutil.move(DB_PATH, backup)
        moved = True
    yield
    if DB_PATH.exists():
        DB_PATH.unlink()
    if moved:
        shutil.move(backup, DB_PATH)


@pytest.mark.parametrize("page_file", PAGE_FILES)
def test_page_does_not_crash_on_empty_database(page_file):
    at = AppTest.from_file(page_file, default_timeout=30)
    at.run()
    assert not at.exception, f"{page_file} raised: {[e.value for e in at.exception]}"


def test_competitor_ads_library_with_competitors_but_no_ads_yet():
    """Reproduces the exact reported bug: competitors exist (the pipeline's
    ensure_competitors_synced always runs), but the meta_ads/tiktok_ads
    tables are still empty (e.g. the scheduled Action ran before a Meta
    access token was configured). pd.DataFrame([]) has zero columns, so code
    indexing df["competitor_id"] raised KeyError before dashboard/utils.py
    started passing `columns=` explicitly."""
    Base.metadata.create_all(engine)
    session = get_session()
    session.add(
        Competitor(name="Example Competitor 1", meta_search_terms="Example Competitor 1", is_own_brand=False)
    )
    session.add(Competitor(name="Our Brand", is_own_brand=True))
    session.commit()
    session.close()

    for page in ["1_Competitor_Ads_Library.py", "2_Winning_Creatives_and_Dupes.py"]:
        at = AppTest.from_file(str(BASE_DIR / "dashboard" / "pages" / page), default_timeout=30)
        at.run()
        assert not at.exception, f"{page} raised: {[e.value for e in at.exception]}"
