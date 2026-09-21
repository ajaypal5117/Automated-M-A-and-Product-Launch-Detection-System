"""Build the company universe from EDGAR's quarterly indexes.

    python scripts/build_universe.py --from 2005 --to 2025
    python scripts/build_universe.py --from 2020 --forms 8-K

Writes data/universe.csv and prints the distinct company count. One request per
quarter, so a twenty-year universe is ~80 requests.
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from corpevents import universe
from corpevents.config import ROOT

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="start", type=int, required=True)
    parser.add_argument("--to", dest="end", type=int, default=None)
    parser.add_argument("--forms", nargs="+", default=None,
                        help="Restrict to specific form types, e.g. 8-K")
    parser.add_argument("--out", default=str(ROOT / "data" / "universe.csv"))
    args = parser.parse_args()

    companies = universe.build(args.start, args.end, forms=args.forms,
                               out_path=Path(args.out))

    total_filings = sum(c["filings"] for c in companies.values())
    print(f"\nuniverse: {len(companies):,} distinct companies")
    print(f"filings covered: {total_filings:,}")
    print(f"window: {args.start}-{args.end or 'present'}"
          + (f", forms {args.forms}" if args.forms else ""))
    print(f"written to {args.out}")


if __name__ == "__main__":
    main()
