"""Measure noise reduction on real filings.

    python scripts/measure_noise.py --quarter 2025Q2 --sample 500

Reports both stages separately, because they reduce different things:

  filing-level    share of filings dropped without being downloaded
  character-level share of bytes removed from the filings that were downloaded

The README quotes both. Run it and paste the output there rather than trusting
the number that happens to be written down.
"""

import argparse
import random
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from corpevents import cleaning, filters, pipeline
from corpevents.client import get

QUARTER = re.compile(r"^(\d{4})Q([1-4])$", re.IGNORECASE)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quarter", required=True)
    parser.add_argument("--sample", type=int, default=300)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()

    match = QUARTER.match(args.quarter)
    if not match:
        parser.error("--quarter must look like 2025Q2")

    filings = pipeline.discover_quarter(int(match.group(1)), int(match.group(2)))
    print(f"{len(filings):,} 8-K filings in {args.quarter}")

    random.seed(args.seed)
    sample = random.sample(filings, min(args.sample, len(filings)))

    kept = dropped = unknown = 0
    reductions = []
    reasons = {}

    for filing in sample:
        try:
            raw = get(filing["url"])
        except Exception:
            continue

        text, metrics = cleaning.clean(raw)
        reductions.append(metrics["reduction"])

        items = filing.get("items") or ",".join(sorted(set(cleaning.find_item_numbers(text))))
        verdict = filters.explain(items)
        if verdict["decision"] == "keep":
            kept += 1
        elif verdict["decision"] == "drop":
            dropped += 1
            for reason in verdict["reason"].split("; "):
                reasons[reason] = reasons.get(reason, 0) + 1
        else:
            unknown += 1

    total = kept + dropped + unknown
    print(f"\nsample of {total} filings from {args.quarter}\n")
    print("stage 1 - item-number filter (before download)")
    print(f"  kept     {kept:5} ({kept / total:.1%})")
    print(f"  dropped  {dropped:5} ({dropped / total:.1%})")
    print(f"  unknown  {unknown:5} ({unknown / total:.1%})")

    if reasons:
        print("\n  top drop reasons:")
        for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1])[:6]:
            print(f"    {count:4}  {reason}")

    if reductions:
        print("\nstage 2 - text cleaning (characters removed)")
        print(f"  mean     {statistics.mean(reductions):.1%}")
        print(f"  median   {statistics.median(reductions):.1%}")
        print(f"  min/max  {min(reductions):.1%} / {max(reductions):.1%}")


if __name__ == "__main__":
    main()
