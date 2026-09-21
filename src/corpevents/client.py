"""HTTP layer for EDGAR.

Everything that talks to sec.gov goes through here, which is the only way to
hold one global rate limit while several worker threads are running. The
limiter is a token bucket behind a lock: threads block on it instead of each
keeping their own timer, so the total outbound rate stays under the SEC's
ceiling regardless of worker count.

Two hosts, different jobs:
  data.sec.gov - JSON metadata (submissions)
  www.sec.gov  - filing documents and the quarterly full indexes
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time

import requests

from .config import settings

log = logging.getLogger(__name__)

DATA_HOST = "https://data.sec.gov"
WWW_HOST = "https://www.sec.gov"


class RateLimiter:
    """Token bucket shared across threads."""

    def __init__(self, per_second):
        self.interval = 1.0 / per_second
        self._lock = threading.Lock()
        self._next_slot = 0.0

    def acquire(self):
        with self._lock:
            now = time.monotonic()
            wait = max(0.0, self._next_slot - now)
            self._next_slot = max(now, self._next_slot) + self.interval
        if wait:
            time.sleep(wait)


_limiter = RateLimiter(settings.rate_limit)
_local = threading.local()


def _session():
    """One Session per thread - requests.Session isn't safe to share."""
    if not hasattr(_local, "session"):
        s = requests.Session()
        s.headers.update(
            {"User-Agent": settings.require_user_agent(), "Accept-Encoding": "gzip, deflate"}
        )
        _local.session = s
    return _local.session


def _cache_path(url):
    digest = hashlib.sha1(url.encode()).hexdigest()[:16]
    tail = url.rsplit("/", 1)[-1][:60].replace("?", "_")
    return settings.cache_dir / digest[:2] / f"{digest}_{tail}"


class Stats:
    """Counters for the throughput measurement."""

    def __init__(self):
        self._lock = threading.Lock()
        self.requests = 0
        self.cache_hits = 0
        self.bytes = 0
        self.errors = 0

    def bump(self, name, amount=1):
        with self._lock:
            setattr(self, name, getattr(self, name) + amount)

    def snapshot(self):
        with self._lock:
            return {"requests": self.requests, "cache_hits": self.cache_hits,
                    "bytes": self.bytes, "errors": self.errors}

    def reset(self):
        with self._lock:
            self.requests = self.cache_hits = self.bytes = self.errors = 0


stats = Stats()


def get(url, as_json=False, use_cache=True):
    """Fetch a URL. Cache hits skip both the network and the rate limiter."""
    cached = _cache_path(url)
    if use_cache and cached.exists():
        stats.bump("cache_hits")
        text = cached.read_text(encoding="utf-8", errors="replace")
        return json.loads(text) if as_json else text

    last_error = None
    for attempt in range(settings.max_retries):
        _limiter.acquire()
        try:
            r = _session().get(url, timeout=settings.timeout)
            if r.status_code == 429:
                # A 429 means we drifted over the limit. Backing off is the fix;
                # retrying hard just extends the block.
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 404:
                raise FileNotFoundError(url)
            r.raise_for_status()
            text = r.text
            stats.bump("requests")
            stats.bump("bytes", len(text))
            if use_cache:
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_text(text, encoding="utf-8")
            return json.loads(text) if as_json else text
        except FileNotFoundError:
            raise
        except Exception as e:
            last_error = e
            time.sleep(0.5 * (attempt + 1))

    stats.bump("errors")
    raise RuntimeError(f"failed after {settings.max_retries} attempts: {url} ({last_error})")
