"""Unit tests for ``sunspot.tables.write_analysis_tables``."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from sunspot.stats.correlation import CCFResult, LagResult
from sunspot.tables import write_analysis_tables


def _toy_report() -> dict:
    return {
        "metrics": {
            "f107": {
                "n_aligned": 100,
                "associations": [
                    {"kind": "pearson", "value": 0.20, "p": 0.04},
                    {"kind": "spearman", "value": 0.18, "p": 0.05},
                    {"kind": "kendall", "value": 0.12, "p": 0.07},
                ],
                "pearson_ci95": {"r": 0.20, "lo": 0.01, "hi": 0.38, "p": 0.04, "n": 100},
                "spearman_ci95": {"rho": 0.18, "lo": -0.01, "hi": 0.36, "p": 0.05, "n": 100},
                "lag_fdr_significant_count": 2,
                "lag_profile": [
                    {"lag_days": -2, "rho": 0.05, "p": 0.4, "fdr_significant": False},
                    {"lag_days": -1, "rho": 0.10, "p": 0.2, "fdr_significant": False},
                    {"lag_days": 0, "rho": 0.18, "p": 0.05, "fdr_significant": True},
                    {"lag_days": 1, "rho": 0.12, "p": 0.18, "fdr_significant": False},
                    {"lag_days": 2, "rho": 0.06, "p": 0.5, "fdr_significant": False},
                ],
                "ccf_profile": [
                    {
                        "lag_days": -1, "ccf": 0.05, "bartlett_ci95": 0.18,
                        "crosses_bartlett_ci95": False, "method": "pearson", "n_eff": 99,
                    },
                    {
                        "lag_days": 0, "ccf": 0.20, "bartlett_ci95": 0.18,
                        "crosses_bartlett_ci95": True, "method": "pearson", "n_eff": 99,
                    },
                    {
                        "lag_days": 1, "ccf": 0.10, "bartlett_ci95": 0.18,
                        "crosses_bartlett_ci95": False, "method": "pearson", "n_eff": 99,
                    },
                ],
                "ma_correlations": [
                    {
                        "window": 7, "n": 90, "n_eff": 12,
                        "pearson_r": 0.30, "pearson_lo": 0.10, "pearson_hi": 0.48,
                        "pearson_p": 0.005,
                        "spearman_rho": 0.28, "spearman_lo": 0.08, "spearman_hi": 0.46,
                        "spearman_p": 0.008,
                    },
                    {
                        "window": 30, "n": 70, "n_eff": 2,
                        "pearson_r": 0.55, "pearson_lo": 0.30, "pearson_hi": 0.74,
                        "pearson_p": 1e-5,
                        "spearman_rho": 0.50, "spearman_lo": 0.25, "spearman_hi": 0.69,
                        "spearman_p": 5e-5,
                    },
                ],
                "mi_lag": {
                    "lags": [-2, -1, 0, 1, 2],
                    "values_nats": [0.01, 0.02, 0.05, 0.03, 0.02],
                    "n_per_lag": [98, 99, 100, 99, 98],
                    "best_lag": 0, "best_value_nats": 0.05,
                    "method": "binned", "bins_or_k": 12,
                },
                "mutual_information": {
                    "binned_nats": 0.05, "binned_normalised": 0.10,
                    "binned_bins": 12, "ksg_nats": 0.04, "n": 100,
                },
                "regression_ols": {
                    "n": 100, "b0": 0.1, "b1": 0.2, "r2": 0.04, "sigma2": 1.2,
                    "pearson_r": 0.20, "pearson_lo": 0.01, "pearson_hi": 0.38,
                    "pearson_p": 0.04,
                    "durbin_watson": 1.85, "normality_stat": 1.0, "normality_p": 0.5,
                },
                "partial_correlation_ar1": {
                    "controls": ["commits_lag1", "metric_lag1"],
                    "pearson":  {"r": 0.10, "p": 0.32, "n": 99},
                    "spearman": {"rho": 0.09, "p": 0.40, "n": 99},
                },
                "periodogram_top5": [
                    {"period_days": 27.0, "power": 0.30},
                    {"period_days": 365.25, "power": 0.20},
                ],
                "spectral_band_power": [
                    {
                        "band": "solar_rotation", "min_period_days": 24.0,
                        "max_period_days": 31.0, "power_fraction": 0.12,
                    },
                ],
            },
        },
        "commits_summary": {
            "total_days": 100, "days_with_commits": 50,
            "active_days_fraction": 0.5,
            "dow_means_mon_to_sun": [1, 1, 1, 1, 1, 0, 0],
        },
        "cross_metric_correlation": {
            "f107": {"f107": 1.0, "ssn": 0.85, "commits": 0.20},
            "ssn":  {"f107": 0.85, "ssn": 1.0, "commits": 0.18},
            "commits": {"f107": 0.20, "ssn": 0.18, "commits": 1.0},
        },
        "commits_periodogram_top5": [
            {"period_days": 7.0, "power": 0.5},
            {"period_days": 30.0, "power": 0.3},
        ],
        "commits_spectral_band_power": [
            {
                "band": "weekly", "min_period_days": 6.0,
                "max_period_days": 8.0, "power_fraction": 0.22,
            },
        ],
        "per_repo_topk": [
            {"repo": "u/r1", "metric": "f107", "n": 100, "total_commits": 25,
             "rho": 0.30, "p": 0.001, "q_significant": True},
        ],
        "cohort_user_summary": [
            {
                "login": "u1", "total_commits": 10.0, "total_days": 100,
                "active_days": 5, "active_days_fraction": 0.05,
                "mean_per_day": 0.1, "mean_per_active_day": 2.0,
                "max_day": 4.0, "max_day_date": "2020-01-03",
            },
        ],
    }


def test_write_analysis_tables_emits_expected_files(tmp_path: Path) -> None:
    rep = _toy_report()
    lag = LagResult(
        lags=[-2, -1, 0, 1, 2],
        values=[0.05, 0.10, 0.18, 0.12, 0.06],
        p_values=[0.4, 0.2, 0.05, 0.18, 0.5],
        best_lag=0, best_value=0.18,
    )
    ccf = CCFResult(
        lags=[-1, 0, 1], values=[0.05, 0.20, 0.10],
        bartlett_ci=0.18, n=99, method="pearson",
    )
    paths = write_analysis_tables(
        rep, tmp_path,
        lag_results={"f107": lag}, ccf_results={"f107": ccf},
    )
    written = {p.name for p in paths}
    expected = {
        "associations.csv", "lag_profile.csv", "ccf_profile.csv",
        "ma_correlations.csv", "mi_lag.csv", "mutual_information.csv",
        "regression_ols.csv", "partial_correlation_ar1.csv",
        "cross_metric_spearman.csv", "periodogram_top.csv",
        "spectral_band_power.csv", "commits_daily_summary.csv",
        "per_repo_topk.csv", "cohort_user_summary.csv",
    }
    assert expected.issubset(written)
    tables_dir = tmp_path / "tables"
    # README always written.
    assert (tables_dir / "README.md").is_file()

    # Spot-check a few schemas.
    assoc = pd.read_csv(tables_dir / "associations.csv")
    assert {"metric", "kind", "n", "value", "ci95_lo", "ci95_hi", "p", "stars"} \
        .issubset(assoc.columns)
    assert set(assoc["kind"]) == {"pearson", "spearman", "kendall"}

    lag_df = pd.read_csv(tables_dir / "lag_profile.csv")
    assert {"metric", "lag_days", "rho", "p", "fdr_significant"}.issubset(lag_df.columns)
    assert (lag_df["metric"] == "f107").all()
    assert int(lag_df["lag_days"].max()) == 2
    assert lag_df["fdr_significant"].astype(bool).sum() == 1

    ccf_df = pd.read_csv(tables_dir / "ccf_profile.csv")
    assert "crosses_bartlett_ci95" in ccf_df.columns
    assert ccf_df["crosses_bartlett_ci95"].astype(bool).sum() == 1

    ma_df = pd.read_csv(tables_dir / "ma_correlations.csv")
    assert (ma_df["window_days"].sort_values().tolist() == [7, 30])

    mi_df = pd.read_csv(tables_dir / "mi_lag.csv")
    assert mi_df["mi_nats"].max() == 0.05
    assert (mi_df["bins_or_k"] == 12).all()

    reg = pd.read_csv(tables_dir / "regression_ols.csv")
    assert reg.loc[0, "durbin_watson"] == 1.85

    cm = pd.read_csv(tables_dir / "cross_metric_spearman.csv", index_col=0)
    assert cm.loc["f107", "ssn"] == 0.85

    spec = pd.read_csv(tables_dir / "spectral_band_power.csv")
    assert set(spec["series"]) == {"commits", "f107"}

    cohort = pd.read_csv(tables_dir / "cohort_user_summary.csv")
    assert cohort.loc[0, "login"] == "u1"


def test_write_analysis_tables_handles_empty_report(tmp_path: Path) -> None:
    """A report missing optional blocks should still produce the README and
    only the files for which data exists — no traceback."""
    paths = write_analysis_tables({"metrics": {}}, tmp_path)
    assert (tmp_path / "tables" / "README.md").is_file()
    assert paths == []  # nothing else to emit
