import numpy as np
import pandas as pd
from scipy import stats as sst

from sunspot.stats import (
    cross_metric_corr_matrix,
    lag_window_grid,
    moving_average_correlation_curve,
    pearson_with_ci,
    per_repo_associations,
)


def _series(seed: int, n: int = 200, scale: float = 1.0) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    return pd.Series(rng.normal(scale=scale, size=n), index=idx)


def test_pearson_with_ci_matches_scipy_and_brackets_r() -> None:
    a = _series(0, 300)
    b = a + _series(1, 300, scale=0.5)
    r, lo, hi, p, n = pearson_with_ci(a, b)
    ref = sst.pearsonr(a.to_numpy(), b.to_numpy())
    assert n == 300
    assert abs(r - float(ref.statistic)) < 1e-10
    assert lo < r < hi
    assert 0.0 <= p <= 1.0


def test_pearson_with_ci_handles_constant_input() -> None:
    a = pd.Series([1.0] * 50, index=pd.date_range("2020-01-01", periods=50))
    b = _series(2, 50)
    r, lo, hi, p, n = pearson_with_ci(a, b)
    assert np.isnan(r) and np.isnan(lo) and np.isnan(hi) and p is None and n == 50


def test_lag_window_grid_shape_and_finite() -> None:
    a = _series(3, 400)
    b = a.shift(5).fillna(0.0)
    grid, lags, wins = lag_window_grid(a, b, lags=list(range(-10, 11, 2)), windows=[30, 60])
    assert grid.shape == (len(lags), len(wins))
    assert np.isfinite(grid).any()
    # value range should be in [-1, 1]
    finite = grid[np.isfinite(grid)]
    assert finite.min() >= -1.0 and finite.max() <= 1.0


def test_cross_metric_corr_matrix_symmetric_with_ones_on_diagonal() -> None:
    df = pd.DataFrame({"x": _series(0, 200), "y": _series(1, 200), "z": _series(2, 200)})
    m = cross_metric_corr_matrix(df, method="spearman")
    arr = m.to_numpy()
    assert m.shape == (3, 3)
    assert np.allclose(np.diag(arr), 1.0)
    assert np.allclose(arr, arr.T, equal_nan=True)


def test_moving_average_correlation_curve_increases_with_smoothing() -> None:
    # signal at low frequency drowned in daily noise: smoothing should
    # uncover the underlying correlation, so |r| at MA-30 > |r| at MA-1.
    n = 800
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    rng = np.random.default_rng(7)
    base = np.sin(np.arange(n) / 60.0)
    a = pd.Series(base + rng.normal(scale=2.0, size=n), index=idx)
    b = pd.Series(base + rng.normal(scale=2.0, size=n), index=idx)
    rows = moving_average_correlation_curve(a, b, windows=[1, 7, 30, 90], method="pearson")
    assert [r["window"] for r in rows] == [1, 7, 30, 90]
    for r in rows:
        for k in ("r", "lo", "hi", "n", "n_eff"):
            assert k in r
        assert -1.0 <= r["r"] <= 1.0
        assert r["lo"] <= r["r"] <= r["hi"] or not np.isfinite(r["lo"])
    assert abs(rows[2]["r"]) > abs(rows[0]["r"])  # MA-30 reveals more signal than raw daily


def test_moving_average_correlation_curve_spearman_matches_method() -> None:
    n = 300
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    rng = np.random.default_rng(0)
    a = pd.Series(rng.normal(size=n), index=idx)
    rows = moving_average_correlation_curve(a, a, windows=[1, 7], method="spearman")
    assert all(r["method"] == "spearman" for r in rows)
    assert abs(rows[0]["r"] - 1.0) < 1e-9


def test_per_repo_associations_returns_fdr_flags() -> None:
    idx = pd.date_range("2020-01-01", periods=400, freq="D")
    rng = np.random.default_rng(0)
    metric = pd.Series(rng.normal(size=400), index=idx, name="m")
    metric2 = pd.Series(rng.normal(size=400), index=idx, name="n")
    repos: dict[str, pd.Series] = {}
    for i in range(20):
        # repo 0 strongly correlated with metric, others noise
        if i == 0:
            v = metric.to_numpy() * 5 + rng.normal(scale=0.3, size=400)
        else:
            v = rng.normal(size=400)
        repos[f"u/r{i}"] = pd.Series(np.clip(v, 0, None).round(), index=idx)
    df = per_repo_associations(repos, pd.DataFrame({"m": metric, "n": metric2}), method="spearman")
    expected_cols = {"repo", "metric", "rho", "p", "q_significant", "n", "total_commits"}
    assert expected_cols.issubset(df.columns)
    # at least one (repo, metric) pair flagged significant after FDR
    assert df["q_significant"].any()
