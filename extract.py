"""Turn one 8-K filing into a structured event record, or discard it.

Most 8-Ks are noise for this purpose — Item 2.02 earnings releases, Item 5.02
officer changes, Item 7.01 investor decks. The cheap filter is the 8-K item
number the SEC already assigns, applied before any text is downloaded. Only
filings that survive that filter get parsed, which is where the bulk of the
noise reduction comes from.

Text is then scanned for a deal value and a counterparty, and classified as an
acquisition, a merger, a divestiture or a product launch.
"""

import re
from html import unescape

# 8-K items worth reading. 1.01/2.01 carry M&A; 7.01/8.01 carry launches and
# other voluntary disclosures. Everything else is dropped unread.
RELEVANT_ITEMS = {
    "1.01": "material_agreement",
    "2.01": "completed_acquisition",
    "7.01": "reg_fd_disclosure",
    "8.01": "other_events",
}

# Items that dominate 8-K volume and never contain what we want.
NOISE_ITEMS = {"2.02", "5.02", "5.07", "9.01"}

MNA_CUES = [
    "acquisition", "acquire", "merger", "merge with", "definitive agreement",
    "purchase agreement", "business combination", "tender offer", "divestiture",
    "sale of", "stock purchase agreement", "asset purchase",
]

LAUNCH_CUES = [
    "launch", "unveil", "introduce", "announce the availability", "general availability",
    "now available", "product line", "new product", "commercial release", "debut",
]

TAGS = re.compile(r"<[^>]+>")
WHITESPACE = re.compile(r"\s+")

# "$1.2 billion", "$450 million", "$1,200,000"
MONEY = re.compile(
    r"\$\s?([\d,]+(?:\.\d+)?)\s*(billion|million|thousand|bn|mm|m|b)?",
    re.IGNORECASE,
)

MULTIPLIER = {
    "billion": 1_000_000_000, "bn": 1_000_000_000, "b": 1_000_000_000,
    "million": 1_000_000, "mm": 1_000_000, "m": 1_000_000,
    "thousand": 1_000,
}

# "acquisition of Foo Corp", "merger with Bar Inc."
COUNTERPARTY = re.compile(
    r"(?:acquisition of|acquire|merger with|combination with|purchase of)\s+"
    r"((?:[A-Z][\w&.\-]*\s+){0,4}[A-Z][\w&.\-]*"
    r"(?:\s+(?:Inc|Corp|Corporation|Ltd|LLC|LP|PLC|Holdings|Group|Technologies|Systems)\.?)?)"
)


def parse_items(items_field):
    """Split the comma-separated item list the submissions API returns."""
    if not items_field:
        return []
    return [item.strip() for item in str(items_field).split(",") if item.strip()]


def is_relevant(items_field):
    """Cheap pre-filter on item numbers, run before downloading the document."""
    items = parse_items(items_field)
    if not items:
        return False
    return any(item in RELEVANT_ITEMS for item in items)


def clean_html(raw):
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    text = TAGS.sub(" ", text)
    text = unescape(text)
    return WHITESPACE.sub(" ", text).strip()


def parse_amount(match):
    """Turn a regex money match into a float number of dollars."""
    number, unit = match.group(1), (match.group(2) or "").lower()
    try:
        value = float(number.replace(",", ""))
    except ValueError:
        return None
    return value * MULTIPLIER.get(unit, 1)


def largest_amount(text):
    """The biggest dollar figure in the text — usually the headline deal value."""
    amounts = [parse_amount(match) for match in MONEY.finditer(text)]
    amounts = [amount for amount in amounts if amount]
    return max(amounts) if amounts else None


def classify_event(text):
    """Return (event_type, confidence) from cue density."""
    lowered = text.lower()
    mna = sum(lowered.count(cue) for cue in MNA_CUES)
    launch = sum(lowered.count(cue) for cue in LAUNCH_CUES)

    if mna == 0 and launch == 0:
        return None, 0.0

    if mna >= launch:
        if "divestiture" in lowered or "sale of" in lowered:
            event = "divestiture"
        elif "merger" in lowered or "business combination" in lowered:
            event = "merger"
        else:
            event = "acquisition"
        strength = mna
    else:
        event = "product_launch"
        strength = launch

    confidence = min(0.5 + 0.1 * strength, 0.95)
    return event, round(confidence, 2)


def find_counterparty(text):
    match = COUNTERPARTY.search(text)
    if not match:
        return None
    name = match.group(1).strip().rstrip(",.")
    return name if len(name) > 2 else None


def extract_event(filing, raw_text):
    """Build an event record from a filing, or return None if it isn't one."""
    text = clean_html(raw_text)
    event_type, confidence = classify_event(text)
    if event_type is None:
        return None

    # A dollar figure only means "deal value" for M&A. In a launch filing the
    # biggest number is usually a unit price, so leave it out rather than
    # letting it inflate the totals.
    value = largest_amount(text) if event_type != "product_launch" else None
    return {
        "cik": filing.get("cik"),
        "company": filing.get("company"),
        "filing_date": filing.get("filing_date"),
        "accession": filing.get("accession"),
        "items": filing.get("items"),
        "event_type": event_type,
        "confidence": confidence,
        "deal_value_usd": value,
        "counterparty": find_counterparty(text),
        "url": filing.get("url"),
    }
