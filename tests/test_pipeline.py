"""Pipeline tests with the network stubbed out.

These cover the parts that only break under concurrency or on restart:
checkpoint resume, error isolation, and the aggregate counters the run report
prints.
"""

import json

import pytest

from corpevents import client, pipeline


@pytest.fixture
def stub_network(monkeypatch, fixture):
    """Map fake URLs to fixture documents."""
    documents = {
        "url://acq": fixture("8k_acquisition.txt"),
        "url://launch": fixture("8k_launch.txt"),
        "url://earnings": fixture("8k_earnings.txt"),
        "url://dividend": fixture("8k_dividend.txt"),
        "url://broken": None,
    }

    def fake_get(url, as_json=False, use_cache=True):
        body = documents.get(url)
        if body is None:
            raise RuntimeError("simulated network failure")
        return body

    monkeypatch.setattr(pipeline, "get", fake_get)
    monkeypatch.setattr(client, "get", fake_get)
    return documents


def _filings():
    return [
        {"cik": "1", "company": "Meridian", "filing_date": "2025-10-14",
         "accession": "a1", "items": "1.01,9.01", "url": "url://acq"},
        {"cik": "2", "company": "Northgate", "filing_date": "2025-09-03",
         "accession": "a2", "items": "7.01", "url": "url://launch"},
        {"cik": "1", "company": "Meridian", "filing_date": "2025-07-22",
         "accession": "a3", "items": "2.02,9.01", "url": "url://earnings"},
        {"cik": "1", "company": "Meridian", "filing_date": "2025-02-10",
         "accession": "a4", "items": "8.01", "url": "url://dividend"},
    ]


def test_run_extracts_only_real_events(stub_network):
    records, stats = pipeline.run(_filings())
    assert stats.processed == 4
    assert stats.events == 2
    assert stats.dropped_item_filter == 1
    assert stats.dropped_no_cues == 1
    assert {r["event_type"] for r in records} == {"merger", "product_launch"}


def test_a_failing_filing_does_not_kill_the_run(stub_network):
    filings = _filings() + [{"cik": "9", "company": "Broken", "filing_date": "2025-01-01",
                             "accession": "a9", "items": "1.01", "url": "url://broken"}]
    records, stats = pipeline.run(filings)
    assert stats.errors == 1
    assert stats.events == 2          # the other four still processed


def test_checkpoint_lets_a_run_resume(stub_network, tmp_path):
    checkpoint = tmp_path / "ckpt.jsonl"
    pipeline.run(_filings()[:2], checkpoint=str(checkpoint))

    lines = checkpoint.read_text().strip().splitlines()
    assert len(lines) == 2

    # Second pass over the full set: the first two are skipped, not redone.
    records, stats = pipeline.run(_filings(), checkpoint=str(checkpoint))
    assert stats.processed == 4
    assert stats.events == 2
    assert len(records) == 2


def test_checkpoint_records_dropped_filings_too(stub_network, tmp_path):
    checkpoint = tmp_path / "ckpt.jsonl"
    pipeline.run(_filings(), checkpoint=str(checkpoint))
    entries = [json.loads(line) for line in checkpoint.read_text().strip().splitlines()]
    assert sum(1 for e in entries if e.get("event_type") is None) == 2


def test_run_report_reports_both_reduction_rates(stub_network):
    _, stats = pipeline.run(_filings())
    report = stats.as_dict()
    assert report["filing_level_reduction"] == 0.5      # 2 of 4 dropped
    assert 0.5 < report["character_level_reduction"] < 1.0
    assert report["filings_per_hour"] > 0
