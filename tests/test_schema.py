import pandas as pd

from corpevents import schema


def _row(**overrides):
    base = {"cik": "0000912345", "company": "Meridian Systems Inc",
            "filing_date": "2025-10-14", "accession": "a-1", "items": "1.01",
            "event_type": "acquisition", "confidence": 0.8, "deal_value_usd": 2.4e9,
            "counterparty": "Calderon Technologies Inc", "evidence": "{}",
            "chars_in": 1000, "chars_out": 200, "url": "https://example.invalid"}
    base.update(overrides)
    return base


def test_empty_frame_has_the_declared_columns():
    assert list(schema.empty_frame().columns) == list(schema.COLUMNS)


def test_coerce_sets_dtypes():
    frame = schema.coerce(pd.DataFrame([_row()]))
    assert pd.api.types.is_datetime64_any_dtype(frame["filing_date"])
    assert frame["deal_value_usd"].dtype == "float64"


def test_validate_passes_on_a_clean_frame():
    assert schema.validate(schema.coerce(pd.DataFrame([_row()]))) == []


def test_validate_flags_unknown_event_type():
    frame = schema.coerce(pd.DataFrame([_row(event_type="spinoff")]))
    assert any("unknown event_type" in p for p in schema.validate(frame))


def test_validate_flags_duplicate_accessions():
    frame = schema.coerce(pd.DataFrame([_row(), _row()]))
    assert any("duplicate" in p for p in schema.validate(frame))


def test_validate_flags_a_launch_carrying_a_deal_value():
    frame = schema.coerce(pd.DataFrame([_row(event_type="product_launch")]))
    assert any("product launches" in p for p in schema.validate(frame))


def test_coerce_adds_missing_columns():
    frame = schema.coerce(pd.DataFrame([{"cik": "1", "event_type": "acquisition"}]))
    assert list(frame.columns) == list(schema.COLUMNS)
