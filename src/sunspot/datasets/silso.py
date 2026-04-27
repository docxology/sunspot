"""
WDC-SILSO daily total sunspot number (version 2.0).

Source: https://www.sidc.be/silso/DATA/
License: CC BY-NC 4.0 (non-commercial; attribute SILSO/ROB).
See README for citation text.
"""

from __future__ import annotations

import io
import logging
from typing import TextIO

import pandas as pd

from sunspot.datasets.cache import ensure_cached_url

_LOG = logging.getLogger(__name__)

# Pinned public file (semicolon-separated; missing SSN = -1).
SILSO_DAILY_TOT_V2_URL = "https://www.sidc.be/silso/DATA/SN_d_tot_V2.0.csv"


def load_silso_daily_tot_v2(
    path_or_url: str | None = None,
    *,
    cache: bool = True,
) -> pd.DataFrame:
    """
    Load SILSO daily total SSN (V2.0) into a DataFrame.

    Columns: ``ssn`` (float), index ``date`` (UTC midnight, timezone-naive).
    Rows with ``ssn < 0`` are replaced with ``NaN`` (missing).
    """
    url = path_or_url or SILSO_DAILY_TOT_V2_URL
    _LOG.info("SILSO load: %s", url)
    if url.startswith("http://") or url.startswith("https://"):
        if cache:
            p = ensure_cached_url(url, suffix=".csv")
        else:
            import httpx

            p = None  # type: ignore[assignment]
            with httpx.Client(timeout=60.0, follow_redirects=True) as c:
                r = c.get(url)
                r.raise_for_status()
                out = _parse_silso_csv(io.StringIO(r.text))
                _LOG.info("SILSO daily V2.0: %s rows (no disk cache)", len(out))
                return out
        text = p.read_text(encoding="utf-8", errors="replace")
    else:
        text = open(url, encoding="utf-8", errors="replace").read()
    out = _parse_silso_csv(io.StringIO(text))
    _LOG.info("SILSO daily V2.0: %s rows in range", len(out))
    return out


def _parse_silso_csv(f: TextIO) -> pd.DataFrame:
    # Year;Month;Day;Date in fraction;SN;Std;Observations;Definitive
    df = pd.read_csv(
        f,
        sep=";",
        header=None,
        names=[
            "year",
            "month",
            "day",
            "frac_year",
            "ssn",
            "std",
            "n_obs",
            "definitive",
        ],
        comment="#",
    )
    ts = pd.to_datetime(
        dict(year=df["year"], month=df["month"], day=df["day"]),
        utc=True,
    ).dt.tz_convert(None)
    ssn = df["ssn"].astype(float)
    ssn = ssn.where(ssn >= 0)
    out = pd.DataFrame({"ssn": ssn})
    out.index = pd.DatetimeIndex(ts).normalize()
    out.index.name = "date"
    return out
