"""The output contract.

Declared once, here, so the CSV, the parquet file and the evaluation harness
agree on column names and types. `docs/data-dictionary.md` documents what each
field means; this is the machine-readable half of the same thing.
"""

from __future__ import annotations

import pandas as pd

COLUMNS = {
    "cik": "string",
    "company": "string",
    "filing_date": "datetime64[ns]",
    "accession": "string",
    "items": "string",
    "event_type": "string",
    "confidence": "float64",
    "deal_value_usd": "float64",
    "counterparty": "string",
    "evidence": "string",
    "chars_in": "Int64",
    "chars_out": "Int64",
    "url": "string",
}

EVENT_TYPES = ["acquisition", "merger", "divestiture", "product_launch"]


def empty_frame():
    return pd.DataFrame({name: pd.Series(dtype=dtype) for name, dtype in COLUMNS.items()})


def coerce(frame):
    """Force a raw frame into the declared schema. Missing columns are added."""
    if frame.empty:
        return empty_frame()

    for name, dtype in COLUMNS.items():
        if name not in frame.columns:
            frame[name] = None
        if dtype.startswith("datetime"):
            frame[name] = pd.to_datetime(frame[name], errors="coerce")
        elif dtype == "float64":
            frame[name] = pd.to_numeric(frame[name], errors="coerce")
        elif dtype == "Int64":
            frame[name] = pd.to_numeric(frame[name], errors="coerce").astype("Int64")
        else:
            frame[name] = frame[name].astype("string")

    return frame[list(COLUMNS)]


def validate(frame):
    """Return a list of problems. Empty list means the dataset is well-formed."""
    problems = []
    if frame.empty:
        return problems

    missing = [c for c in COLUMNS if c not in frame.columns]
    if missing:
        problems.append(f"missing columns: {', '.join(missing)}")

    bad_types = sorted(set(frame["event_type"].dropna()) - set(EVENT_TYPES))
    if bad_types:
        problems.append(f"unknown event_type values: {bad_types}")

    if frame["confidence"].dropna().between(0, 1).all() is False:
        problems.append("confidence outside [0, 1]")

    negative = (frame["deal_value_usd"].dropna() < 0).sum()
    if negative:
        problems.append(f"{negative} negative deal values")

    duplicates = frame.duplicated(subset=["accession"]).sum()
    if duplicates:
        problems.append(f"{duplicates} duplicate accession numbers")

    launches_with_value = frame[
        (frame["event_type"] == "product_launch") & frame["deal_value_usd"].notna()
    ]
    if len(launches_with_value):
        problems.append(f"{len(launches_with_value)} product launches carry a deal value")

    return problems
