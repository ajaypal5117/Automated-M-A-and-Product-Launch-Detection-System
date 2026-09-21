# Working notes

Running log of things that broke, things I decided, and things still open.

## Decisions

**Item filter before fetch, not after.** First version downloaded everything and
filtered on the parsed text. Same dataset, roughly five times the wall clock.
Moving the filter onto the metadata was the single biggest change.

**Two noise numbers instead of one.** Tried to report a single "noise reduction"
figure and it was meaningless — a filing dropped on metadata costs nothing,
while one cleaned after download cost a round trip. They're reported separately.

**Threads over asyncio.** Network-bound work, and I wanted readable stack
traces. The constraint is the SEC's 10 req/s ceiling, not CPU, so the rate
limiter has to be global. Per-thread timers would have multiplied the rate by
the worker count.

**Cue weights, not a classifier.** No labelled corpus exists. Weighted phrases
with an `evidence` column beat a black box I can't debug at this scale.

## Bugs worth remembering

- Product launches were getting a `deal_value_usd` — the regex grabbed the
  product's unit price ($4,200) and it inflated the totals. Launches now carry
  no deal value; `test_launch_carries_no_deal_value` pins it.
- The amount-exclusion context window was symmetric, so "revenue" appearing
  *after* a figure disqualified it. Qualifiers nearly always precede the number
  ("revenue of $900 million"); the one that follows is "per share". Window is
  now 60 chars back, 20 forward.
- Resuming from a checkpoint reported zero events while holding a full
  checkpoint file — the counters only tracked the current session. They now
  seed from the checkpoint.
- `zip()` over the submissions arrays assumed equal lengths. EDGAR has been
  consistent so far but it's `strict=False` now rather than implicit.

## Open

- [ ] Extract the press release date from the document; `filing_date` is the
      acceptance date and is 1-4 days late for event-study use.
- [ ] Recall measurement. Needs a positives-known sample; see docs/evaluation.md.
- [ ] Cue weights were set by hand. Once a labelled set exists they could be
      fit properly.
- [ ] Multi-transaction filings break the "largest amount" heuristic. Probably
      needs sentence-level attribution rather than a document-level max.
- [ ] S-4 / DEFM14A would add deal terms that 8-Ks omit.
