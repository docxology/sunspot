"""
Unit tests for `sunspot.stats.information`.

The estimators are intentionally exercised on small but well-controlled
synthetic samples so we can pin down expected behaviour:

- strongly dependent samples should yield large positive MI in nats,
- independent samples should round to ~0,
- the lag curve should peak at the engineered lead/lag,
- KSG and binned should agree to within sampling noise.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from sunspot.stats.information import (
    MILagResult,
    mutual_information_binned,
    mutual_information_ksg,
    mutual_information_lag_curve,
    normalised_mi,
)


@pytest.fixture
def linked_series() -> tuple[pd.Series, pd.Series]:
    rng = np.random.default_rng(0)
    n = 1500
    x = rng.normal(size=n)
    y = x + rng.normal(scale=0.5, size=n)
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    return pd.Series(x, index=idx), pd.Series(y, index=idx)


@pytest.fixture
def independent_series() -> tuple[pd.Series, pd.Series]:
    rng = np.random.default_rng(1)
    n = 1500
    x = rng.normal(size=n)
    y = rng.normal(size=n)
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    return pd.Series(x, index=idx), pd.Series(y, index=idx)


def test_binned_mi_dependent_is_large(linked_series):
    a, b = linked_series
    mi, n, bins = mutual_information_binned(a, b)
    assert n == len(a)
    assert bins >= 8
    assert mi > 0.4, f"expected substantial MI, got {mi:.3f}"


def test_binned_mi_independent_is_small(independent_series):
    a, b = independent_series
    mi, _, _ = mutual_information_binned(a, b)
    # Miller-Madow correction should bring this well under 0.2 nats.
    assert mi < 0.2, f"expected near-zero MI, got {mi:.3f}"


def test_ksg_mi_dependent_matches_binned_within_noise(linked_series):
    a, b = linked_series
    mi_b, _, _ = mutual_information_binned(a, b)
    mi_k, _ = mutual_information_ksg(a, b, k=5)
    assert mi_k > 0.4
    # Two estimators should agree to ~0.25 nats on these samples.
    assert abs(mi_b - mi_k) < 0.25, f"binned={mi_b:.3f} ksg={mi_k:.3f}"


def test_ksg_mi_independent_is_zeroish(independent_series):
    a, b = independent_series
    mi_k, _ = mutual_information_ksg(a, b, k=5)
    assert mi_k < 0.1, f"expected near-zero KSG MI, got {mi_k:.3f}"


def test_constant_input_returns_zero():
    n = 200
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    a = pd.Series(np.ones(n), index=idx)
    b = pd.Series(np.arange(n, dtype=float), index=idx)
    mi_b, _, _ = mutual_information_binned(a, b)
    mi_k, _ = mutual_information_ksg(a, b, k=5)
    assert mi_b == 0.0
    assert mi_k == 0.0


def test_too_few_points_returns_nan():
    idx = pd.date_range("2020-01-01", periods=3, freq="D")
    a = pd.Series([1.0, 2.0, 3.0], index=idx)
    b = pd.Series([1.0, 2.0, 3.0], index=idx)
    mi, n, bins = mutual_information_binned(a, b)
    assert math.isnan(mi)
    assert n == 0
    assert bins == 0


def test_normalised_mi_in_unit_interval(linked_series):
    a, b = linked_series
    mi, n, bins = mutual_information_binned(a, b)
    nmi = normalised_mi(mi, n, bins)
    assert 0.0 <= nmi <= 1.0


def test_lag_curve_peaks_at_engineered_lag(linked_series):
    a, b = linked_series
    # Make `a` clearly lead `b` by 4 days.
    a_shifted = a.shift(4)
    res = mutual_information_lag_curve(a_shifted, b, max_lag=10)
    assert isinstance(res, MILagResult)
    assert res.method == "binned"
    # `a_shifted` is `a` 4 days late, so to recover `a` (which leads b) the
    # estimator must shift it back by -4 days.
    assert -6 <= res.best_lag <= -2, f"expected peak near -4d, got {res.best_lag}"
    assert res.best_value > 0.4


def test_lag_curve_ksg_method_runs():
    rng = np.random.default_rng(2)
    n = 400
    x = rng.normal(size=n)
    y = np.roll(x, 3) + rng.normal(scale=0.3, size=n)
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    res = mutual_information_lag_curve(
        pd.Series(x, index=idx),
        pd.Series(y, index=idx),
        max_lag=8,
        method="ksg",
    )
    assert res.method == "ksg"
    assert res.bins_or_k == 5
    # Best lag should be near +3 (a leads b by 3).
    assert 1 <= res.best_lag <= 5
