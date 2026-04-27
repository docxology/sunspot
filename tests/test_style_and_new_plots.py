"""Tests for style configuration and the new plot functions."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from sunspot.stats import multi_user_associations  # noqa: E402
from sunspot.viz import (  # noqa: E402
    PlotStyle,
    apply_rcparams,
    period_label,
    save_acf_pacf,
    save_ccf,
    save_dow_response,
    save_joint_density,
    save_ma_correlation_curve,
    save_mi_lag_curve,
    save_multi_user_cumulative,
    save_multi_user_heatmap,
    save_multi_user_overview,
    save_multi_user_phase,
    save_multi_user_rank_matrix,
    save_periodogram,
    save_quantile_response,
    save_regression,
    save_seasonal_calendar,
    save_stacked_panel,
    set_style,
)


def _toy(n: int = 400, seed: int = 0) -> tuple[pd.Series, pd.Series]:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    metric = pd.Series(
        np.sin(np.arange(n) / 30.0) + rng.normal(scale=0.2, size=n), index=idx, name="m",
    )
    raw = metric.to_numpy() * 3 + rng.normal(scale=1.0, size=n)
    commits = pd.Series(np.clip(raw, 0, None).round(), index=idx, name="commits")
    return commits, metric


def test_period_label_formats() -> None:
    s = period_label(date(2020, 1, 1), date(2020, 12, 31))
    assert "2020-01-01" in s and "2020-12-31" in s and "366d" in s


def test_set_style_returns_overrides() -> None:
    assert PlotStyle().dpi == 300
    s = set_style(font_scale=1.4, line_width=2.4, dpi=120, theme="light")
    assert isinstance(s, PlotStyle)
    assert s.font_scale == 1.4
    assert s.line_width == 2.4
    assert s.dpi == 120
    apply_rcparams(s)


def test_save_ccf_returns_result_and_writes(tmp_path: Path) -> None:
    c, m = _toy()
    out = tmp_path / "ccf.png"
    res = save_ccf(c, m, out=out, max_lag=20, prewhiten=True, metric_label="m",
                   period=(date(2020, 1, 1), date(2021, 2, 4)))
    assert out.is_file() and out.stat().st_size > 1500
    assert len(res.lags) == 41
    assert res.bartlett_ci > 0


def test_save_acf_pacf(tmp_path: Path) -> None:
    _, m = _toy()
    out = tmp_path / "acf.png"
    save_acf_pacf(m, out=out, n_lags=40, label="m")
    assert out.is_file() and out.stat().st_size > 1500


def test_save_periodogram(tmp_path: Path) -> None:
    c, m = _toy()
    out = tmp_path / "pg.png"
    res = save_periodogram(c, m, out=out, label_a="commits", label_b="m")
    assert out.is_file() and out.stat().st_size > 1500
    assert "commits" in res and "m" in res


def test_save_multi_user_views(tmp_path: Path) -> None:
    _, m = _toy()
    rng = np.random.default_rng(2)
    idx = m.index
    users: dict[str, pd.Series] = {}
    for i in range(3):
        v = m.to_numpy() * (i + 1) + rng.normal(size=len(idx))
        users[f"u{i}"] = pd.Series(np.clip(v, 0, None).round(), index=idx)
    save_multi_user_overview(
        users, m, out=tmp_path / "ov.png", window=20,
        period=(date(2020, 1, 1), date(2021, 2, 4)),
    )
    save_multi_user_rank_matrix(users, out=tmp_path / "ru.png", smoothing_window=10)
    save_multi_user_cumulative(users, m, out=tmp_path / "cu.png")
    save_multi_user_phase(users, m, out=tmp_path / "ph.png")
    df = multi_user_associations(users, pd.DataFrame({"m": m}), method="spearman")
    save_multi_user_heatmap(df, out=tmp_path / "hm.png")
    for fn in ("ov.png", "ru.png", "cu.png", "ph.png", "hm.png"):
        p = tmp_path / fn
        assert p.is_file() and p.stat().st_size > 1500


def test_save_quantile_response(tmp_path: Path) -> None:
    c, m = _toy()
    out = tmp_path / "qr.png"
    save_quantile_response(
        c, m, out=out, metric_label="m", n_bins=8,
        period=(date(2020, 1, 1), date(2021, 2, 4)),
    )
    assert out.is_file() and out.stat().st_size > 1500


def test_save_joint_density(tmp_path: Path) -> None:
    c, m = _toy()
    out = tmp_path / "jd.png"
    save_joint_density(c, m, out=out, metric_label="m")
    assert out.is_file() and out.stat().st_size > 1500


def test_save_seasonal_calendar_with_and_without_solar(tmp_path: Path) -> None:
    c, m = _toy(n=900)
    out1 = tmp_path / "cal_solar.png"
    save_seasonal_calendar(c, out=out1, solar=m, solar_label="SSN")
    out2 = tmp_path / "cal_only.png"
    save_seasonal_calendar(c, out=out2)
    for p in (out1, out2):
        assert p.is_file() and p.stat().st_size > 1500


def test_save_stacked_panel(tmp_path: Path) -> None:
    c, m = _toy(n=400)
    frame = pd.DataFrame({"m": m, "m2": m.shift(5).fillna(0.0)})
    out = tmp_path / "sp.png"
    save_stacked_panel(c, frame, out=out, ma_window=14)
    assert out.is_file() and out.stat().st_size > 1500


def test_save_ma_correlation_curve(tmp_path: Path) -> None:
    c, m = _toy(n=600)
    out = tmp_path / "ma.png"
    rows = save_ma_correlation_curve(
        c, m, out=out, metric_label="m", windows=[1, 7, 30, 90],
        period=(date(2020, 1, 1), date(2021, 8, 23)),
    )
    assert out.is_file() and out.stat().st_size > 1500
    assert {r["window"] for r in rows} == {1, 7, 30, 90}
    for r in rows:
        for k in (
            "n", "n_eff", "pearson_r", "pearson_lo", "pearson_hi", "pearson_p",
            "spearman_rho", "spearman_lo", "spearman_hi", "spearman_p",
        ):
            assert k in r
    pearson_r_at_30 = next(r for r in rows if r["window"] == 30)["pearson_r"]
    assert -1.0 <= pearson_r_at_30 <= 1.0


def test_save_dow_response_with_metric(tmp_path: Path) -> None:
    c, m = _toy(n=400)
    out = tmp_path / "dow.png"
    summary = save_dow_response(c, m, out=out, metric_label="m")
    assert out.is_file() and out.stat().st_size > 1500
    assert len(summary["dow_means"]) == 7
    assert "weekday_mean" in summary and "weekend_mean" in summary


def test_save_dow_response_commits_only(tmp_path: Path) -> None:
    c, _ = _toy(n=400)
    out = tmp_path / "dow_only.png"
    summary = save_dow_response(c, None, out=out)
    assert out.is_file() and out.stat().st_size > 1500
    assert len(summary["dow_means"]) == 7


def test_save_regression_returns_diagnostics(tmp_path: Path) -> None:
    c, m = _toy(n=400)
    out = tmp_path / "reg.png"
    diag = save_regression(
        c, m, out=out, metric_label="m",
        period=(date(2020, 1, 1), date(2021, 2, 4)),
    )
    assert out.is_file() and out.stat().st_size > 1500
    for k in (
        "n", "b0", "b1", "r2", "sigma2",
        "pearson_r", "pearson_p", "pearson_lo", "pearson_hi",
        "durbin_watson", "normality_stat", "normality_p",
    ):
        assert k in diag, f"missing diagnostic key: {k}"
    # DW lives in [0, 4]; resids of a real-ish series will not be exactly 2.
    assert 0.0 <= diag["durbin_watson"] <= 4.0
    # Normality test should produce a finite p for n=400.
    assert 0.0 <= diag["normality_p"] <= 1.0


def test_save_mi_lag_curve_writes_and_returns(tmp_path: Path) -> None:
    c, m = _toy(n=600)
    out = tmp_path / "mi_lag.png"
    res = save_mi_lag_curve(
        c, m, out=out, metric_label="m", max_lag=12, method="binned",
        period=(date(2020, 1, 1), date(2021, 8, 23)),
    )
    assert out.is_file() and out.stat().st_size > 1500
    assert res["method"] == "binned"
    assert len(res["lags"]) == 25  # ±12 inclusive
    assert len(res["values_nats"]) == 25
    assert isinstance(res["best_lag"], int)
    if res["best_value_nats"] is not None:
        assert res["best_value_nats"] >= 0.0
