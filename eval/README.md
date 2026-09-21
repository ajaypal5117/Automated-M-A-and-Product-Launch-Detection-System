# Evaluation

`gold/labels.template.csv` shows the expected format. The workflow and the
definition of each metric are in [`../docs/evaluation.md`](../docs/evaluation.md).

`gold/labels.csv` is produced by `scripts/label_sample.py` and then filled in by
hand. It is the evidence behind the accuracy figure; `accuracy_report.md` is
derived from it by `scripts/evaluate.py` and can be regenerated at any time.

Nothing here is auto-labelled. Scoring the pipeline against its own output
would measure agreement with itself.
