"""The L in ETL: write the dataset out and summarise it."""

from __future__ import annotations

import pandas as pd

from .config import settings
from .schema import coerce, validate


def write(records, name="events"):
    """Write CSV and parquet. Returns (frame, paths)."""
    frame = coerce(pd.DataFrame(records))
    if not frame.empty:
        frame = frame.sort_values(
            ["deal_value_usd", "filing_date"], ascending=[False, False], na_position="last"
        )

    settings.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = settings.out_dir / f"{name}.csv"
    frame.to_csv(csv_path, index=False)

    paths = {"csv": csv_path}
    try:
        parquet_path = settings.out_dir / f"{name}.parquet"
        frame.to_parquet(parquet_path, index=False)
        paths["parquet"] = parquet_path
    except Exception:
        # pyarrow is optional; CSV is the guaranteed output.
        pass

    return frame, paths


def summarise(frame):
    if frame.empty:
        return "No events extracted."

    lines = []
    valued = frame["deal_value_usd"].dropna()
    total = valued.sum()
    lines.append(f"{len(frame)} events | {len(valued)} with a disclosed value "
                 f"| ${total / 1e9:,.1f}B total")
    lines.append("")
    lines.append(frame["event_type"].value_counts().to_string())

    top = frame.dropna(subset=["deal_value_usd"]).head(10)
    if not top.empty:
        lines.append("")
        lines.append("Largest disclosed events:")
        for _, row in top.iterrows():
            date = row["filing_date"].date() if pd.notna(row["filing_date"]) else "?"
            company = (row["company"] or "")[:36]
            lines.append(f"  ${row['deal_value_usd'] / 1e9:8.2f}B  {date}  "
                         f"{company:36} {row['event_type']}")

    problems = validate(frame)
    if problems:
        lines.append("")
        lines.append("Schema warnings: " + "; ".join(problems))

    return "\n".join(lines)
