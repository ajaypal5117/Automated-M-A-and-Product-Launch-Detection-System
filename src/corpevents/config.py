"""Runtime configuration, all of it from the environment.

Kept in one place so the pipeline, the measurement scripts and the tests can't
drift apart on things like the rate limit or the cache location.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]


def _s(key, default):
    v = os.getenv(key)
    return default if v is None or not v.strip() else v.strip()


def _i(key, default):
    try:
        return int(_s(key, str(default)))
    except ValueError:
        return default


def _f(key, default):
    try:
        return float(_s(key, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # SEC requires a contact string; requests without one get 403'd.
    user_agent: str = field(default_factory=lambda: _s("EDGAR_USER_AGENT", ""))

    # Published ceiling is 10 req/s. Going over gets the IP blocked for ~10 min,
    # so the default sits just under it.
    rate_limit: float = field(default_factory=lambda: _f("RATE_LIMIT", 9.0))
    workers: int = field(default_factory=lambda: _i("WORKERS", 6))
    timeout: int = field(default_factory=lambda: _i("HTTP_TIMEOUT", 30))
    max_retries: int = field(default_factory=lambda: _i("MAX_RETRIES", 3))

    cache_dir: Path = field(default_factory=lambda: ROOT / _s("CACHE_DIR", ".cache"))
    out_dir: Path = field(default_factory=lambda: ROOT / _s("OUT_DIR", "out"))

    def require_user_agent(self):
        if not self.user_agent:
            raise RuntimeError(
                "EDGAR_USER_AGENT is unset. The SEC rejects anonymous requests. "
                "Set it to 'Name email@domain' in .env - see .env.example."
            )
        return self.user_agent


settings = Settings()
