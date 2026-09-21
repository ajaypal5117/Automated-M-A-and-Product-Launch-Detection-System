# Measuring data accuracy

## What is being measured

**Field-level accuracy**: across a hand-labelled sample, the share of extracted
field values a human agreed with. Reported per field, because the failure modes
differ sharply — `event_type` is wrong when cue language is ambiguous, while
`deal_value_usd` is wrong when a filing discusses more than one transaction.

**Precision** is tracked separately. A row can carry the correct `event_type`
and still be a false positive if the filing wasn't an event at all. The
`is_actually_an_event` column catches that; without it a classifier that
labelled every filing "acquisition" could post respectable field accuracy.

Recall is **not** measured. Doing so honestly needs a sample of filings known
to contain events, which means reading a large number of filings that mostly
don't — several days of work. This is the most significant gap in the
evaluation and is listed as such in the README.

## Procedure

```bash
# 1. Produce a dataset
python scripts/run_pipeline.py --quarter 2025Q2 --checkpoint out/ckpt.jsonl

# 2. Draw a stratified sample for labelling
python scripts/label_sample.py --input out/events.csv --n 100

# 3. Label by hand: open eval/gold/labels.csv, read each filing via its url
#    column, fill in the judgement columns.

# 4. Score
python scripts/evaluate.py --labels eval/gold/labels.csv
```

Step 3 is the part that can't be automated. Using the pipeline's own output as
ground truth would measure nothing at all.

## Why stratified rather than random

The event distribution is heavily skewed toward acquisitions. A random sample
of 100 gives roughly 80 acquisitions and a handful of divestitures, so the
overall number says almost nothing about the rare classes.
`scripts/label_sample.py` samples evenly per event type; per-class accuracy is
reported alongside the overall figure.

## Judgement columns

| Column | Values | Meaning |
|---|---|---|
| `event_type_correct` | y / n | Is the classification right? |
| `deal_value_correct` | y / n / na | Does the value match the filing? `na` when none was disclosed. |
| `counterparty_correct` | y / n / na | Is the named party the actual counterparty? |
| `is_actually_an_event` | y / n | Is this a real corporate event, or a false positive? |
| `notes` | free text | Why it failed. These become the failure-analysis section of the report. |

`na` rows are excluded from the denominator rather than counted as correct.

## Reproducibility

`scripts/evaluate.py` writes `eval/accuracy_report.md` with per-field rates,
per-class breakdown, and the failure notes. The label file is the evidence; the
report is derived from it and can be regenerated at any time.
