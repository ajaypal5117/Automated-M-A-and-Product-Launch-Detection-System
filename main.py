"""Run the pipeline: companies -> 8-K filings -> filtered -> parsed -> CSV.

    python main.py --limit 200 --since 2025-01-01
    python main.py --tickers AAPL MSFT NVDA --since 2024-01-01
    python main.py --summary out/events.csv

Progress and counts print as it goes, because a full run over thousands of
companies takes hours at the SEC's rate limit and a silent process is
indistinguishable from a hung one.
"""

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

import edgar
import extract

COLUMNS = [
    "cik", "company", "filing_date", "event_type", "confidence",
    "deal_value_usd", "counterparty", "items", "accession", "url",
]


def select_companies(limit=None, tickers=None):
    companies = edgar.company_tickers()
    if tickers:
        wanted = {ticker.upper() for ticker in tickers}
        companies = [c for c in companies if c["ticker"].upper() in wanted]
    return companies[:limit] if limit else companies


def run(companies, since=None, per_company=None):
    events = []
    stats = {"companies": 0, "filings": 0, "relevant": 0, "events": 0, "errors": 0}
    started = time.time()

    for index, company in enumerate(companies, start=1):
        stats["companies"] += 1
        try:
            filings = edgar.recent_8ks(company["cik"], since=since, limit=per_company)
        except Exception as error:
            stats["errors"] += 1
            print(f"  ! {company['ticker']}: {error}", file=sys.stderr)
            continue

        stats["filings"] += len(filings)

        for filing in filings:
            # Item-number filter first: avoids downloading the document at all.
            if not extract.is_relevant(filing["items"]):
                continue
            stats["relevant"] += 1
            try:
                raw = edgar.filing_text(filing["url"])
            except Exception:
                stats["errors"] += 1
                continue

            event = extract.extract_event(filing, raw)
            if event:
                events.append(event)
                stats["events"] += 1

        if index % 25 == 0 or index == len(companies):
            rate = stats["filings"] / max(time.time() - started, 1)
            print(
                f"  {index}/{len(companies)} companies | {stats['filings']} filings "
                f"| {stats['relevant']} relevant | {stats['events']} events "
                f"| {rate:.1f} filings/s"
            )

    return events, stats


def to_frame(events):
    frame = pd.DataFrame(events, columns=COLUMNS)
    if frame.empty:
        return frame
    frame["filing_date"] = pd.to_datetime(frame["filing_date"], errors="coerce")
    return frame.sort_values("deal_value_usd", ascending=False, na_position="last")


def summarise(frame):
    if frame.empty:
        print("No events extracted.")
        return

    total = frame["deal_value_usd"].sum(skipna=True)
    print(f"\n{len(frame)} events | disclosed value ${total/1e9:,.1f}B\n")
    print(frame["event_type"].value_counts().to_string())

    top = frame.dropna(subset=["deal_value_usd"]).head(10)
    if not top.empty:
        print("\nLargest disclosed events:")
        for _, row in top.iterrows():
            date = row["filing_date"].date() if pd.notna(row["filing_date"]) else "?"
            print(f"  ${row['deal_value_usd']/1e9:7.2f}B  {date}  "
                  f"{row['company'][:34]:34} {row['event_type']}")


def main():
    parser = argparse.ArgumentParser(description="Extract M&A and product launch events from 8-Ks.")
    parser.add_argument("--limit", type=int, help="Number of companies to scan")
    parser.add_argument("--tickers", nargs="+", help="Specific tickers instead of a slice")
    parser.add_argument("--since", help="Only filings on or after this date (YYYY-MM-DD)")
    parser.add_argument("--per-company", type=int, default=20, help="Max 8-Ks per company")
    parser.add_argument("--out", default="out/events.csv", help="Output CSV path")
    parser.add_argument("--summary", metavar="CSV", help="Summarise an existing CSV and exit")
    args = parser.parse_args()

    if args.summary:
        summarise(pd.read_csv(args.summary, parse_dates=["filing_date"]))
        return 0

    companies = select_companies(limit=args.limit, tickers=args.tickers)
    if not companies:
        print("No companies matched.")
        return 1

    print(f"Scanning {len(companies)} companies since {args.since or 'the start of the feed'}\n")
    events, stats = run(companies, since=args.since, per_company=args.per_company)

    frame = to_frame(events)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)

    dropped = stats["filings"] - stats["relevant"]
    if stats["filings"]:
        print(f"\nFiltered out {dropped}/{stats['filings']} filings "
              f"({dropped/stats['filings']:.0%}) on item number before download.")
    summarise(frame)
    print(f"\nWrote {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
