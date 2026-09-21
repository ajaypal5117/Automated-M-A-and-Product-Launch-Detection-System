"""Measure sustained processing throughput.

    python scripts/measure_throughput.py --quarter 2025Q2 --n 400 --no-cache

Times a fixed number of filings end to end (fetch, clean, filter, classify) and
extrapolates to 25,000. Run it with --no-cache for a number that reflects real
network conditions; cached runs measure parsing speed only.
"""

import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from corpevents import pipeline
from corpevents.client import stats
from corpevents.config import settings

QUARTER = re.compile(r"^(\d{4})Q([1-4])$", re.IGNORECASE)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quarter", required=True)
    parser.add_argument("--n", type=int, default=400)
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    match = QUARTER.match(args.quarter)
    if not match:
        parser.error("--quarter must look like 2025Q2")

    if args.no_cache:
        import shutil
        shutil.rmtree(settings.cache_dir, ignore_errors=True)

    filings = pipeline.discover_quarter(int(match.group(1)), int(match.group(2)),
                                        limit=args.n)
    stats.reset()

    started = time.time()
    _, run_stats = pipeline.run(filings)
    elapsed = time.time() - started

    per_hour = run_stats.processed / elapsed * 3600
    print(f"\n{run_stats.processed} filings in {elapsed:.1f}s")
    print(f"  workers            {settings.workers}")
    print(f"  rate limit         {settings.rate_limit}/s")
    print(f"  throughput         {per_hour:,.0f} filings/hr")
    print(f"  25,000 filings in  {25000 / per_hour:.1f} hrs")
    print(f"  http               {stats.snapshot()}")


if __name__ == "__main__":
    main()
