"""Draw a stratified sample for manual labelling.

    python scripts/label_sample.py --input out/events.csv --n 100

Writes eval/gold/labels.csv with the extracted values filled in and the
judgement columns blank. You open it, read each source filing (the url column
is there for exactly that), and mark each field correct or not.

Stratifying by event type matters: a random sample of a skewed dataset gives you
forty acquisitions and two divestitures, and the accuracy figure then says
almost nothing about the rare classes.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from corpevents.config import ROOT

JUDGEMENT_COLUMNS = [
    "event_type_correct",      # y / n
    "deal_value_correct",      # y / n / na
    "counterparty_correct",    # y / n / na
    "is_actually_an_event",    # y / n  - catches false positives
    "notes",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(ROOT / "out" / "events.csv"))
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--out", default=str(ROOT / "eval" / "gold" / "labels.csv"))
    args = parser.parse_args()

    frame = pd.read_csv(args.input)
    if frame.empty:
        print("input is empty - run the pipeline first")
        return 1

    per_type = max(1, args.n // frame["event_type"].nunique())
    sample = (
        frame.groupby("event_type", group_keys=False)
        .apply(lambda g: g.sample(min(len(g), per_type), random_state=args.seed))
        .reset_index(drop=True)
    )

    keep = ["accession", "cik", "company", "filing_date", "event_type",
            "confidence", "deal_value_usd", "counterparty", "url"]
    sample = sample[keep]
    for column in JUDGEMENT_COLUMNS:
        sample[column] = ""

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sample.to_csv(out_path, index=False)

    print(f"wrote {len(sample)} rows to {out_path}")
    print("fill the judgement columns by hand, then run scripts/evaluate.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
