"""Cleaning is measured, not eyeballed - these pin the behaviour the noise
reduction figure depends on."""

from corpevents import cleaning


def test_sgml_header_is_removed(fixture):
    text, _ = cleaning.clean(fixture("8k_acquisition.txt"))
    assert "CENTRAL INDEX KEY" not in text
    assert "STANDARD INDUSTRIAL CLASSIFICATION" not in text


def test_embedded_graphic_is_removed(fixture):
    text, _ = cleaning.clean(fixture("8k_acquisition.txt"))
    assert "begin 644" not in text
    assert "ABCDEFGHIJKLMNOP" not in text


def test_style_blocks_do_not_survive_as_text(fixture):
    text, _ = cleaning.clean(fixture("8k_acquisition.txt"))
    assert "font-family:Arial" not in text


def test_cover_page_boilerplate_is_removed(fixture):
    text, _ = cleaning.clean(fixture("8k_acquisition.txt"))
    assert "Check the appropriate box" not in text
    assert "Securities registered pursuant" not in text


def test_forward_looking_disclaimer_is_removed(fixture):
    text, _ = cleaning.clean(fixture("8k_acquisition.txt"))
    assert "Private Securities Litigation Reform" not in text


def test_narrative_survives_cleaning(fixture):
    text, _ = cleaning.clean(fixture("8k_acquisition.txt"))
    assert "Agreement and Plan of Merger" in text
    assert "Calderon Technologies" in text
    assert "$2.4 billion" in text


def test_html_entities_are_decoded(fixture):
    text, _ = cleaning.clean(fixture("8k_acquisition.txt"))
    assert "&nbsp;" not in text and "&quot;" not in text


def test_metrics_are_internally_consistent(fixture):
    raw = fixture("8k_acquisition.txt")
    text, metrics = cleaning.clean(raw)
    assert metrics["chars_in"] == len(raw)
    assert metrics["chars_out"] == len(text)
    assert metrics["chars_removed"] == metrics["chars_in"] - metrics["chars_out"]
    assert 0 <= metrics["reduction"] <= 1


def test_exhibit_heavy_filing_reduces_more_than_a_plain_one(fixture):
    _, with_exhibit = cleaning.clean(fixture("8k_acquisition.txt"))
    _, without = cleaning.clean(fixture("8k_dividend.txt"))
    assert with_exhibit["reduction"] > without["reduction"]


def test_item_numbers_recoverable_from_text(fixture):
    text, _ = cleaning.clean(fixture("8k_divestiture.txt"))
    assert "2.01" in cleaning.find_item_numbers(text)


def test_empty_input_does_not_divide_by_zero():
    text, metrics = cleaning.clean("")
    assert text == "" and metrics["reduction"] == 0.0
