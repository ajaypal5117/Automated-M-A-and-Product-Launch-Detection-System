import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

FIXTURES = ROOT / "data" / "fixtures"


@pytest.fixture
def fixture():
    def _read(name):
        return (FIXTURES / name).read_text()
    return _read


@pytest.fixture
def filing():
    def _make(**overrides):
        base = {"cik": "0000912345", "company": "Meridian Systems Inc",
                "filing_date": "2025-10-14", "accession": "0001628280-25-031447",
                "items": None, "url": "https://example.invalid/doc.txt"}
        base.update(overrides)
        return base
    return _make
