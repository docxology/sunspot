"""
NASA GSFC/SPDF OMNI2 hourly flat files, aggregated to daily means.

Cite SPDF/OMNI when using these series. See: https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni/omni2.text

F10.7, Dst, ap-index, and sunspot R are present on each hourly line; daily values
arithmetic-mean the contributing hourly rows (per OMNI's daily-average definition).
"""

from __future__ import annotations

import datetime as dt
import logging
import math
from collections.abc import Iterable

import pandas as pd

from sunspot.datasets.cache import ensure_cached_url

_LOG = logging.getLogger(__name__)

# In-memory cache: repeated metric loads in one correlate() run share one OHLC-style daily frame
_OMNI2_DAILY_MEM: dict[tuple[int, ...], pd.DataFrame] = {}

OMNI2_YEAR_URL = "https://spdf.gsfc.nasa.gov/pub/data/omni/low_res_omni/omni2_{year}.dat"


def _omni2_year_file_url(year: int) -> str:
    return OMNI2_YEAR_URL.format(year=year)


def load_omni2_hourly_year(
    year: int,
    *,
    cache: bool = True,
) -> pd.DataFrame:
    url = _omni2_year_file_url(year)
    _LOG.debug("OMNI2 %s: %s", year, url)
    if cache:
        path = ensure_cached_url(url, suffix=f"_{year}.dat")
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    else:
        import httpx

        with httpx.Client(timeout=120.0, follow_redirects=True) as c:
            r = c.get(url)
            r.raise_for_status()
        lines = r.text.splitlines()
    df = _parse_omni2_hourly_lines(lines, year=year)
    _LOG.debug("OMNI2 %s: hourly rows=%s", year, len(df))
    return df


def _fill_sentinel_f(v: str, kind: str) -> float:
    v = v.strip()
    if not v or v in {"9999.", "99999.", "99999.9", "999.9", "99999.99", "999999.99"}:
        return math.nan
    if kind in {"f107", "dst", "r", "ap"}:
        x = float(v)
        if v.startswith("9") and x > 1000:  # gross fill
            return math.nan
        return x
    return float(v)


def _parse_omni2_hourly_line(line: str) -> tuple[pd.Timestamp, float, float, float, float] | None:
    """
    Whitespace token positions on typical OMNI2 lines (0-based)::

        40: R (sunspot)
        41: Dst
        49: ap
        50: f10.7
    """
    parts = line.split()
    if len(parts) < 51:
        return None
    try:
        y, doy, hour = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None
    r = _fill_sentinel_f(parts[40], "r")
    dst = _fill_sentinel_f(parts[41], "dst")
    ap = _fill_sentinel_f(parts[49], "ap")
    f107 = _fill_sentinel_f(parts[50], "f107")
    start = dt.datetime(int(y), 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(days=doy - 1)
    t = start + dt.timedelta(hours=hour)
    t = t.replace(tzinfo=None)  # naive UTC
    return pd.Timestamp(t), f107, dst, r, ap


def _parse_omni2_hourly_lines(lines: list[str], *, year: int) -> pd.DataFrame:
    recs: list[tuple[pd.Timestamp, float, float, float, float]] = []
    for line in lines:
        if not line or line[0] not in "0123456789":
            continue
        p = _parse_omni2_hourly_line(line)
        if p is not None:
            recs.append(p)
    if not recs:
        return pd.DataFrame(
            columns=["f107", "dst", "r_ssn", "ap_nT"],
        )
    idx = [r[0] for r in recs]
    d = {
        "f107": [r[1] for r in recs],
        "dst": [r[2] for r in recs],
        "r_ssn": [r[3] for r in recs],
        "ap_nT": [r[4] for r in recs],
    }
    return pd.DataFrame(d, index=pd.DatetimeIndex(idx, name="time_utc")).sort_index()


def load_omni2_daily(
    years: Iterable[int],
    *,
    cache: bool = True,
) -> pd.DataFrame:
    year_list = sorted({int(y) for y in years})
    if not year_list:
        return pd.DataFrame(columns=["f107", "dst", "r_ssn", "ap_nT"])
    ykey = tuple(year_list)
    if ykey in _OMNI2_DAILY_MEM:
        _LOG.debug(
            "OMNI2 daily: memory hit %s years (%s … %s) → %s days",
            len(ykey),
            ykey[0],
            ykey[-1],
            len(_OMNI2_DAILY_MEM[ykey]),
        )
        return _OMNI2_DAILY_MEM[ykey].copy()
    _LOG.info("OMNI2 daily: %s year files (%s … %s)", len(year_list), year_list[0], year_list[-1])
    parts = [load_omni2_hourly_year(y, cache=cache) for y in year_list]
    df = pd.concat(parts).sort_index()
    daily = df.resample("1D").mean()
    _LOG.info(
        "OMNI2 daily: %s UTC days after resample (first load; memory-cached this run)",
        len(daily),
    )
    _OMNI2_DAILY_MEM[ykey] = daily.copy()
    return daily.copy()
