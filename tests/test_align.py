"""Direct unit tests for :mod:`sunspot.align.join`.

These primitives are reused across the codebase (``correlate``, ``cohort``,
``stats.rolling_pearson`` and every plot that aligns two series), so they
deserve first-class tests rather than only indirect coverage.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from sunspot.align import clip_to_window, join_on_dates, to_daily_dataframe, zscore


def _s(vals: list[float], start: str = "2020-01-01", name: str | None = None) -> pd.Series:
    idx = pd.date_range(start, periods=len(vals), freq="D")
    return pd.Series(vals, index=idx, name=name)


def test_to_daily_dataframe_names_columns() -> None:
    df = to_daily_dataframe(_s([1, 2, 3], name="a"), _s([4, 5, 6], name="b"))
    assert list(df.columns) == ["a", "b"]
    assert df.shape == (3, 2)


def test_to_daily_dataframe_empty_input_returns_empty_frame() -> None:
    df = to_daily_dataframe()
    assert df.empty
    assert isinstance(df, pd.DataFrame)


def test_to_daily_dataframe_autonames_on_missing_names() -> None:
    df = to_daily_dataframe(_s([1, 2]), _s([3, 4]))
    assert list(df.columns) == ["s0", "s1"]


def test_join_on_dates_outer_joins_and_sorts() -> None:
    a = _s([1, 2, 3], start="2020-01-01", name="a")
    b = _s([10, 20], start="2020-01-03", name="b")
    df = join_on_dates(a, b)
    assert list(df.columns) == ["a", "b"]
    # Union of dates: 2020-01-01..04 (4 rows).
    assert df.shape[0] == 4
    # 2020-01-01 has `a` only.
    assert pd.isna(df.loc[pd.Timestamp("2020-01-01"), "b"])
    # 2020-01-04 has `b` only.
    assert pd.isna(df.loc[pd.Timestamp("2020-01-04"), "a"])
    # Overlap row carries both.
    assert df.loc[pd.Timestamp("2020-01-03"), "a"] == 3
    assert df.loc[pd.Timestamp("2020-01-03"), "b"] == 10
    # Sorted index
    assert df.index.is_monotonic_increasing


def test_join_on_dates_handles_unnamed_series() -> None:
    a = _s([1, 2, 3])
    b = _s([10, 20, 30])
    df = join_on_dates(a, b)
    # Left series → "x"; first other → "x1"
    assert "x" in df.columns
    assert "x1" in df.columns


def test_zscore_returns_zero_for_constant() -> None:
    out = zscore(_s([5.0, 5.0, 5.0]))
    assert (out == 0.0).all()


def test_zscore_centers_and_scales() -> None:
    s = _s([1.0, 2.0, 3.0, 4.0, 5.0])
    z = zscore(s)
    assert abs(float(z.mean())) < 1e-12
    # Population std used (ddof=0); variance = 2
    assert abs(float(z.std(ddof=0)) - 1.0) < 1e-12


def test_clip_to_window_inclusive_bounds() -> None:
    s = _s(list(range(10)), start="2020-01-01", name="x")
    out = clip_to_window(s, date(2020, 1, 3), date(2020, 1, 5))
    assert out.index[0] == pd.Timestamp("2020-01-03")
    assert out.index[-1] == pd.Timestamp("2020-01-05")
    assert out.tolist() == [2, 3, 4]
    assert out.name == "x"


def test_clip_to_window_none_bounds_are_unbounded() -> None:
    s = _s(list(range(5)))
    assert list(clip_to_window(s, None, None).values) == list(range(5))
    out = clip_to_window(s, None, date(2020, 1, 2))
    assert out.tolist() == [0, 1]
    out = clip_to_window(s, date(2020, 1, 4), None)
    assert out.tolist() == [3, 4]


def test_clip_to_window_empty_series_returns_empty() -> None:
    empty = pd.Series(dtype=float, name="y")
    out = clip_to_window(empty, date(2020, 1, 1), date(2020, 12, 31))
    assert out.empty
    assert out.name == "y"


def test_clip_to_window_preserves_dtype_and_nans() -> None:
    s = pd.Series(
        [1.0, float("nan"), 3.0],
        index=pd.date_range("2020-01-01", periods=3, freq="D"),
        name="m",
    )
    out = clip_to_window(s, date(2020, 1, 1), date(2020, 1, 3))
    assert out.dtype == np.float64
    assert np.isnan(out.iloc[1])
