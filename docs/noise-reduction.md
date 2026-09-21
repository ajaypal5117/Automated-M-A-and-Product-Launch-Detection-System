# Noise reduction

"Noise" here means everything in an 8-K submission that cannot contain a
corporate event announcement. It gets removed in two stages that reduce
different things, so they're measured separately.

## Stage 1 ??? item-number filter (filing level)

Every 8-K is tagged by the filer with the item numbers it reports under, and
those tags are in the submissions metadata before any document is fetched.
Whole categories are structurally incapable of announcing a transaction:

| Item | Meaning | Kept |
|---|---|---|
| 1.01 | entry into a material definitive agreement | yes |
| 1.02 | termination of a material agreement | yes |
| 2.01 | completion of acquisition or disposition | yes |
| 7.01 | Regulation FD disclosure | yes |
| 8.01 | other events | yes |
| 2.02 | results of operations (earnings release) | no |
| 5.02 | departure/election of officers | no |
| 5.03 | amendments to bylaws | no |
| 5.07 | submission of matters to a vote | no |
| 9.01 | financial statements and exhibits | no |

Because the filter runs on metadata, a dropped filing is never downloaded. The
saving is bandwidth and wall-clock, not just parsing.

`tests/test_filters.py::test_filing_level_reduction_on_a_representative_item_mix`
pins this against an assumed item mix weighted toward the high-volume items
(38% earnings, 19% officer changes, 11% votes, and so on). On that mix the
filter drops **79%** of filings.

That mix is an assumption, documented so it can be argued with. To measure it
on real filings instead:

```bash
python scripts/measure_noise.py --quarter 2025Q2 --sample 500
```

That samples a real quarter and reports the observed rate, along with the
breakdown of why filings were dropped.

## Stage 2 ??? text cleaning (character level)

A filing that survives stage 1 is still mostly not prose. A raw submission
carries an SGML header block, cover-page checkbox boilerplate, forward-looking
statement disclaimers, inline CSS, and base64-encoded exhibits that are often
larger than the filing itself.

Measured on the fixtures in `data/fixtures/`:

| Fixture | Raw | Cleaned | Removed |
|---|---|---|---|
| `8k_acquisition.txt` | 7,670 | 899 | 88.3% |
| `8k_launch.txt` | 7,285 | 560 | 92.3% |
| `8k_earnings.txt` | 6,996 | 257 | 96.3% |
| `8k_divestiture.txt` | 2,404 | 387 | 83.9% |
| `8k_dividend.txt` | 1,562 | 248 | 84.1% |

Mean 89.0%, median 88.3%. Reproduce with `python scripts/noise_fixtures.py`.

Real filings reduce by more than these fixtures, not less ??? production 8-Ks
carry far heavier exhibit payloads than anything reasonable to commit to a
repository.

## Why two numbers rather than one

They answer different questions. Stage 1 says how much work was avoided; stage
2 says how much of a fetched document was signal. Collapsing them into a single
figure would hide that a filing dropped at stage 1 cost nothing, while one
cleaned at stage 2 cost a full round trip.

