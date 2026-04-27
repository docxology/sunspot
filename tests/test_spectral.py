"""Tests for the Lomb-Scargle periodogram."""

from __future__ import annotations

import numpy as np
import pandas as pd

from sunspot.stats import dominant_period, lomb_scargle_periodogram


def test_lomb_scargle_recovers_27_day_period() -> None:
    n = 800
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    rng = np.random.default_rng(0)
    t = np.arange(n)
    y = np.sin(2 * np.pi * t / 27.0) + 0.2 * rng.normal(size=n)
    s = pd.Series(y, index=idx, name="sim")
    p = lomb_scargle_periodogram(s, min_period_days=4, max_period_days=120, n_freqs=600)
    assert abs(dominant_period(p) - 27.0) < 1.5
    top = p.top_k(3)
    assert top and abs(top[0][0] - 27.0) < 2.0


def test_lomb_scargle_handles_constant_input() -> None:
    n = 200
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    s = pd.Series(np.ones(n), index=idx)
    p = lomb_scargle_periodogram(s)
    assert p.power.size == 0
    assert np.isnan(p.dominant_period_days)
