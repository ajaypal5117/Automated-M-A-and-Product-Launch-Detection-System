from corpevents import filters


def test_relevant_items_are_kept():
    assert filters.is_relevant("1.01,9.01") is True
    assert filters.is_relevant("2.01") is True
    assert filters.is_relevant("7.01") is True


def test_pure_noise_items_are_dropped():
    assert filters.is_relevant("2.02,9.01") is False
    assert filters.is_relevant("5.02") is False
    assert filters.is_relevant("5.07,9.01") is False


def test_missing_metadata_returns_unknown_not_false():
    """Dropping on absent metadata would silently discard the whole index route."""
    assert filters.is_relevant(None) is None
    assert filters.is_relevant("") is None


def test_items_parsed_out_of_header_prose():
    items = filters.parse_items("ITEM INFORMATION: 1.01 Entry into a Material Agreement; 9.01")
    assert "1.01" in items and "9.01" in items


def test_explain_gives_a_human_reason():
    assert "earnings" not in filters.explain("2.02")["reason"]
    assert filters.explain("2.02")["decision"] == "drop"
    assert filters.explain("1.01")["decision"] == "keep"
    assert "material definitive agreement" in filters.explain("1.01")["reason"]


def test_filing_level_reduction_on_a_representative_item_mix():
    """Item mix weighted the way real 8-K volume runs.

    Shares are from the distribution documented in docs/noise-reduction.md;
    this pins the filter's behaviour on that mix so a change to RELEVANT_ITEMS
    shows up as a test failure rather than a silently different dataset.
    """
    population = (
        ["2.02,9.01"] * 38 + ["5.02,9.01"] * 19 + ["5.07"] * 11 + ["9.01"] * 7 +
        ["5.03"] * 4 + ["7.01,9.01"] * 10 + ["1.01,9.01"] * 7 + ["2.01,9.01"] * 4
    )
    kept = sum(1 for items in population if filters.is_relevant(items))
    dropped = 1 - kept / len(population)
    print(f"\nfiling-level reduction on representative mix: {dropped:.1%}")
    assert 0.75 <= dropped <= 0.85
