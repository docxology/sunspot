import json
from datetime import date
from pathlib import Path

import pandas as pd

from sunspot.correlate import run_correlation_report


def test_report_with_zero_commits_offline(tmp_path: Path) -> None:
    import sunspot.correlate as cor

    def fake(
        _user: str, *, since: date, until: date, use_commit_cache: bool = True, **_: object
    ) -> dict[str, pd.Series]:
        idx = pd.date_range(pd.Timestamp(since), pd.Timestamp(until), freq="D")
        s = pd.Series(0.0, index=idx, name="commits")
        return {"__all__": s, "a/r": s}

    cor.public_commit_time_series, orig = fake, cor.public_commit_time_series
    out = tmp_path / "run"
    try:
        run_correlation_report(
            "dummy",
            since=date(2010, 1, 1),
            until=date(2010, 1, 20),
            metrics=["f107", "dst"],
            out_dir=out,
        )
    finally:
        cor.public_commit_time_series = orig
    p = json.loads((out / "statistics" / "report.json").read_text())
    assert p["version"]
    # Daily commits summary present and well-formed.
    cs = p.get("commits_summary") or {}
    assert {
        "total_days", "days_with_commits", "active_days_fraction",
        "mean_per_day", "mean_per_active_day", "max_day",
        "longest_active_streak_days", "longest_quiet_streak_days",
        "dow_means_mon_to_sun", "weekday_share", "weekend_share",
    }.issubset(cs.keys())
    assert len(cs["dow_means_mon_to_sun"]) == 7
    for k in ("f107", "dst"):
        assert k in p["metrics"]
        block = p["metrics"][k]
        if "error" not in block:
            assert "n_aligned" in block
            assert "pearson_ci95" in block
            assert "profile_p_min" in block["lag"]
            assert "lag_profile" in block
    # New artifacts
    assert (out / "analysis" / "summary.txt").is_file()
    assert (out / "analysis" / "methods.md").is_file()
    # All GitHub commit data lives under data/commits/.
    commits_dir = out / "data" / "commits"
    for fn in ("daily.csv", "weekly.csv", "monthly.csv", "dow_means.csv",
               "summary.csv", "manifest.json"):
        assert (commits_dir / fn).is_file(), fn
    assert (commits_dir / "by_repo").is_dir()
    # The pre-1.0 location must no longer be written.
    assert not (out / "data" / "commits_daily.csv").exists()
    # Analysis tables sidecars exist with the README index.
    tables = out / "analysis" / "tables"
    assert tables.is_dir()
    assert (tables / "README.md").is_file()
    assert (tables / "commits_daily_summary.csv").is_file()
    # Per-metric: dual/lag plus the new ccf/acf_pacf/periodogram when overlap exists
    for m in ("f107", "dst"):
        if "error" in p["metrics"][m]:
            continue
        for fn in (
            "dual_axis.png", "lag.png", "ccf.png", "acf_pacf.png", "periodogram.png",
        ):
            assert (out / "visualizations" / m / fn).is_file(), fn
        block = p["metrics"][m]
        # New stats fields
        assert "spearman_ci95" in block
        if "ccf" in block:
            assert "ccf_profile" in block
    # Per-metric tables that don't require non-zero variance always surface for
    # at least one non-error metric. (MA / MI / regression need variance and
    # are exercised by the multi-user test below.)
    if any("error" not in p["metrics"][m] for m in ("f107", "dst")):
        for fn in (
            "associations.csv", "lag_profile.csv",
            "cross_metric_spearman.csv", "periodogram_top.csv",
        ):
            assert (out / "analysis" / "tables" / fn).is_file(), fn
    # Mosaic + index always present (mosaic packs whatever it finds)
    assert (out / "visualizations" / "mosaic.png").is_file()
    assert (out / "visualizations" / "mosaic_index.json").is_file()
    # Seasonal calendar always attempted at the overview level (commits-only fallback ok)
    assert (out / "visualizations" / "overview" / "seasonal_calendar.png").is_file()
    # Cross-metric overview heatmap and overview ACF/spectral
    if any("error" not in p["metrics"][m] for m in ("f107", "dst")):
        assert (out / "visualizations" / "overview" / "metric_correlation_matrix.png").is_file()
        assert (out / "visualizations" / "overview" / "stacked_panel.png").is_file()
    assert (out / "visualizations" / "overview" / "commits_acf_pacf.png").is_file()
    assert (out / "visualizations" / "overview" / "dow_response.png").is_file()


