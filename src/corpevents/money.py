"""Dollar amount parsing.

Filings write the same number half a dozen ways: "$2.4 billion", "$2,400.0
million", "approximately $2.4 billion in cash and stock", "$1,850,000,000".
They also contain amounts that are not the deal value at all - share prices,
prior-year revenue, credit facility sizes.

`headline_amount` takes the largest figure, which is right for consideration
paid and wrong when a filing discusses several transactions. That trade-off is
deliberate and recorded in the known-issues section of the README.
"""

from __future__ import annotations

import re

AMOUNT = re.compile(
    r"\$\s?(\d[\d,]*(?:\.\d+)?)\s*(billion|million|thousand|bn|mm\b|m\b|b\b)?",
    re.IGNORECASE,
)

MULTIPLIER = {
    "billion": 1e9, "bn": 1e9, "b": 1e9,
    "million": 1e6, "mm": 1e6, "m": 1e6,
    "thousand": 1e3,
}

# Amounts sitting next to these are not deal consideration.
EXCLUDE_CONTEXT = re.compile(
    r"(?i)(per share|revenue|net income|earnings|credit facility|par value|"
    r"exercise price|annual salary|outstanding shares)"
)


def parse(match):
    raw, unit = match.group(1), (match.group(2) or "").strip().lower()
    try:
        value = float(raw.replace(",", ""))
    except ValueError:
        return None
    return value * MULTIPLIER.get(unit, 1)


def all_amounts(text):
    return [v for v in (parse(m) for m in AMOUNT.finditer(text)) if v]


def headline_amount(text, look_back=60, look_ahead=20):
    """Largest amount that isn't sitting in an excluded context.

    The window is deliberately asymmetric. Disqualifying phrases almost always
    precede the figure ("revenue of $900 million", "credit facility of $1.2
    billion"); the one that follows it is a unit suffix like "per share". A
    symmetric window lets an unrelated phrase further down the sentence
    disqualify a perfectly good deal value.
    """
    candidates = []
    for match in AMOUNT.finditer(text):
        value = parse(match)
        if not value:
            continue
        context = text[max(0, match.start() - look_back):match.end() + look_ahead]
        if EXCLUDE_CONTEXT.search(context):
            continue
        candidates.append(value)
    return max(candidates) if candidates else None
