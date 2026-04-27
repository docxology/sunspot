"""Offline tests for :mod:`sunspot.cohort` (no network, metrics mocked)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from sunspot.cohort import run_cohort_report
from sunspot.cohort_presets import expand_preset


def _mock_commits(
    _user: str, *, since, until, use_commit_cache: bool = True, **_k: object,
) -> dict:
    idx = pd.date_range(pd.Timestamp(since), pd.Timestamp(until), freq="D")
    rng = np.random.default_rng(hash(_user) % 2**32)
    a = _user
    c = (rng.random(len(idx)) * 2.0) ** 2
    s = pd.Series(c, index=idx, name="commits")
    return {f"{a}/r": s, "__all__": s}


def _mock_metric(idx: pd.DatetimeIndex) -> pd.Series:
    x = np.sin(np.arange(len(idx)) * 0.01) * 20.0 + 50.0
    return pd.Series(x, index=idx, name="m")


def _metric_factory(_m: str, *, since, until) -> pd.Series:
    idx = pd.date_range(pd.Timestamp(since), pd.Timestamp(until), freq="D")
    s = _mock_metric(idx)
    s.name = _m
    return s


@pytest.mark.parametrize("preset_name", ("panel", "ai", "wide", "full"))
def test_expand_preset_nonempty(preset_name: str) -> None:
    t = expand_preset(preset_name)
    assert len(t) >= 2
    assert all(isinstance(s, str) and s for s in t)


@patch("sunspot.cohort._series_for_metric", side_effect=_metric_factory)
@patch("sunspot.cohort.public_commit_time_series", side_effect=_mock_commits)
def test_run_cohort_report_offline(
    _pc: object, _met: object, tmp_path: Path,
) -> None:
    s0, u0 = date(2023, 1, 1), date(2023, 4, 1)
    rep = run_cohort_report(
        ["u1", "u2"],
        since=s0,
        until=u0,
        metrics=["ssn", "f107"],
        out_dir=tmp_path,
        use_commit_cache=True,
        make_mosaic=True,
    )
    assert rep.get("report_kind") == "cohort"
    assert set(rep.get("cohort_users", [])) == {"u1", "u2"}
    assert (tmp_path / "data" / "commits" / "daily_users_wide.csv").is_file()
    assert (tmp_path / "data" / "commits" / "user_summary.csv").is_file()
    assert (tmp_path / "data" / "commits" / "by_user" / "u1.csv").is_file()
    assert (tmp_path / "visualizations" / "cohort" / "user_pca_scatter.png").is_file()
    assert (tmp_path / "visualizations" / "cohort" / "user_summary.png").is_file()
    rj = json.loads((tmp_path / "statistics" / "report.json").read_text())
    assert rj.get("cohort_pca")
    assert rj.get("cohort_user_summary")
    assert (tmp_path / "analysis" / "multi_user_associations.csv").is_file()
    assert (tmp_path / "analysis" / "tables" / "cohort_user_summary.csv").is_file()
    assert (tmp_path / "visualizations" / "mosaic.png").is_file()
