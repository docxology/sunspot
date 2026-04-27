"""
NOAA SWPC text products (recent window).

- ``daily-solar-indices.txt``: last ~30 days, includes F10.7 and a sunspot number.

Use long-history F10.7 and geomagnetic series from :mod:`sunspot.datasets.omni`.
"""

from __future__ import annotations

import io
import logging
import re
from typing import TextIO

import pandas as pd

from sunspot.datasets.cache import ensure_cached_url

_LOG = logging.getLogger(__name__)

DAILY_SOLAR_INDICES_URL = "https://services.swpc.noaa.gov/text/daily-solar-indices.txt"


def load_noaa_daily_solar_indices(
    text: str | None = None,
    *,
    url: str = DAILY_SOLAR_INDICES_URL,
    cache: bool = True,
) -> pd.DataFrame:
    """
    Parse NOAA daily solar indices (recent days).

    Output columns: ``f107``, ``solar_spot_number_swpc`` (from product).
    """
    if text is None:
        _LOG.info("NOAA SWPC: %s", url)
        if cache:
            p = ensure_cached_url(url, suffix=".txt")
            text = p.read_text(encoding="utf-8", errors="replace")
        else:
            import httpx

            with httpx.Client(timeout=60.0, follow_redirects=True) as c:
                r = c.get(url)
                r.raise_for_status()
                text = r.text
    out = _parse_daily_solar_indices(io.StringIO(text))
    _LOG.debug("NOAA SWPC: parsed %s rows", len(out))
    return out


def _parse_daily_solar_indices(f: TextIO) -> pd.DataFrame:
    rows: list[tuple[pd.Timestamp, float, float]] = []
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith(":"):
            continue
        m = re.match(
            r"^(\d{4})\s+(\d{2})\s+(\d{2})\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+",
            line,
        )
        if not m:
            continue
        y, mo, d, f107, ssn = m.groups()
        ts = pd.Timestamp(int(y), int(mo), int(d), tz="UTC").tz_localize(None).normalize()
        f107_v = float(f107)
        ssn_v = float(ssn)
        if f107_v < 0 or f107_v == -999:
            f107_v = float("nan")
        if ssn_v < 0 or ssn_v == -999:
            ssn_v = float("nan")
        rows.append((ts, f107_v, ssn_v))
    if not rows:
        return pd.DataFrame(columns=["f107", "solar_spot_number_swpc"])
    out = pd.DataFrame(rows, columns=["date", "f107", "solar_spot_number_swpc"])
    out = out.set_index("date").sort_index()
    out.index.name = "date"
    return out
