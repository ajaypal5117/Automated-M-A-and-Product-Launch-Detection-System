"""Run the ETL.

    python scripts/run_pipeline.py --quarter 2025Q2
    python scripts/run_pipeline.py --quarter 2025Q2 --limit 25000 --checkpoint out/ckpt.jsonl
    python scripts/run_pipeline.py --tickers AAPL MSFT --since 2024-01-01

Prints a run report at the end containing every figure the README quotes:
filings processed, wall clock, throughput, both noise reduction rates.
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from corpevents import load, pipeline
from corpevents.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
log = logging.getLogger("run")

QUARTER = re.compile(r"^(\d{4})Q([1-4])$", re.IGNORECASE)


def progress(stats):
    log.info("%d processed | %d events | %.0f filings/hr",
             stats.processed, stats.events, stats.filings_per_hour)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quarter", help="Bulk mode, e.g. 2025Q2")
    parser.add_argument("--tickers", nargs="+", help="Targeted mode")
    parser.add_argument("--since", help="YYYY-MM-DD (ticker mode only)")
    parser.add_argument("--limit", type=int, help="Cap the number of filings")
    parser.add_argument("--per-company", type=int, default=40)
    parser.add_argument("--checkpoint", help="JSONL file to resume from")
    parser.add_argument("--name", default="events", help="Output file stem")
    args = parser.parse_args()

    if args.quarter:
        match = QUARTER.match(args.quarter)
        if not match:
            parser.error("--quarter must look like 2025Q2")
        filings = pipeline.discover_quarter(int(match.group(1)), int(match.group(2)),
                                            limit=args.limit)
    elif args.tickers:
        filings = pipeline.discover_tickers(args.tickers, since=args.since,
                                            per_company=args.per_company)
        if args.limit:
            filings = filings[:args.limit]
    else:
        parser.error("give --quarter or --tickers")

    if not filings:
        print("nothing discovered")
        return 1

    print(f"discovered {len(filings):,} 8-K filings\n")
    records, stats = pipeline.run(filings, checkpoint=args.checkpoint, on_progress=progress)

    frame, paths = load.write(records, name=args.name)
    print("\n" + load.summarise(frame))

    report = stats.as_dict()
    report_path = settings.out_dir / f"{args.name}_run_report.json"
    report_path.write_text(json.dumps(report, indent=2))

    print("\nrun report")
    print(f"  processed          {report['processed']:,} filings")
    print(f"  wall clock         {report['elapsed_seconds'] / 3600:.2f} hrs")
    print(f"  throughput         {report['filings_per_hour']:,.0f} filings/hr")
    print(f"  filing-level drop  {report['filing_level_reduction']:.1%}")
    print(f"  character-level    {report['character_level_reduction']:.1%}")
    print(f"  errors             {report['errors']}")
    print(f"\nwrote {paths['csv']} and {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
