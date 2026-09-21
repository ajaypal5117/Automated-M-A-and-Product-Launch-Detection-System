from corpevents import transform


def test_acquisition_produces_a_full_record(fixture, filing):
    record, diagnostics = transform.process(filing(items="1.01,9.01"),
                                            fixture("8k_acquisition.txt"))
    assert record["event_type"] == "merger"
    assert record["deal_value_usd"] == 2.4e9
    assert "Calderon" in record["counterparty"]
    assert diagnostics["dropped_by"] is None


def test_launch_carries_no_deal_value(fixture, filing):
    """A unit price is not consideration - this was a real bug once."""
    record, _ = transform.process(filing(items="7.01"), fixture("8k_launch.txt"))
    assert record["event_type"] == "product_launch"
    assert record["deal_value_usd"] is None


def test_earnings_filing_is_dropped_by_the_item_filter(fixture, filing):
    record, diagnostics = transform.process(filing(items="2.02,9.01"),
                                            fixture("8k_earnings.txt"))
    assert record is None
    assert diagnostics["dropped_by"] == "item_filter"


def test_dividend_filing_is_dropped_by_the_cue_stage(fixture, filing):
    record, diagnostics = transform.process(filing(items="8.01"),
                                            fixture("8k_dividend.txt"))
    assert record is None
    assert diagnostics["dropped_by"] == "no_event_cues"


def test_items_recovered_when_metadata_is_absent(fixture, filing):
    """The full-index route supplies no item numbers."""
    record, diagnostics = transform.process(filing(items=None),
                                            fixture("8k_divestiture.txt"))
    assert "2.01" in diagnostics["items"]
    assert record["event_type"] == "divestiture"


def test_diagnostics_returned_even_for_dropped_filings(fixture, filing):
    _, diagnostics = transform.process(filing(items="2.02"), fixture("8k_earnings.txt"))
    assert diagnostics["chars_in"] > 0 and diagnostics["chars_out"] > 0


def test_provenance_survives_into_the_record(fixture, filing):
    record, _ = transform.process(filing(items="1.01"), fixture("8k_acquisition.txt"))
    assert record["accession"] == "0001628280-25-031447"
    assert record["cik"] == "0000912345"
