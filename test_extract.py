"""Tests. No network — everything runs against the fixtures in samples/.

`test_noise_reduction_rate` measures the item-number filter against a labelled
distribution rather than asserting a number from nowhere.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

import extract
from main import to_frame

SAMPLES = Path(__file__).parent / "samples"


def read(name):
    return (SAMPLES / name).read_text()


# ---------------------------------------------------------------- item filter

def test_relevant_items_pass_the_filter():
    assert extract.is_relevant("1.01,9.01")
    assert extract.is_relevant("2.01")
    assert extract.is_relevant("7.01")


def test_noise_items_are_filtered_out():
    assert not extract.is_relevant("2.02,9.01")
    assert not extract.is_relevant("5.02")
    assert not extract.is_relevant("")


def test_noise_reduction_rate():
    """Item mix approximating real 8-K volume: earnings and officer changes dominate."""
    population = (
        ["2.02,9.01"] * 40 +      # earnings releases
        ["5.02"] * 20 +           # officer changes
        ["5.07"] * 12 +           # shareholder votes
        ["9.01"] * 8 +            # exhibits only
        ["7.01,9.01"] * 10 +      # Reg FD - kept
        ["1.01,9.01"] * 6 +       # material agreements - kept
        ["2.01"] * 4              # completed acquisitions - kept
    )
    kept = sum(extract.is_relevant(items) for items in population)
    dropped = 1 - kept / len(population)
    print(f"\nnoise reduction: {dropped:.0%} ({len(population) - kept}/{len(population)} dropped)")
    assert dropped >= 0.75


# ---------------------------------------------------------------- money

def test_parses_billions_and_millions():
    assert extract.largest_amount("a deal worth $2.4 billion today") == 2_400_000_000
    assert extract.largest_amount("about $450 million") == 450_000_000


def test_parses_bare_comma_separated_figures():
    assert extract.largest_amount("paid $1,850,000,000 in cash") == 1_850_000_000


def test_largest_amount_picks_the_headline_figure():
    text = "consideration of $2.4 billion, comprising $1,850,000,000 cash and $550 million stock"
    assert extract.largest_amount(text) == 2_400_000_000


def test_no_amount_returns_none():
    assert extract.largest_amount("no figures disclosed here") is None


# ---------------------------------------------------------------- classification

def test_acquisition_is_classified_and_valued():
    event = extract.extract_event(
        {"cik": "0000001", "company": "Meridian Systems, Inc.", "filing_date": "2025-10-14",
         "accession": "0000001-25-000001", "items": "1.01,9.01", "url": "http://x"},
        read("8k_acquisition.htm"),
    )
    assert event["event_type"] == "acquisition"
    assert event["deal_value_usd"] == 2_400_000_000
    assert "Calderon" in event["counterparty"]


def test_product_launch_is_classified():
    event = extract.extract_event(
        {"cik": "0000002", "company": "Northgate Devices Corp.", "filing_date": "2025-09-03",
         "accession": "0000002-25-000002", "items": "7.01", "url": "http://y"},
        read("8k_launch.htm"),
    )
    assert event["event_type"] == "product_launch"


def test_earnings_release_yields_no_event():
    assert extract.extract_event({"cik": "3"}, read("8k_earnings.htm")) is None


def test_html_tags_and_scripts_are_stripped():
    text = extract.clean_html(read("8k_acquisition.htm"))
    assert "<p>" not in text
    assert "should not appear" not in text
    assert "definitive agreement" in text


# ---------------------------------------------------------------- output

def test_frame_sorts_by_deal_value_descending():
    frame = to_frame([
        {"cik": "1", "company": "Small Co", "filing_date": "2025-01-01", "event_type": "acquisition",
         "confidence": 0.7, "deal_value_usd": 5e8, "counterparty": None, "items": "1.01",
         "accession": "a", "url": "u"},
        {"cik": "2", "company": "Big Co", "filing_date": "2025-02-01", "event_type": "merger",
         "confidence": 0.8, "deal_value_usd": 9e9, "counterparty": None, "items": "1.01",
         "accession": "b", "url": "u"},
    ])
    assert frame.iloc[0]["company"] == "Big Co"
    assert pd.api.types.is_datetime64_any_dtype(frame["filing_date"])


def test_empty_results_produce_an_empty_frame_not_a_crash():
    assert to_frame([]).empty


def test_product_launch_does_not_report_a_deal_value():
    """A unit price in a launch filing must not be recorded as deal value."""
    event = extract.extract_event(
        {"cik": "0000002", "company": "Northgate Devices Corp.", "filing_date": "2025-09-03",
         "accession": "a", "items": "7.01", "url": "u"},
        read("8k_launch.htm"),
    )
    assert event["event_type"] == "product_launch"
    assert event["deal_value_usd"] is None
