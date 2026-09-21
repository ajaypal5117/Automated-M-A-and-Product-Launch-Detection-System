.PHONY: install test lint universe run noise noise-fixtures throughput label evaluate clean

install:
pip install -r requirements-dev.txt

test:
pytest -q

lint:
ruff check src scripts tests

# Build the company universe from the quarterly indexes.
universe:
python scripts/build_universe.py --from 2005 --to 2025

# One quarter of 8-Ks, resumable.
run:
python scripts/run_pipeline.py --quarter 2025Q2 --checkpoint out/ckpt.jsonl

# Noise reduction measured on a live sample.
noise:
python scripts/measure_noise.py --quarter 2025Q2 --sample 500

# Same measurement on the committed fixtures - no network needed.
noise-fixtures:
python scripts/noise_fixtures.py

throughput:
python scripts/measure_throughput.py --quarter 2025Q2 --n 400 --no-cache

label:
python scripts/label_sample.py --input out/events.csv --n 100

evaluate:
python scripts/evaluate.py --labels eval/gold/labels.csv

clean:
rm -rf out .pytest_cache .ruff_cache
find . -name __pycache__ -type d -exec rm -rf {} +
