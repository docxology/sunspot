from pathlib import Path

import numpy as np
import pandas as pd

from sunspot.stats import lag_correlation_search, per_repo_associations
from sunspot.viz import (
    save_distribution,
    save_lag_grid,
    save_lag_heatmap,
    save_metric_correlation_matrix,
    save_metrics_zscored_overview,
    save_monthly,
    save_regression,
    save_repo_metric_spearman_heatmap,
    save_rolling_corr,
    save_top_repos_ma,
)


def _toy(n: int = 400, seed: int = 0) -> tuple[pd.Series, pd.Series]:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    metric = pd.Series(
        np.sin(np.arange(n) / 30.0) + rng.normal(scale=0.2, size=n),
        index=idx,
        name="m",
    )
    raw = metric.to_numpy() * 3 + rng.normal(scale=1.0, size=n)
    commits = pd.Series(np.clip(raw, 0, None).round(), index=idx, name="commits")
    return commits, metric


def test_per_metric_plots_write_files(tmp_path: Path) -> None:
    c, m = _toy()
    save_regression(c, m, out=tmp_path / "regression.png", metric_label="m")
    save_rolling_corr(c, m, out=tmp_path / "rolling_corr.png", window=60, metric_label="m")
    save_lag_heatmap(
        c,
        m,
        out=tmp_path / "lag_heatmap.png",
        metric_label="m",
        lags=list(range(-20, 21, 5)),
        windows=[30, 60],
    )
    save_distribution(c, m, out=tmp_path / "distribution.png", metric_label="m")
    save_monthly(c, m, out=tmp_path / "monthly.png", metric_label="m")
    expected = (
        "regression.png",
        "rolling_corr.png",
        "lag_heatmap.png",
        "distribution.png",
        "monthly.png",
    )
    for fn in expected:
        p = tmp_path / fn
        assert p.is_file() and p.stat().st_size > 1000


def test_overview_plots_write_files(tmp_path: Path) -> None:
    c, m = _toy()
    df = pd.DataFrame({"m": m, "n": m.shift(5).fillna(0.0)})
    save_metric_correlation_matrix(df, out=tmp_path / "matrix.png")
    save_metrics_zscored_overview(c, df, out=tmp_path / "overview.png")
    lr = {"m": lag_correlation_search(c, m, max_lag=10, method="spearman")}
    save_lag_grid(lr, out=tmp_path / "lag_grid.png")
    for fn in ("matrix.png", "overview.png", "lag_grid.png"):
        assert (tmp_path / fn).stat().st_size > 1000


def test_per_repo_plots_write_files(tmp_path: Path) -> None:
    c, m = _toy()
    rng = np.random.default_rng(7)
    repos: dict[str, pd.Series] = {}
    for i in range(5):
        v = c.to_numpy() / (i + 1) + rng.normal(size=len(c))
        repos[f"u/r{i}"] = pd.Series(np.clip(v, 0, None).round(), index=c.index, name="commits")
    save_top_repos_ma(repos, m, out=tmp_path / "top.png", top_n=3)
    df_pr = per_repo_associations(repos, pd.DataFrame({"m": m}))
    save_repo_metric_spearman_heatmap(df_pr, out=tmp_path / "heat.png")
    assert (tmp_path / "top.png").stat().st_size > 1000
    assert (tmp_path / "heat.png").stat().st_size > 1000
