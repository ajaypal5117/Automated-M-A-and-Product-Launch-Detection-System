"""Turn one raw filing into one dataset row, or decide it isn't an event.

This is the T in the ETL: extraction is the client and discovery modules, load
is `load.py`, and everything in between happens here.
"""

from __future__ import annotations

import json

from . import classify, cleaning, filters, money


def process(filing, raw_text):
    """Return (record | None, diagnostics).

    The diagnostics come back either way, because the measurement scripts need
    to know about the filings that were dropped as well as the ones that weren't.
    """
    text, metrics = cleaning.clean(raw_text)

    items = filing.get("items")
    if not items:
        # Full-index route doesn't carry item numbers; recover them from the text.
        found = cleaning.find_item_numbers(text)
        items = ",".join(sorted(set(found))) if found else None

    relevant = filters.is_relevant(items)
    diagnostics = {**metrics, "items": items, "item_filter": relevant}

    if relevant is False:
        diagnostics["dropped_by"] = "item_filter"
        return None, diagnostics

    event_type, confidence, evidence = classify.classify(text)
    if event_type is None:
        diagnostics["dropped_by"] = "no_event_cues"
        return None, diagnostics

    # A dollar figure in a launch announcement is a unit price, not a deal value.
    value = money.headline_amount(text) if event_type != "product_launch" else None

    record = {
        "cik": filing.get("cik"),
        "company": filing.get("company"),
        "filing_date": filing.get("filing_date"),
        "accession": filing.get("accession"),
        "items": items,
        "event_type": event_type,
        "confidence": confidence,
        "deal_value_usd": value,
        "counterparty": classify.counterparty(text),
        "evidence": json.dumps(evidence, sort_keys=True),
        "chars_in": metrics["chars_in"],
        "chars_out": metrics["chars_out"],
        "url": filing.get("url"),
    }
    diagnostics["dropped_by"] = None
    return record, diagnostics
