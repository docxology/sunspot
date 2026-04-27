from __future__ import annotations

from datetime import date

import pandas as pd


def clip_to_window(
    s: pd.Series,
    since: date | None,
    until: date | None,
) -> pd.Series:
    """
    Return ``s`` restricted to the inclusive UTC-day window ``[since, until]``.

    ``None`` on either side leaves that edge unbounded. The index is expected to
    be a ``DatetimeIndex``; the name and dtype of ``s`` are preserved. Bounds
    are inclusive and compared against normalized timestamps so date/datetime
    mixtures all resolve the same way.
    """
    if s.empty:
        return s
    idx = pd.DatetimeIndex(s.index)
    mask = pd.Series(True, index=idx)
    if since is not None:
        mask &= idx >= pd.Timestamp(since)
    if until is not None:
        mask &= idx <= pd.Timestamp(until)
    out = s.loc[mask.values]
    out.name = s.name
    return out


def to_daily_dataframe(
    *series: pd.Series,
    names: list[str] | None = None,
) -> pd.DataFrame:
    if not series:
        return pd.DataFrame()
    if names is None:
        names = [s.name or f"s{i}" for i, s in enumerate(series)]
    out = pd.concat(series, axis=1)
    out.columns = names
    return out


def join_on_dates(
    left: pd.Series,
    *others: pd.Series,
) -> pd.DataFrame:
    name = left.name or "x"
    df = left.to_frame(name=name)
    for i, s in enumerate(others):
        nm = s.name or f"x{i + 1}"
        df = df.join(s.rename(nm), how="outer")
    return df.sort_index()


def zscore(s: pd.Series) -> pd.Series:
    m = s.mean()
    v = s.std(ddof=0)
    if v == 0 or v != v:
        return s * 0.0
    return (s - m) / v
