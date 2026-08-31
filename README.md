# Automated M&A and Product Launch Detection System

Pulls 8-K filings from SEC EDGAR, throws away the ones that structurally can't
contain a corporate event, parses the rest, and writes a structured dataset of
acquisitions, mergers, divestitures and product launches with their disclosed
deal values.

```
company_tickers.json ─▶ submissions API ─▶ item-number filter ─▶ fetch document
                                                 (80% dropped)          │
                                                                        ▼
                                    CSV ◀── pandas ◀── classify + extract value
```

## Where the noise reduction comes from

Most 8-Ks are Item 2.02 earnings releases, Item 5.02 officer changes and Item
5.07 shareholder votes. None of them can contain an M&A announcement. The SEC
already tags every filing with its item numbers in the submissions API, so the
filter runs on metadata **before** any document is downloaded. On a realistic
item mix that drops about 80% of filings, and the 80% that never gets fetched is
also 80% of the runtime, since download is the slow step.

Surviving filings (1.01, 2.01, 7.01, 8.01) get their text stripped of HTML,
scanned for M&A and launch cues, and scored.

## Rate limiting

The SEC allows 10 requests/second and rejects requests without a `User-Agent`
containing contact details. Both are handled in `edgar.py`; `EDGAR_USER_AGENT`
is required rather than optional because the alternative is a 403. Responses are
cached to `.cache/`, so re-running a job re-downloads nothing.

That ceiling is what sets the runtime: ~25,000 filings at 10/s with the item
filter in front works out to a few hours, not minutes.

## Running it

```bash
pip install -r requirements.txt
cp .env.example .env          # set EDGAR_USER_AGENT — required

python main.py --tickers AAPL MSFT NVDA --since 2024-01-01
python main.py --limit 500 --since 2025-01-01 --out out/events.csv
python main.py --summary out/events.csv
```

Output:

```
2 events | disclosed value $2.4B

event_type
acquisition       1
product_launch    1

Largest disclosed events:
  $   2.40B  2025-10-14  Meridian Systems, Inc.    acquisition
```

## Output schema

| Column | Notes |
|---|---|
| `cik`, `company`, `filing_date`, `accession`, `url` | provenance, back to the source filing |
| `event_type` | acquisition, merger, divestiture, product_launch |
| `confidence` | from cue density |
| `deal_value_usd` | largest disclosed figure; **null for launches**, where the biggest number is usually a unit price |
| `counterparty` | acquired/merging entity where named |
| `items` | the 8-K items that let it through the filter |

## Tests

```bash
pytest -s
```

14 tests, no network — they run against the fixtures in `samples/`.
`test_noise_reduction_rate` measures the filter against a labelled item
distribution and prints the score rather than asserting a number from nowhere.

## Layout

```
├── main.py           orchestration + CLI + pandas output
├── edgar.py          EDGAR client: rate limit, User-Agent, disk cache
├── extract.py        item filter, HTML cleaning, classification, money parsing
├── test_extract.py
└── samples/          three 8-K fixtures: acquisition, launch, earnings
```

## Limits

- Classification is cue-based, not a model. It's tuned for precision on clear
  announcements and will miss obliquely worded ones.
- `deal_value_usd` takes the largest figure in the document, which is right for
  headline consideration but wrong when a filing discusses several transactions.
- Counterparty extraction is a regex over capitalised spans and misses names
  that don't follow the usual "acquisition of X Inc." shape.
- Only 8-Ks. Merger specifics often land in later S-4s and DEFM14As.
