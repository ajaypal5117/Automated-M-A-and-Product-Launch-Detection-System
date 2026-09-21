"""Find 8-K filings to process.

Two routes, for two different jobs:

* `from_index` reads the quarterly full index and returns every 8-K filed in
  that quarter. One request per quarter covers thousands of filings, which is
  what makes a bulk run feasible.
* `from_submissions` hits the per-company JSON API. Slower per filing, but it
  carries the item numbers, which is what the prefilter needs. Used when
  targeting specific tickers.

The index route doesn't include item numbers, so those filings get their items
from the filing header during processing instead.
"""

from __future__ import annotations

import logging

from .client import DATA_HOST, WWW_HOST, get
from .universe import fetch_index, parse_index

log = logging.getLogger(__name__)


def document_url(cik, accession, document):
    return (f"{WWW_HOST}/Archives/edgar/data/{int(cik)}/"
            f"{accession.replace('-', '')}/{document}")


def index_file_url(file_name):
    """The 'File Name' column is a path relative to the archives root."""
    return f"{WWW_HOST}/Archives/{file_name}"


def from_index(year, quarter, limit=None):
    """Every 8-K accepted in one quarter, from the full index."""
    text = fetch_index(year, quarter)
    if not text:
        return []

    filings = []
    for row in parse_index(text):
        if row["form"] != "8-K":
            continue
        filings.append({
            "cik": row["cik"],
            "company": row["company"],
            "filing_date": row["date"],
            "accession": row["file"].rsplit("/", 1)[-1].replace(".txt", ""),
            "items": None,                    # not in the index; read later
            "url": index_file_url(row["file"]),
            "source": "full-index",
        })
        if limit and len(filings) >= limit:
            break

    log.info("%sQ%s: %d 8-K filings", year, quarter, len(filings))
    return filings


def from_submissions(cik, since=None, limit=None):
    """8-Ks for one company, with item numbers attached."""
    cik = str(cik).zfill(10)
    data = get(f"{DATA_HOST}/submissions/CIK{cik}.json", as_json=True)
    recent = data.get("filings", {}).get("recent", {})
    if not recent:
        return []

    name = data.get("name", "")
    columns = ["form", "accessionNumber", "filingDate", "primaryDocument", "items"]
    filings = []

    columns_data = [recent.get(c, []) for c in columns]
    for form, accession, filed, document, items in zip(*columns_data, strict=False):
        if form != "8-K" or (since and filed < since):
            continue
        filings.append({
            "cik": cik,
            "company": name,
            "filing_date": filed,
            "accession": accession,
            "items": items,
            "url": document_url(cik, accession, document),
            "source": "submissions",
        })
        if limit and len(filings) >= limit:
            break
    return filings


def resolve_tickers(tickers):
    """Map tickers to CIKs using the SEC's own mapping file."""
    data = get(f"{WWW_HOST}/files/company_tickers.json", as_json=True)
    wanted = {t.upper() for t in tickers}
    return [
        {"cik": str(row["cik_str"]).zfill(10), "ticker": row["ticker"], "company": row["title"]}
        for row in data.values()
        if row["ticker"].upper() in wanted
    ]
