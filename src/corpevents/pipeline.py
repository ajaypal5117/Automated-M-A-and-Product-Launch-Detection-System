"""Pipeline orchestration.

Runs discovery, then processes filings through a thread pool. Threads help here
despite the GIL because the work is almost entirely network wait; the global
rate limiter in `client` is what stops the extra concurrency from exceeding the
SEC's ceiling.

Progress is checkpointed to a JSONL file after every batch. A run over tens of
thousands of filings will hit a transient network failure at some point, and
restarting from zero each time is not workable.
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from . import discovery, transform
from .client import get, stats
from .config import settings

log = logging.getLogger(__name__)


@dataclass
class RunStats:
    discovered: int = 0
    processed: int = 0
    dropped_item_filter: int = 0
    dropped_no_cues: int = 0
    events: int = 0
    errors: int = 0
    chars_in: int = 0
    chars_out: int = 0
    started: float = field(default_factory=time.time)

    @property
    def elapsed(self):
        return max(time.time() - self.started, 1e-6)

    @property
    def filings_per_hour(self):
        return self.processed / self.elapsed * 3600

    def as_dict(self):
        noise = (1 - self.chars_out / self.chars_in) if self.chars_in else 0.0
        dropped = self.dropped_item_filter + self.dropped_no_cues
        return {
            "discovered": self.discovered,
            "processed": self.processed,
            "events": self.events,
            "dropped_item_filter": self.dropped_item_filter,
            "dropped_no_cues": self.dropped_no_cues,
            "filing_level_reduction": round(dropped / self.processed, 4) if self.processed else 0,
            "character_level_reduction": round(noise, 4),
            "errors": self.errors,
            "elapsed_seconds": round(self.elapsed, 1),
            "filings_per_hour": round(self.filings_per_hour, 1),
            "http": stats.snapshot(),
        }


def _load_checkpoint(path):
    if not path or not Path(path).exists():
        return set(), []
    seen, records = set(), []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            seen.add(entry.get("accession"))
            if entry.get("event_type"):
                records.append(entry)
    log.info("resuming: %d filings already processed", len(seen))
    return seen, records


def _process_one(filing):
    raw = get(filing["url"])
    return transform.process(filing, raw)


def run(filings, checkpoint=None, on_progress=None):
    """Process a list of filings. Returns (records, RunStats)."""
    run_stats = RunStats(discovered=len(filings))
    seen, records = _load_checkpoint(checkpoint)

    pending = [f for f in filings if f["accession"] not in seen]
    run_stats.processed = len(seen)
    # Counters describe the whole dataset, not just this session - otherwise a
    # resumed run reports zero events while holding a full checkpoint.
    run_stats.events = len(records)
    log.info("%d filings to process (%d already done)", len(pending), len(seen))

    checkpoint_handle = open(checkpoint, "a", encoding="utf-8") if checkpoint else None

    try:
        with ThreadPoolExecutor(max_workers=settings.workers) as pool:
            futures = {pool.submit(_process_one, f): f for f in pending}

            for done, future in enumerate(as_completed(futures), start=1):
                filing = futures[future]
                try:
                    record, diagnostics = future.result()
                except Exception as e:
                    run_stats.errors += 1
                    log.debug("failed %s: %s", filing["accession"], e)
                    continue

                run_stats.processed += 1
                run_stats.chars_in += diagnostics.get("chars_in", 0)
                run_stats.chars_out += diagnostics.get("chars_out", 0)

                if diagnostics.get("dropped_by") == "item_filter":
                    run_stats.dropped_item_filter += 1
                elif diagnostics.get("dropped_by") == "no_event_cues":
                    run_stats.dropped_no_cues += 1

                if record:
                    records.append(record)
                    run_stats.events += 1

                if checkpoint_handle:
                    line = record or {"accession": filing["accession"], "event_type": None}
                    checkpoint_handle.write(json.dumps(line, default=str) + "\n")
                    if done % 50 == 0:
                        checkpoint_handle.flush()

                if on_progress and done % 100 == 0:
                    on_progress(run_stats)
    finally:
        if checkpoint_handle:
            checkpoint_handle.close()

    return records, run_stats


def discover_quarter(year, quarter, limit=None):
    return discovery.from_index(year, quarter, limit=limit)


def discover_tickers(tickers, since=None, per_company=None):
    filings = []
    for company in discovery.resolve_tickers(tickers):
        filings.extend(
            discovery.from_submissions(company["cik"], since=since, limit=per_company)
        )
    return filings
