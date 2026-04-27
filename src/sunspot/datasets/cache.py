"""Local cache for downloaded science text/CSV products."""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any

import httpx

_LOG = logging.getLogger(__name__)


def default_cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    if base:
        return Path(base) / "sunspot"
    return Path.home() / ".cache" / "sunspot"


def cache_path_for_url(url: str, suffix: str) -> Path:
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return default_cache_dir() / "url" / f"{h}{suffix}"


def ensure_cached_url(
    url: str,
    *,
    suffix: str = ".txt",
    timeout_s: float = 60.0,
    client: httpx.Client | None = None,
) -> Path:
    """Download ``url`` to a stable cache path if missing."""
    out = cache_path_for_url(url, suffix)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.is_file() and out.stat().st_size > 0:
        _LOG.debug("cache hit %s %s B", out.name, out.stat().st_size)
        return out
    _LOG.info("cache miss, fetching %s", url)
    c = client or httpx.Client(timeout=timeout_s, follow_redirects=True)
    try:
        r = c.get(url)
        r.raise_for_status()
        out.write_bytes(r.content)
    finally:
        if client is None:
            c.close()
    _LOG.info("wrote cache %s %s B", out, out.stat().st_size)
    return out


def read_text_cached(url: str, **kwargs: Any) -> str:
    path = ensure_cached_url(url, **kwargs)
    return path.read_text(encoding="utf-8", errors="replace")
