"""SEC EDGAR client.

Three things the SEC actually enforces, all handled here:

* A descriptive `User-Agent` with a contact address. Requests without one get
  403'd, so `EDGAR_USER_AGENT` is required rather than optional.
* 10 requests per second, max. `_throttle` sleeps to stay under it, which is
  what makes a 25,000-filing run take hours rather than getting the IP blocked.
* Filing documents live on `www.sec.gov`, but the JSON metadata APIs live on
  `data.sec.gov`. They are different hosts with different path shapes.

Responses are cached on disk, so re-running a job does not re-download anything.
"""

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

DATA_HOST = "https://data.sec.gov"
WWW_HOST = "https://www.sec.gov"
CACHE_DIR = Path(os.getenv("CACHE_DIR", Path(__file__).parent / ".cache"))
RATE_LIMIT = 10.0            # requests per second, SEC's published ceiling
_last_request = [0.0]


def user_agent():
    agent = os.getenv("EDGAR_USER_AGENT", "").strip()
    if not agent:
        raise RuntimeError(
            "EDGAR_USER_AGENT is not set. The SEC requires a contact string such as "
            "'Your Name your.email@example.com'. Copy .env.example to .env."
        )
    return agent


def _throttle():
    elapsed = time.monotonic() - _last_request[0]
    minimum = 1.0 / RATE_LIMIT
    if elapsed < minimum:
        time.sleep(minimum - elapsed)
    _last_request[0] = time.monotonic()


def _cache_path(url):
    name = url.replace("https://", "").replace("/", "_")[:180]
    return CACHE_DIR / name


def fetch(url, as_json=False, use_cache=True):
    """GET a URL, honouring the rate limit and the on-disk cache."""
    cached = _cache_path(url)
    if use_cache and cached.exists():
        text = cached.read_text(encoding="utf-8", errors="replace")
        return json.loads(text) if as_json else text

    _throttle()
    response = requests.get(
        url,
        headers={"User-Agent": user_agent(), "Accept-Encoding": "gzip, deflate"},
        timeout=30,
    )
    response.raise_for_status()
    text = response.text

    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cached.write_text(text, encoding="utf-8")

    return json.loads(text) if as_json else text


def company_tickers():
    """Every registrant with a ticker: {cik, ticker, title}. ~10k companies."""
    data = fetch(f"{WWW_HOST}/files/company_tickers.json", as_json=True)
    return [
        {"cik": str(row["cik_str"]).zfill(10), "ticker": row["ticker"], "name": row["title"]}
        for row in data.values()
    ]


def submissions(cik):
    """All recent filings for one company."""
    cik = str(cik).zfill(10)
    return fetch(f"{DATA_HOST}/submissions/CIK{cik}.json", as_json=True)


def recent_8ks(cik, since=None, limit=None):
    """Return 8-K filings for a company as a list of dicts."""
    data = submissions(cik)
    recent = data.get("filings", {}).get("recent", {})
    if not recent:
        return []

    name = data.get("name", "")
    columns = ["form", "accessionNumber", "filingDate", "primaryDocument", "items"]
    rows = zip(*(recent.get(column, []) for column in columns))

    filings = []
    for form, accession, date, document, items in rows:
        if form != "8-K":
            continue
        if since and date < since:
            continue
        filings.append(
            {
                "cik": str(cik).zfill(10),
                "company": name,
                "accession": accession,
                "filing_date": date,
                "items": items,
                "url": document_url(cik, accession, document),
            }
        )
        if limit and len(filings) >= limit:
            break
    return filings


def document_url(cik, accession, document):
    plain_cik = str(int(cik))
    plain_accession = accession.replace("-", "")
    return f"{WWW_HOST}/Archives/edgar/data/{plain_cik}/{plain_accession}/{document}"


def filing_text(url):
    return fetch(url)
