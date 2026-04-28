"""Offline tests for cohort correlation distribution histogram."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from sunspot.viz.cohort import save_correlation_distribution_histogram


def test_save_correlation_distribution_histogram_synthetic(tmp_path: Path) -> None:
    rng = pd.date_range("2020-01-01", periods=3, freq="D")
    _ = rng  # period for plot API
    mu = pd.DataFrame({
        "user": [f"u{i}" for i in range(12)],
        "metric": ["ssn"] * 12,
        "n": [100] * 12,
        "total_commits": [10.0] * 12,
        "active_days": [50] * 12,
        "rho": [0.1 * i - 0.55 for i in range(12)],
        "p": [0.05] * 12,
    })
    out = tmp_path / "h.png"
    csv = tmp_path / "h.csv"
    summ = save_correlation_distribution_histogram(
        mu,
        metric="ssn",
        out=out,
        out_csv=csv,
        period=(date(2020, 1, 1), date(2020, 1, 3)),
    )
    assert out.is_file()
    assert csv.is_file()
    assert summ["n_finite_rho"] == 12
    assert summ["median"] is not None
    assert abs(summ["median"]) < 1.0


def test_save_correlation_distribution_histogram_no_finite(tmp_path: Path) -> None:
    mu = pd.DataFrame({
        "user": ["a", "b"],
        "metric": ["ssn", "ssn"],
        "n": [10, 10],
        "total_commits": [1.0, 1.0],
        "active_days": [5, 5],
        "rho": [float("nan"), float("nan")],
        "p": [float("nan"), float("nan")],
    })
    summ = save_correlation_distribution_histogram(
        mu,
        metric="ssn",
        out=tmp_path / "empty.png",
        out_csv=tmp_path / "empty.csv",
    )
    assert summ["n_finite_rho"] == 0
    assert (tmp_path / "empty.png").is_file()
