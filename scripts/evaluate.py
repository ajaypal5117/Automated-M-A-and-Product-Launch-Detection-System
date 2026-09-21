"""Score the pipeline against a hand-labelled sample.

    python scripts/evaluate.py --labels eval/gold/labels.csv

"Data accuracy" is defined here as field-level correctness: across the labelled
rows, the share of extracted field values that a human agreed with. It is
reported per field as well as overall, because one number hides the fact that
event_type and deal_value fail in very different ways.

Precision is reported separately from field accuracy. A row can have the right
event_type and still be a false positive if the filing wasn't an event at all.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from corpevents.config import ROOT

FIELDS = {
    "event_type_correct": "event_type",
    "deal_value_correct": "deal_value_usd",
    "counterparty_correct": "counterparty",
}


def rate(series):
    """Share of 'y' among rows judged either way. 'na' rows are excluded."""
    judged = series.astype(str).str.strip().str.lower()
    judged = judged[judged.isin(["y", "n"])]
    if judged.empty:
        return None, 0
    return (judged == "y").mean(), len(judged)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", default=str(ROOT / "eval" / "gold" / "labels.csv"))
    parser.add_argument("--out", default=str(ROOT / "eval" / "accuracy_report.md"))
    args = parser.parse_args()

    path = Path(args.labels)
    if not path.exists():
        print(f"no label file at {path}")
        print("run scripts/label_sample.py first, then fill in the judgement columns")
        return 1

    frame = pd.read_csv(path)
    unlabelled = frame["event_type_correct"].isna().sum()
    if unlabelled:
        print(f"warning: {unlabelled} rows have no judgement yet\n")

    lines = ["# Accuracy report", "", f"Labelled rows: {len(frame)}", ""]
    lines.append("| Field | Accuracy | Rows judged |")
    lines.append("|---|---|---|")

    correct_total = judged_total = 0
    for column, field in FIELDS.items():
        if column not in frame.columns:
            continue
        accuracy, n = rate(frame[column])
        if accuracy is None:
            lines.append(f"| `{field}` | not judged | 0 |")
            continue
        correct_total += accuracy * n
        judged_total += n
        lines.append(f"| `{field}` | {accuracy:.1%} | {n} |")

    if judged_total:
        overall = correct_total / judged_total
        lines += ["", f"**Field-level accuracy: {overall:.1%}** "
                      f"({judged_total} field judgements)"]

    if "is_actually_an_event" in frame.columns:
        precision, n = rate(frame["is_actually_an_event"])
        if precision is not None:
            lines += ["", f"**Precision: {precision:.1%}** ({n} rows) - share of extracted "
                          "rows that are genuinely corporate events."]

    if "event_type" in frame.columns and "event_type_correct" in frame.columns:
        lines += ["", "## By event type", "", "| Event type | Accuracy | n |", "|---|---|---|"]
        for event_type, group in frame.groupby("event_type"):
            accuracy, n = rate(group["event_type_correct"])
            if accuracy is not None:
                lines.append(f"| {event_type} | {accuracy:.1%} | {n} |")

    notes = frame.get("notes")
    if notes is not None and notes.notna().any():
        lines += ["", "## Failure notes", ""]
        for _, row in frame[frame["notes"].notna()].head(15).iterrows():
            lines.append(f"- `{row['accession']}` - {row['notes']}")

    report = "\n".join(lines)
    Path(args.out).write_text(report + "\n")
    print(report)
    print(f"\nwritten to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
