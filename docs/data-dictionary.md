# Output schema

One row per detected corporate event. Declared in `src/corpevents/schema.py`
and enforced by `schema.coerce` before anything is written.

| Column | Type | Description |
|---|---|---|
| `cik` | string | SEC Central Index Key, zero-padded to 10 digits. Stable company identifier across name changes. |
| `company` | string | Registrant name as filed. |
| `filing_date` | datetime | Date the 8-K was accepted by EDGAR, not the date of the underlying event. |
| `accession` | string | Accession number. Primary key — `schema.validate` flags duplicates. |
| `items` | string | 8-K item numbers that let the filing through the filter. Recovered from the document text when metadata didn't carry them. |
| `event_type` | string | One of `acquisition`, `merger`, `divestiture`, `product_launch`. |
| `confidence` | float | 0.45–0.95, from weighted cue density. Not a probability — an ordering. |
| `deal_value_usd` | float | Headline consideration in USD. Null for product launches by design, and null when no amount was disclosed. |
| `counterparty` | string | The acquired, merging or divested entity where the text names one. |
| `evidence` | string (JSON) | Which cue phrases fired and how often. This is what makes a classification auditable. |
| `chars_in` | Int64 | Raw filing size in characters. |
| `chars_out` | Int64 | Size after cleaning. `1 - chars_out/chars_in` is the per-filing noise reduction. |
| `url` | string | Link to the source filing on EDGAR. Every row traces back to a document. |

## Notes on specific fields

**`confidence` is an ordering, not a probability.** It comes from summed cue
weights passed through a saturating function. A 0.9 row is more likely correct
than a 0.6 row; it does not mean 90% of such rows are correct.

**`deal_value_usd` is the largest qualifying amount in the document.** This is
right for headline consideration and wrong when a filing describes several
transactions. Amounts adjacent to disqualifying context (per-share prices,
revenue, credit facilities) are excluded — see `money.headline_amount`.

**`filing_date` is not the event date.** 8-Ks are due within four business days
of the triggering event, so the announcement usually precedes the filing by one
to four days. For event-study work, the press release date inside the document
is the better anchor and is not currently extracted.

**`evidence` exists so classifications can be argued with.** When a row looks
wrong, that column shows exactly which phrases caused it, which turns "the
classifier is bad" into a specific fixable cue weight.
