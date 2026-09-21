"""Stage 1 of noise reduction: decide what not to download.

Every 8-K is tagged by the SEC with the item numbers it reports under. Most of
that volume is structurally incapable of containing a corporate event - Item
2.02 is an earnings release, 5.02 is an officer change, 5.07 is a shareholder
vote. Filtering on the item number happens on metadata, before the document is
requested, so the filings that get dropped cost nothing to drop.

That ordering is the whole point: the filter saves bandwidth and wall-clock,
not just downstream parsing.
"""

from __future__ import annotations

import re

# Items that can carry an acquisition, a merger or a launch announcement.
RELEVANT_ITEMS = {
    "1.01": "entry into a material definitive agreement",
    "1.02": "termination of a material definitive agreement",
    "2.01": "completion of acquisition or disposition of assets",
    "7.01": "regulation FD disclosure",
    "8.01": "other events",
}

# High-volume items that never carry one. Listed explicitly so the reasoning is
# reviewable rather than implied by absence.
KNOWN_NOISE_ITEMS = {
    "2.02": "results of operations",
    "5.02": "departure or election of officers",
    "5.03": "amendments to bylaws",
    "5.07": "submission of matters to a vote",
    "9.01": "financial statements and exhibits",
}

ITEM_PATTERN = re.compile(r"\b(\d{1,2}\.\d{2})\b")


def parse_items(raw):
    """Item lists arrive as comma-separated strings, or embedded in header text."""
    if not raw:
        return []
    return ITEM_PATTERN.findall(str(raw))


def is_relevant(raw):
    items = parse_items(raw)
    if not items:
        # No item metadata (the full-index route) - can't rule it out here, so
        # it falls through to the text-level filter instead of being dropped.
        return None
    return any(item in RELEVANT_ITEMS for item in items)


def explain(raw):
    """Why a filing was kept or dropped. Used by the measurement script."""
    items = parse_items(raw)
    if not items:
        return {"decision": "unknown", "items": [], "reason": "no item metadata"}
    kept = [i for i in items if i in RELEVANT_ITEMS]
    if kept:
        return {"decision": "keep", "items": items,
                "reason": "; ".join(RELEVANT_ITEMS[i] for i in kept)}
    noise = [KNOWN_NOISE_ITEMS.get(i, f"item {i}") for i in items]
    return {"decision": "drop", "items": items, "reason": "; ".join(noise)}
