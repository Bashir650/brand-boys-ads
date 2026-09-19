"""Extension point for Google's Ads Transparency Center
(https://adstransparency.google.com), which also covers a large number of
Indian and international advertisers and could feed the same
Competitor -> collector -> analysis -> dashboard pipeline as Meta and TikTok.

Left unimplemented on purpose: unlike Meta's Ad Library, Google has not
published a stable, documented public API for this at the time of writing.
The site's data loads via an internal backend used by its own JS frontend,
so a scraper here would need a headless browser (e.g. Playwright) and would
depend on an interface Google can change without notice.

Options if/when you want this wired up:
  1. Playwright-based scraping of adstransparency.google.com (JS-rendered,
     so requests/BeautifulSoup alone won't work).
  2. A paid data provider that already licenses this data (e.g. Pathmatics,
     Sensor Tower, Meltwater) via their own API.

The rest of the codebase is structured so adding this later is just: a new
`sync_competitor_google_ads(session, competitor)` function following the same
shape as src/collectors/meta_ads_library.py, a table in src/db/models.py, and
one more call in src/pipeline.py.
"""


def sync_competitor_google_ads(session, competitor):
    raise NotImplementedError(
        "Google Ads Transparency Center collector not implemented yet - see this "
        "module's docstring for options."
    )
