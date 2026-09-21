# Architecture

```
                    ┌─────────────────────────────────────┐
                    │  EDGAR quarterly full index         │
                    │  /Archives/edgar/full-index/...     │
                    └───────────────┬─────────────────────┘
                                    │  1 request per quarter
                    ┌───────────────▼─────────────────────┐
                    │  universe.py    distinct CIKs       │
                    │  discovery.py   8-K filing list     │
                    └───────────────┬─────────────────────┘
                                    │
                    ┌───────────────▼─────────────────────┐
                    │  filters.py — item-number filter    │
                    │  runs on metadata, before download  │
                    └───────┬───────────────────┬─────────┘
                       dropped               kept
                    (never fetched)            │
                                    ┌──────────▼──────────┐
                                    │  client.py          │
                                    │  rate limit + cache │
                                    └──────────┬──────────┘
                                    ┌──────────▼──────────┐
                                    │  cleaning.py        │
                                    │  markup, header,    │
                                    │  exhibits, boilerplate
                                    └──────────┬──────────┘
                                    ┌──────────▼──────────┐
                                    │  classify.py        │
                                    │  money.py           │
                                    └──────────┬──────────┘
                                    ┌──────────▼──────────┐
                                    │  transform.py       │
                                    │  schema.py          │
                                    │  load.py → csv/parquet
                                    └─────────────────────┘
```

## Design decisions worth explaining

**Why the item filter comes before the fetch.** It's the difference between a
run that takes hours and one that takes most of a day. Filtering after download
would produce the same dataset at roughly five times the cost.

**Why the index route and the submissions route both exist.** The quarterly
index returns thousands of filings per request, which is the only practical way
to do bulk work — but it carries no item numbers. The submissions API carries
item numbers but costs one request per company. Bulk runs use the index and
recover item numbers from the document text; targeted runs use submissions.

**Why threads and not asyncio.** The work is network-bound, so threads are
enough, and the whole thing stays debuggable with a normal stack trace. The
rate limiter is a lock-guarded token bucket shared by all workers, so
concurrency never pushes the outbound rate past the SEC's ceiling — adding
workers changes latency hiding, not request rate.

**Why the cache is on disk and keyed by URL.** Re-running a job after a crash,
or re-measuring noise on a quarter already fetched, should cost nothing.
Combined with the JSONL checkpoint, a failed run resumes rather than restarts.

**Why cue-based classification rather than a model.** There is no labelled
corpus of 8-K event types to train on; building one large enough would have
been the entire project. Cues are transparent, and the `evidence` column makes
every classification auditable. The trade-off is recall on obliquely worded
announcements, which is recorded in the README's known issues.

## Failure handling

- HTTP 429 backs off exponentially rather than retrying hard. A 429 means the
  limiter drifted; retrying aggressively extends the block.
- A filing that fails after retries increments an error counter and is skipped.
  One bad document doesn't end a run of 25,000.
- Progress is checkpointed to JSONL after every batch, including filings that
  were dropped, so a resumed run doesn't re-fetch them.
