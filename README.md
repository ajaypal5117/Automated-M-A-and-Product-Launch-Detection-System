# Automated M&A and Product Launch Detection System

A Corporate Events Intelligence Pipeline over SEC 8-K filings.

Detects M&A activity and product launches in SEC 8-K filings. Discovers filings
from EDGAR's quarterly indexes, drops the ones that structurally can't contain
an event before downloading them, cleans the rest down to narrative text, and
writes a structured dataset with deal values, counterparties and a link back to
every source filing.

```
quarterly index --> item-number filter --> fetch --> clean --> classify --> CSV / parquet
                    (metadata only,                 (~89% of                + run report
                     nothing downloaded)             characters)
```

## The idea

Roughly 60,000 8-Ks are filed a year and almost none of them are interesting.
Most are earnings releases (Item 2.02), officer changes (5.02) and shareholder
votes (5.07) - categories that *cannot* contain an acquisition announcement.
The SEC tags every filing with those item numbers in metadata, so you can throw
out most of the corpus before spending a single byte of bandwidth on it.

What survives is still mostly not prose: SGML headers, cover-page checkboxes,
forward-looking-statement disclaimers, and base64 exhibits that are frequently
larger than the filing. Stripping those leaves a few hundred characters of
actual announcement text, which is small enough to classify with transparent
rules instead of a model.

## Quick start

```bash
pip install -r requirements-dev.txt
cp .env.example .env          # set EDGAR_USER_AGENT - the SEC 403s without it

pytest                              # 54 tests, no network required
python scripts/noise_fixtures.py    # noise reduction on the committed fixtures

python scripts/run_pipeline.py --tickers AAPL MSFT NVDA --since 2024-01-01
```

Bulk run over a full quarter, resumable:

```bash
python scripts/run_pipeline.py --quarter 2025Q2 --checkpoint out/ckpt.jsonl
```

## Reproducing the numbers

Every figure this project reports has a command that produces it. Nothing is
hardcoded in the README.

| What | Command | Status |
|---|---|---|
| Noise reduction, character level | `python scripts/noise_fixtures.py` | measured - 89.0% mean on committed fixtures |
| Noise reduction, filing level | `pytest -s -k representative_item_mix` | measured - 79.0% on the documented item mix |
| Noise reduction on live filings | `python scripts/measure_noise.py --quarter 2025Q2` | needs network |
| Company universe size | `python scripts/build_universe.py --from 2005 --to 2025` | needs network (~80 requests, about a minute) |
| Throughput and projected runtime | `python scripts/measure_throughput.py --quarter 2025Q2` | needs network |
| Field-level accuracy | `scripts/label_sample.py` then `scripts/evaluate.py` | needs a hand-labelled sample |

The first two run offline against `data/fixtures/`, which is why those fixtures
are realistic submissions with headers and exhibits rather than toy snippets.
The rest need EDGAR access; `measure_noise.py` and `measure_throughput.py`
print the measured values so they can be pasted here.

Accuracy deliberately cannot be produced by a script alone. Scoring the
pipeline against its own output would measure agreement with itself, so
`label_sample.py` draws a stratified sample and the judgement columns get
filled in by hand. [`docs/evaluation.md`](docs/evaluation.md) defines what each
metric means.

## Output

```
cik,company,filing_date,accession,items,event_type,confidence,deal_value_usd,counterparty,...
0000912345,MERIDIAN SYSTEMS INC,2025-10-14,0001628280-25-031447,"1.01,9.01",merger,0.93,2400000000.0,Calderon Technologies Inc,...
```

Full field descriptions in [`docs/data-dictionary.md`](docs/data-dictionary.md).
Two fields worth calling out:

- **`evidence`** records which cue phrases fired and how often, so any
  classification can be argued with rather than taken on faith.
- **`deal_value_usd`** is null for product launches by design. An early version
  reported $4,200 for a launch because that was the product's unit price;
  `tests/test_transform.py` pins the fix.

## How it's put together

```
src/corpevents/
  config.py      settings, all from the environment
  client.py      rate-limited HTTP, thread-shared token bucket, disk cache
  universe.py    company universe from the quarterly full indexes
  discovery.py   8-K discovery - bulk via index, targeted via submissions API
  filters.py     stage 1 noise reduction: item-number filter
  cleaning.py    stage 2: strip header, markup, exhibits, boilerplate
  classify.py    weighted cue scoring + counterparty extraction
  money.py       dollar amount parsing with context exclusion
  transform.py   filing -> dataset row
  schema.py      the output contract, plus validation
  load.py        CSV / parquet writing and run summary
  pipeline.py    threaded orchestration with JSONL checkpointing
```

Design decisions and the reasoning behind them are in
[`docs/architecture.md`](docs/architecture.md). The short version:

- The item filter runs **before** the fetch. That ordering is the difference
  between a run taking hours and taking most of a day.
- Threads, not asyncio - the work is network-bound and stack traces stay
  readable. One global rate limiter means adding workers hides latency without
  raising the outbound request rate.
- Cue-based classification rather than a trained model, because no labelled
  corpus of 8-K event types exists and building one would have been the entire
  project. The trade-off is recall, recorded below.

## Rate limiting

The SEC allows 10 requests/second and blocks the IP for about ten minutes if
you exceed it. `client.py` holds a lock-guarded token bucket shared by every
worker thread, so the total outbound rate stays under the ceiling no matter how
many workers run. A 429 backs off exponentially rather than retrying hard,
since retrying aggressively just extends the block.

Responses are cached to `.cache/` keyed by URL, and runs checkpoint to JSONL
after every batch, so a crashed run resumes instead of restarting.

## Known issues

- **Recall isn't measured.** Doing it honestly needs a sample of filings known
  to contain events, which means reading a lot of filings that don't. This is
  the biggest gap in the evaluation.
- `deal_value_usd` takes the largest qualifying amount, which is correct for
  headline consideration and wrong when one filing covers several transactions.
- Counterparty extraction is a regex over capitalised spans. Names not shaped
  like "acquisition of X Inc." are missed.
- `filing_date` is the EDGAR acceptance date, not the event date - 8-Ks are due
  within four business days, so announcements typically precede the filing.
  For event studies the press release date inside the document is the better
  anchor, and it isn't extracted yet.
- Only 8-Ks. Deal specifics often land later in S-4 and DEFM14A filings.
- The item mix used for the filing-level measurement is an assumption
  documented in [`docs/noise-reduction.md`](docs/noise-reduction.md), not a
  figure sampled from EDGAR. `scripts/measure_noise.py` replaces it with a
  measured one.

## Data source

SEC EDGAR, public domain. Usage follows the SEC's
[access policy](https://www.sec.gov/os/webmaster-faq#developers): descriptive
User-Agent, rate limited, responses cached so the same document is never
fetched twice.

## Author

Pal Ajay Ramsagar - github.com/ajaypal5117
