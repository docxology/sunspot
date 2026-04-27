import numpy as np
import pandas as pd

from sunspot.stats.correlation import (
    association_metrics,
    fdr_on_pvalues,
    lag_correlation_search,
    rolling_pearson,
)


def test_lag() -> None:
    idx = pd.date_range("2020-01-01", periods=20, freq="D")
    a = pd.Series(np.arange(20, dtype=float), index=idx, name="a")
    b = a.shift(2)
    r = lag_correlation_search(a, b, max_lag=4, method="pearson")
    assert r.best_lag in (-2, 2) or r.best_value > 0.9


def test_rolling() -> None:
    idx = pd.date_range("2020-01-01", periods=50, freq="D")
    a = pd.Series(np.random.default_rng(0).normal(size=50), index=idx, name="a")
    b = pd.Series(np.random.default_rng(1).normal(size=50), index=idx, name="b")
    s = rolling_pearson(a, b, window=10)
    assert s.notna().any()


def test_fdr() -> None:
    p = np.array([0.01, 0.04, 0.1, 0.5, float("nan")])
    m = fdr_on_pvalues(p, q=0.1)
    assert m.shape == p.shape


def test_assoc() -> None:
    idx = pd.date_range("2020-01-01", periods=10, freq="D")
    a = pd.Series(np.arange(10.0), index=idx, name="a")
    b = pd.Series(np.arange(10.0) * 2, index=idx, name="b")
    m = association_metrics(a, b)
    assert m[0].kind == "pearson"
    assert m[0].p is not None
    assert abs(m[0].value - 1.0) < 1e-6