def test_report_with_compare_users_offline(tmp_path: Path) -> None:
    import sunspot.correlate as cor

    counter = {"i": 0}

    def fake(
        _user: str, *, since: date, until: date, use_commit_cache: bool = True, **_: object,
    ) -> dict[str, pd.Series]:
        counter["i"] += 1
        idx = pd.date_range(pd.Timestamp(since), pd.Timestamp(until), freq="D")
        # Synthesize per-user activity that varies by call so multi-user pipeline runs
        vals = [(counter["i"] + j) % 5 for j in range(len(idx))]
        s = pd.Series(vals, index=idx, name="commits", dtype=float)
        return {"__all__": s, "a/r": s}

    cor.public_commit_time_series, orig = fake, cor.public_commit_time_series
    out = tmp_path / "run_mu"
    try:
        run_correlation_report(
            "alice",
            since=date(2010, 1, 1),
            until=date(2010, 4, 30),
            metrics=["f107"],
            out_dir=out,
            compare_user_logins=["bob", "carol"],
            bootstrap=50,
        )
    finally:
        cor.public_commit_time_series = orig
    p = json.loads((out / "statistics" / "report.json").read_text())
    assert p["compare_user_logins"] == ["bob", "carol"]
    block = p["metrics"]["f107"]
    if "error" not in block:
        assert "bootstrap_ci95" in block
        assert "ccf" in block
        assert "ccf_profile" in block
        # New per-metric stats: MA correlations and AR(1)-controlled partials.
        ma = block.get("ma_correlations") or []
        assert len(ma) >= 4
        for r in ma:
            assert {"window", "pearson_r", "spearman_rho", "n", "n_eff"}.issubset(r)
        pc = block.get("partial_correlation_ar1") or {}
        assert "pearson" in pc and "spearman" in pc
        mi = block.get("mutual_information") or {}
        assert {"binned_nats", "ksg_nats", "n", "binned_bins"}.issubset(mi)
        ml = block.get("mi_lag") or {}
        assert {"lags", "values_nats", "best_lag", "method"}.issubset(ml)
        reg = block.get("regression_ols") or {}
        assert {"r2", "durbin_watson", "normality_p", "b1"}.issubset(reg)
        assert "spectral_band_power" in block
        # Per-metric juxtaposition tiles (incl. MA-correlation + MI-lag).
        for fn in (
            "quantile_response.png", "joint_density.png", "ma_corr_curve.png",
            "mi_lag.png",
        ):
            assert (out / "visualizations" / "f107" / fn).is_file(), fn
    # Per-user commit CSVs land under data/commits/by_user/.
    by_user = out / "data" / "commits" / "by_user"
    assert by_user.is_dir()
    for login in ("alice", "bob", "carol"):
        assert (by_user / f"{login}.csv").is_file(), login
    assert (by_user / "manifest.json").is_file()
    # Tables that require actual variance (MA, MI, regression) appear here.
    tables = out / "analysis" / "tables"
    for fn in (
        "ma_correlations.csv", "mi_lag.csv", "mutual_information.csv",
        "regression_ols.csv", "ccf_profile.csv",
        "spectral_band_power.csv",
    ):
        assert (tables / fn).is_file(), fn
    if "multi_user_topk" in p:
        assert (tables / "multi_user_topk.csv").is_file()
    mu_dir = out / "visualizations" / "multi_user"
    assert mu_dir.is_dir()
    for fn in (
        "overview_30d_ma.png",
        "user_metric_spearman_heatmap.png",
        "user_user_rank_matrix.png",
        "cumulative_vs_solar.png",
        "phase_by_ssn_quantile.png",
    ):
        assert (mu_dir / fn).is_file(), fn
    assert (out / "analysis" / "multi_user_associations.csv").is_file()
