"""Event classification.

Cue-based rather than a trained model, for one practical reason: there is no
labelled corpus of 8-K event types to train on, and building one large enough
would have been the whole project. Cues are transparent, and when a
classification is wrong you can see exactly which phrase caused it.

Scoring is weighted. "definitive agreement" is far more indicative than
"acquire", which shows up in boilerplate about previously acquired subsidiaries.
"""

from __future__ import annotations

import re

ACQUISITION_CUES = {
    "definitive agreement": 3, "merger agreement": 3, "stock purchase agreement": 3,
    "asset purchase agreement": 3, "business combination": 3, "tender offer": 3,
    "agreement and plan of merger": 4,
    "acquisition of": 2, "acquire all": 2, "to acquire": 2, "has acquired": 2,
    "completed the acquisition": 3,
    "acquisition": 1, "merger": 1,
}

DIVESTITURE_CUES = {
    "divestiture": 3, "sale of its": 2, "agreed to sell": 3, "disposition of": 2,
    "spin-off": 3, "carve-out": 2,
}

LAUNCH_CUES = {
    "general availability": 3, "commercially available": 3, "announce the launch": 4,
    "product launch": 3, "new product line": 3, "unveiled": 2, "introduces": 2,
    "now available": 2, "commercial release": 3, "launch of": 2, "launched": 1,
}

MERGER_ONLY = re.compile(r"(?i)(agreement and plan of merger|merger of equals|"
                         r"will merge with and into)")


def _score(text, cues):
    lowered = text.lower()
    hits = {cue: lowered.count(cue) for cue in cues if cue in lowered}
    total = sum(count * cues[cue] for cue, count in hits.items())
    return total, hits


def classify(text):
    """Return (event_type, confidence, evidence) or (None, 0.0, {})."""
    acq, acq_hits = _score(text, ACQUISITION_CUES)
    div, div_hits = _score(text, DIVESTITURE_CUES)
    launch, launch_hits = _score(text, LAUNCH_CUES)

    best = max(acq, div, launch)
    if best < 2:                       # a single weak cue isn't an announcement
        return None, 0.0, {}

    if best == acq:
        event = "merger" if MERGER_ONLY.search(text) else "acquisition"
        evidence = acq_hits
    elif best == div:
        event, evidence = "divestiture", div_hits
    else:
        event, evidence = "product_launch", launch_hits

    # Confidence saturates: past a handful of strong cues, more repetition of
    # the same phrase says nothing extra.
    confidence = round(min(0.45 + 0.08 * best, 0.95), 2)
    return event, confidence, evidence


COUNTERPARTY = re.compile(
    r"(?:acquisition of|agreed to acquire|to acquire|merger with|combination with|"
    r"agreed to sell|sale of)\s+"
    r"((?:[A-Z][\w&.\-']*\s+){0,4}[A-Z][\w&.\-']*"
    r"(?:,?\s+(?:Inc|Corp|Corporation|Ltd|Limited|LLC|L\.L\.C|LP|PLC|N\.V|S\.A|"
    r"Holdings|Group|Technologies|Systems|Labs|Pharmaceuticals)\.?)?)"
)

# Words that mean the regex latched onto a sentence fragment, not a company.
NOT_A_NAME = {"The", "This", "Such", "All", "Certain", "Its", "Our", "A", "An"}


def counterparty(text):
    for match in COUNTERPARTY.finditer(text):
        name = match.group(1).strip().rstrip(",.").strip()
        first = name.split()[0] if name else ""
        if len(name) > 3 and first not in NOT_A_NAME:
            return name
    return None
