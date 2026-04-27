"""Tests for the new statistical primitives."""

from __future__ import annotations

import numpy as np
import pandas as pd

from sunspot.stats import (
    ar1_prewhiten,
    bootstrap_corr_ci,
    cross_correlation_function,
    multi_user_associations,
    multi_user_rank_matrix,
    partial_correlation,
    spearman_with_ci,
)
from sunspot.stats.multi_user import (
    cohort_dendrogram_leaves,
    hierarchical_user_order,
)


def _ts(seed: int, n: int = 400, scale: float = 1.0) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    return pd.Series(rng.normal(scale=scale, size=n), index=idx)


def test_spearman_with_ci_returns_finite_bounds() -> None:
    a = _ts(1, 400)
    b = a.shift(0).fillna(0.0) * 0.5 + _ts(2, 400, 0.5)
    rho, lo, hi, p, n = spearman_with_ci(a, b)
    assert n == 400
    assert -1.0 <= lo <= rho <= hi <= 1.0
    assert 0.0 <= p <= 1.0


def test_bootstrap_corr_ci_brackets_point_estimate() -> None:
    a = _ts(0, 250)
    b = a + _ts(1, 250, 0.4)
    point, lo, hi, n = bootstrap_corr_ci(a, b, method="pearson", n_boot=200, seed=42)
    assert n == 250
    assert lo < point < hi
    assert -1.0 <= lo and hi <= 1.0


def test_ar1_prewhiten_reduces_autocorrelation() -> None:
    rng = np.random.default_rng(0)
    n = 400
    e = rng.normal(size=n)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = 0.85 * x[i - 1] + e[i]
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    s = pd.Series(x, index=idx)
    s2 = pd.Series(rng.normal(size=n), index=idx)
    a, b, phi_a, _ = ar1_prewhiten(s, s2)
    av = a.dropna().to_numpy()
    raw_lag1 = float(np.corrcoef(s.iloc[:-1], s.iloc[1:])[0, 1])
    pw_lag1 = float(np.corrcoef(av[:-1], av[1:])[0, 1])
    assert phi_a > 0.5
    assert abs(pw_lag1) < abs(raw_lag1)


def test_cross_correlation_function_finds_known_lag() -> None:
    rng = np.random.default_rng(7)
    n = 600
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    base = pd.Series(rng.normal(size=n), index=idx)
    delayed = base.shift(5).fillna(0.0) + 0.1 * pd.Series(rng.normal(size=n), index=idx)
    res = cross_correlation_function(
        base, delayed, max_lag=20, method="pearson", prewhiten=False,
    )
    arr = np.array(res.values, dtype=float)
    peak_lag = int(res.lags[int(np.nanargmax(arr))])
    assert abs(peak_lag - 5) <= 1
    assert res.bartlett_ci > 0.0 and res.bartlett_ci < 1.0


def test_partial_correlation_removes_common_driver() -> None:
    rng = np.random.default_rng(3)
    n = 400
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    z = pd.Series(rng.normal(size=n), index=idx)
    a = z + 0.3 * pd.Series(rng.normal(size=n), index=idx)
    b = z + 0.3 * pd.Series(rng.normal(size=n), index=idx)
    raw = float(np.corrcoef(a, b)[0, 1])
    pc, _p, _n = partial_correlation(a, b, controls=[z])
    assert abs(pc) < abs(raw)
    assert abs(pc) < 0.2


def test_multi_user_associations_flags_synthetic_signal() -> None:
    rng = np.random.default_rng(42)
    n = 400
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    metric = pd.Series(rng.normal(size=n), index=idx, name="m")
    other = pd.Series(rng.normal(size=n), index=idx, name="other")
    users: dict[str, pd.Series] = {}
    for i in range(8):
        if i == 0:
            v = metric.to_numpy() * 4 + rng.normal(scale=0.3, size=n)
        else:
            v = rng.normal(size=n)
        users[f"u{i}"] = pd.Series(np.clip(v, 0, None).round(), index=idx)
    df = multi_user_associations(
        users, pd.DataFrame({"m": metric, "other": other}), method="spearman",
    )
    assert {"user", "metric", "rho", "p", "q_significant"}.issubset(df.columns)
    assert df["q_significant"].any()


def test_multi_user_rank_matrix_returns_symmetric_unit_diag() -> None:
    a = _ts(0, 200)
    b = a + _ts(1, 200, 0.2)
    c = _ts(2, 200)
    users = {"a": a.clip(lower=0), "b": b.clip(lower=0), "c": c.clip(lower=0)}
    m = multi_user_rank_matrix(users, smoothing_window=10)
    arr = m.to_numpy()
    assert arr.shape == (3, 3)
    assert np.allclose(np.diag(arr), 1.0)
    assert np.allclose(arr, arr.T, equal_nan=True)


def test_cohort_dendrogram_excludes_inactive_user_finishes_tree() -> None:
    """Constant weekly user would make correlation pdist non-finite; must exclude."""
    idx = pd.date_range("2023-01-01", periods=200, freq="D")
    rng = np.random.default_rng(0)
    u1 = pd.Series(rng.integers(0, 5, size=len(idx)), index=idx)
    u2 = pd.Series(rng.integers(0, 4, size=len(idx)), index=idx)
    flat = pd.Series(0.0, index=idx)
    leaves, excl = cohort_dendrogram_leaves({"a": u1, "b": u2, "flat": flat})
    assert "flat" in excl
    assert leaves is not None
    assert set(leaves) == {"a", "b"}


def test_cohort_dendrogram_no_tree_if_only_one_varying_user() -> None:
    idx = pd.date_range("2023-01-01", periods=100, freq="D")
    u1 = pd.Series(np.random.default_rng(1).integers(0, 3, size=len(idx)), index=idx)
    flat2 = pd.Series(0.0, index=idx)
    leaves, excl = cohort_dendrogram_leaves({"a": u1, "b": flat2})
    assert leaves is None
    assert excl
    assert hierarchical_user_order({"a": u1, "b": flat2}) is None
