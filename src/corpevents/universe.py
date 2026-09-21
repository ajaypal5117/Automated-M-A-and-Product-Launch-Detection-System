"""Build the company universe from EDGAR's quarterly full indexes.

`company_tickers.json` only covers listed companies with a ticker - about ten
thousand. The filer population is far larger, and the complete list lives in the
quarterly full indexes at /Archives/edgar/full-index/YYYY/QTRn/form.idx. Each
one is a fixed-width table of every filing accepted that quarter, so the set of
distinct CIKs across a year range is the real universe of registrants who filed
anything in that window.

Cost is one request per quarter - a 20-year universe is 80 requests, under a
minute at the rate limit. Cheap enough to rebuild rather than vendor.
"""

from __future__ import annotations

import csv
import logging
from datetime import date

from .client import WWW_HOST, get

log = logging.getLogger(__name__)

# form.idx is fixed-width with a header block; these are the column starts.
# They have been stable for years but are parsed from the header row when
# present rather than hardcoded blindly.
DEFAULT_COLUMNS = {"form": 0, "company": 12, "cik": 74, "date": 86, "file": 98}


def index_url(year, quarter):
    return f"{WWW_HOST}/Archives/edgar/full-index/{year}/QTR{quarter}/form.idx"


def _column_starts(header_line):
    """Locate columns from the header rather than trusting fixed offsets."""
    labels = [("form", "Form Type"), ("company", "Company Name"),
              ("cik", "CIK"), ("date", "Date Filed"), ("file", "File Name")]
    starts = {}
    for key, label in labels:
        position = header_line.find(label)
        if position < 0:
            return DEFAULT_COLUMNS
        starts[key] = position
    return starts


def parse_index(text):
    """Yield one dict per filing row in a form.idx file."""
    lines = text.splitlines()
    columns = DEFAULT_COLUMNS
    body_start = 0

    for i, line in enumerate(lines):
        if "Form Type" in line and "CIK" in line:
            columns = _column_starts(line)
        if set(line.strip()) == {"-"}:          # the dashed rule under the header
            body_start = i + 1
            break

    order = sorted(columns.items(), key=lambda kv: kv[1])
    for line in lines[body_start:]:
        if not line.strip():
            continue
        row = {}
        for idx, (key, start) in enumerate(order):
            end = order[idx + 1][1] if idx + 1 < len(order) else len(line)
            row[key] = line[start:end].strip()
        if not row.get("cik", "").isdigit():
            continue
        row["cik"] = row["cik"].zfill(10)
        yield row


def quarters(start_year, end_year=None):
    end_year = end_year or date.today().year
    today = date.today()
    for year in range(start_year, end_year + 1):
        for quarter in (1, 2, 3, 4):
            # Skip quarters that haven't happened yet - EDGAR returns 404.
            if year == today.year and quarter > (today.month - 1) // 3 + 1:
                continue
            yield year, quarter


def fetch_index(year, quarter):
    try:
        return get(index_url(year, quarter))
    except FileNotFoundError:
        log.warning("no index for %sQ%s", year, quarter)
        return ""


def build(start_year, end_year=None, forms=None, out_path=None):
    """Return {cik: {cik, company, forms, first_seen, last_seen, filings}}."""
    companies = {}
    wanted = set(forms) if forms else None

    for year, quarter in quarters(start_year, end_year):
        text = fetch_index(year, quarter)
        if not text:
            continue
        rows = 0
        for row in parse_index(text):
            if wanted and row["form"] not in wanted:
                continue
            rows += 1
            entry = companies.setdefault(
                row["cik"],
                {"cik": row["cik"], "company": row["company"], "forms": set(),
                 "first_seen": row["date"], "last_seen": row["date"], "filings": 0},
            )
            entry["forms"].add(row["form"])
            entry["filings"] += 1
            entry["last_seen"] = max(entry["last_seen"], row["date"])
            entry["first_seen"] = min(entry["first_seen"], row["date"])
        log.info("%sQ%s: %d rows kept, universe now %d companies",
                 year, quarter, rows, len(companies))

    if out_path:
        write_csv(companies, out_path)
    return companies


def write_csv(companies, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["cik", "company", "forms", "filings", "first_seen", "last_seen"])
        for entry in sorted(companies.values(), key=lambda e: e["cik"]):
            writer.writerow([entry["cik"], entry["company"], "|".join(sorted(entry["forms"])),
                             entry["filings"], entry["first_seen"], entry["last_seen"]])
    return out_path
