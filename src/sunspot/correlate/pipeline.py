"""Single-user correlation report orchestration."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from sunspot import __version__
from sunspot.align.join import join_on_dates, zscore
from sunspot.stats.correlation import (
    CCFResult,
    LagResult,
    association_metrics,
    bootstrap_corr_ci,
    cross_metric_corr_matrix,
    lag_correlation_search,
    partial_correlation,
    pearson_with_ci,
    rolling_pearson,
    spearman_with_ci,
)
from sunspot.stats.information import (
    mutual_information_binned,
    mutual_information_ksg,
    normalised_mi,
)
from sunspot.stats.multi_user import multi_user_associations
from sunspot.stats.per_repo import per_repo_associations
from sunspot.stats.spectral import lomb_scargle_periodogram
from sunspot.tables import write_analysis_tables
from sunspot.viz.mosaic import assemble_mosaic, save_executive_summary
from sunspot.viz.multi_user import (
    save_multi_user_cumulative,
    save_multi_user_heatmap,
    save_multi_user_overview,
    save_multi_user_phase,
    save_multi_user_rank_matrix,
)
from sunspot.viz.plots import (
    save_acf_pacf,
    save_ccf,
    save_commits_solar_dynamics,
    save_compare_users_moving_averages,
    save_distribution,
    save_dow_response,
    save_dual_axis,
    save_joint_density,
    save_lag_grid,
    save_lag_heatmap,
    save_lag_plot,
    save_ma_correlation_curve,
    save_metric_correlation_matrix,
    save_metrics_zscored_overview,
    save_mi_lag_curve,
    save_monthly,
    save_periodogram,
    save_quantile_response,
    save_regression,
    save_repo_metric_spearman_heatmap,
    save_rolling_corr,
    save_scatter,
    save_seasonal_calendar,
    save_stacked_panel,
    save_top_repos_ma,
)
from sunspot.viz.style import set_style

from ._constants import DIR_ANALYSIS, DIR_DATA, DIR_STATISTICS, DIR_VIS
from ._io import (
    _write_commit_rollups,
    _write_methods,
    _write_per_repo_commits,
    _write_per_user_commits,
)
from ._report_helpers import (
    _ccf_profile_rows,
    _commits_daily_summary,
    _format_summary,
    _lag_profile_rows,
    _spearman_p_array,
    _spectral_band_power_rows,
)
from ._series import _series_for_metric

_LOG = logging.getLogger(__name__)
def run_correlation_report(
    user: str,
    *,
    since: date,
    until: date,
    metrics: list[str],
    out_dir: Path,
    use_commit_cache: bool = True,
    compare_user_logins: list[str] | None = None,
    rolling_window: int = 90,
    lag_max: int = 60,
    make_mosaic: bool = True,
    bootstrap: int = 0,
    prewhiten: bool = True,
    top_repos: int = 8,
    enable_acf: bool = True,
    enable_spectral: bool = True,
    style_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Write results under ``out_dir`` with:

    - ``statistics/report.json`` — associations, CI/FDR, lag profile, CCF,
      ``commits_summary`` (daily totals, DOW means, streaks),
      ``ma_correlations`` (per-window Pearson + Spearman of MA(commits) vs
      MA(metric) at 1/3/7/14/30/60/90/180/365 d),
      ``partial_correlation_ar1`` (controls for one-day-lagged commits and
      metric), ``mutual_information`` (binned-MM nats + KSG nats + normalised
      MI), ``mi_lag`` (MI vs integer day-lag profile), and
      ``regression_ols`` (R², Durbin–Watson, residual normality).
    - ``data/commits/`` — every GitHub-derived series for the run:
      ``daily.csv``, ``weekly.csv``, ``monthly.csv``, ``dow_means.csv``,
      ``summary.csv``, ``manifest.json``, ``by_repo/{owner__repo}.csv``,
      and — when ``compare_user_logins`` is set —
      ``by_user/{login}.csv`` + ``by_user/manifest.json``.
    - ``data/{metric}/`` — ``aligned_daily.csv`` and ``rolling.csv``.
    - ``visualizations/{metric}/`` — dual_axis, scatter, joint_density,
      regression, rolling_corr, ma_corr_curve, quantile_response,
      distribution, monthly, lag, lag_heatmap, ccf, acf_pacf, periodogram.
    - ``visualizations/dynamics/`` — solar-scale overlays.
    - ``visualizations/overview/`` — cross-metric matrix, lag_grid,
      z-overview, stacked_panel, seasonal_calendar, dow_response.
    - ``visualizations/per_repo/`` — top_repos_30d_ma, repo_metric_spearman_heatmap.
    - ``visualizations/mosaic.png`` and ``mosaic_index.json`` — graphical abstract.
    - ``analysis/`` — ``summary.txt``, ``methods.md``,
      ``per_repo_summary.csv``, and ``tables/*.csv`` — one CSV per
      statistical block (associations, lag profile, CCF profile, MA
      correlations, MI lag, regression OLS, …); see
      [`sunspot.tables`](tables.py) for the schema list.
    """
    out_dir = Path(out_dir)
    stats_dir = out_dir / DIR_STATISTICS
    data_dir = out_dir / DIR_DATA
    vis_dir = out_dir / DIR_VIS
    analysis_dir = out_dir / DIR_ANALYSIS
    stats_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    analysis_dir.mkdir(parents=True, exist_ok=True)

    if style_overrides:
        applied = set_style(**style_overrides)
        _LOG.info(
            "viz style: font_scale=%.2f line_width=%.2f dpi=%d theme=%s",
            applied.font_scale, applied.line_width, applied.dpi, applied.theme,
        )
    period: tuple[date, date] = (since, until)
    import sunspot.correlate as _cor_mod
    _public_commit_time_series = _cor_mod.public_commit_time_series

    t0 = time.perf_counter()
    _LOG.info("phase: fetch GitHub public commit timeseries")
    commits_map = _public_commit_time_series(
        user, since=since, until=until, use_commit_cache=use_commit_cache
    )
    t1 = time.perf_counter()
    _LOG.info("phase: GitHub done in %.1fs", t1 - t0)
    raw = commits_map.get("__all__", pd.Series(dtype="float", name="commits"))
    idx = pd.date_range(pd.Timestamp(since), pd.Timestamp(until), freq="D")
    commits = raw.reindex(idx).fillna(0.0)
    commits.name = "commits"
    commits_dir = data_dir / "commits"
    commits_dir.mkdir(parents=True, exist_ok=True)
    daily_path = commits_dir / "daily.csv"
    commits.to_csv(daily_path)
    by_repo = _write_per_repo_commits(commits_dir, commits_map, since=since, until=until)
    _LOG.info(
        "wrote per-repo series under %s (%s repos)",
        commits_dir / "by_repo",
        len(by_repo),
    )
    _LOG.info(
        "wrote %s (%s rows) days_with_commits=%s commits_total=%s",
        daily_path,
        len(commits),
        int((commits > 0).sum()),
        float(commits.sum()),
    )

    vis_dyn = vis_dir / "dynamics"
    vis_dyn.mkdir(parents=True, exist_ok=True)
    try:
        ssn = _series_for_metric("ssn", since=since, until=until)
        f1 = _series_for_metric("f107", since=since, until=until)
        save_commits_solar_dynamics(
            commits,
            ssn,
            f1,
            out=vis_dyn / "commits_and_solar.png",
            title=f"GitHub {user} — commits vs solar (UTC day)",
            period=period,
        )
        _LOG.info("wrote %s (7d/30d MA, z-SSN, z-F10.7)", vis_dyn / "commits_and_solar.png")
    except Exception as e:  # noqa: BLE001
        _LOG.warning("dynamics panel skipped: %s", e)

    commits_summary = _commits_daily_summary(commits)
    rollups = _write_commit_rollups(commits_dir, commits, commits_summary)
    _LOG.info(
        "wrote commit roll-ups: %s",
        ", ".join(p.name for p in rollups),
    )
    _LOG.info(
        "commits daily: total=%s active=%s/%s (%.1f%%) "
        "mean/day=%.3f mean/active=%.2f max=%s on %s "
        "weekday/weekend share=%.0f%%/%.0f%% streaks active=%sd quiet=%sd",
        int(commits.sum()),
        commits_summary["days_with_commits"], commits_summary["total_days"],
        100.0 * (commits_summary["active_days_fraction"] or 0.0),
        commits_summary["mean_per_day"], commits_summary["mean_per_active_day"],
        int(commits_summary["max_day"]) if np.isfinite(commits_summary["max_day"]) else None,
        commits_summary["max_day_date"],
        100.0 * (commits_summary["weekday_share"] or 0.0),
        100.0 * (commits_summary["weekend_share"] or 0.0),
        commits_summary["longest_active_streak_days"],
        commits_summary["longest_quiet_streak_days"],
    )

    report: dict[str, Any] = {
        "version": __version__,
        "user": user,
        "since": since.isoformat(),
        "until": until.isoformat(),
        "use_commit_cache": use_commit_cache,
        "rolling_window": rolling_window,
        "lag_max": lag_max,
        "bootstrap": int(bootstrap),
        "prewhiten": bool(prewhiten),
        "acf_disabled": not enable_acf,
        "spectral_disabled": not enable_spectral,
        "requested_metrics": list(metrics),
        "per_repo_repos": len(by_repo),
        "commits_total": float(commits.sum()),
        "commits_summary": commits_summary,
        "metrics": {},
        "output_layout": {
            "root": str(out_dir),
            "statistics": str(stats_dir),
            "data": str(data_dir),
            "visualizations": str(vis_dir),
            "dynamics": str(vis_dyn),
            "analysis": str(analysis_dir),
        },
    }

    extra_logins = [u.strip() for u in (compare_user_logins or []) if u and u.strip()]
    extra_logins = [u for u in extra_logins if u != user]
    umap: dict[str, pd.Series] = {user: commits}
    if extra_logins:
        for u2 in extra_logins:
            cm2 = _public_commit_time_series(
                u2, since=since, until=until, use_commit_cache=use_commit_cache,
            )
            a2 = cm2.get("__all__", pd.Series(dtype=float))
            umap[u2] = a2.reindex(idx).fillna(0.0)
            umap[u2].name = "commits"
        per_user_manifest = _write_per_user_commits(commits_dir, umap)
        _LOG.info(
            "wrote per-user series under %s (%s users)",
            commits_dir / "by_user",
            len(per_user_manifest),
        )
        try:
            ssn_c = _series_for_metric("ssn", since=since, until=until)
            save_compare_users_moving_averages(
                umap, ssn_c,
                out=vis_dyn / "compare_users_30d_ma.png", window=30, period=period,
            )
            _LOG.info(
                "wrote %s (multi-user 30d MA + z-SSN)", vis_dyn / "compare_users_30d_ma.png",
            )
        except Exception as e:  # noqa: BLE001
            _LOG.warning("compare-users plot failed: %s", e)
    report["compare_user_logins"] = extra_logins

    metric_frames: dict[str, pd.Series] = {}
    lag_results: dict[str, LagResult] = {}
    ccf_results: dict[str, CCFResult] = {}
    for m in metrics:
        _LOG.info("metric %s: load geodata + correlate + write", m)
        try:
            geo = _series_for_metric(m, since=since, until=until)
        except Exception as e:  # noqa: BLE001
            _LOG.error("metric %s: failed: %s", m, e)
            report["metrics"][m] = {"error": str(e)}
            continue
        mdata = data_dir / m
        mdata.mkdir(parents=True, exist_ok=True)
        mvis = vis_dir / m
        mvis.mkdir(parents=True, exist_ok=True)
        dff = join_on_dates(commits, geo.rename("geo"))
        c = dff["commits"]
        g = dff["geo"]
        msk = c.notna() & g.notna()
        if msk.sum() < 2:
            _LOG.warning("metric %s: insufficient overlap (aligned points=%s)", m, msk.sum())
            report["metrics"][m] = {"error": "insufficient overlap for correlation"}
            continue
        aligned = pd.DataFrame({"commits": c, m: g}).dropna()
        (mdata / "aligned_daily.csv").write_text(aligned.to_csv(), encoding="utf-8")
        n_aligned = int(len(aligned))
        asso = association_metrics(c, g)
        r, lo, hi, p_pearson, n = pearson_with_ci(c, g)
        lag = lag_correlation_search(c, zscore(g), max_lag=lag_max, method="spearman")
        lag_results[m] = lag
        roll = rolling_pearson(c, zscore(g), window=rolling_window)
        ps = _spearman_p_array(lag)
        lag_profile = _lag_profile_rows(lag, fdr_q=0.1)
        nfdr: int | None
        if ps.size and np.isfinite(ps).any():
            nfdr = sum(1 for row in lag_profile if row["fdr_significant"])
            j = int(np.nanargmin(np.where(np.isfinite(ps), ps, np.inf)))
            profile_p_min = float(ps[j]) if np.isfinite(ps[j]) else float("nan")
            profile_p_min_lag = int(lag.lags[j])
        else:
            nfdr = None
            profile_p_min = float("nan")
            profile_p_min_lag = int(lag.best_lag)
        sp_r, sp_lo, sp_hi, sp_p, _ = spearman_with_ci(c, g)
        block: dict[str, Any] = {
            "associations": [asdict(x) for x in asso],
            "lag": {
                "best_lag": int(lag.best_lag),
                "best": float(lag.best_value),
                "profile_p_min": profile_p_min,
                "profile_p_min_lag": profile_p_min_lag,
            },
            "lag_fdr_significant_count": nfdr,
            "lag_profile": lag_profile,
            "n_aligned": n_aligned,
            "pearson_ci95": {
                "r": float(r), "lo": float(lo), "hi": float(hi),
                "p": p_pearson, "n": int(n),
            },
            "spearman_ci95": {
                "rho": float(sp_r), "lo": float(sp_lo), "hi": float(sp_hi),
                "p": sp_p, "n": int(n),
            },
        }
        if bootstrap > 0:
            try:
                bp = bootstrap_corr_ci(c, g, method="pearson", n_boot=bootstrap)
                bs = bootstrap_corr_ci(c, g, method="spearman", n_boot=bootstrap)
                block["bootstrap_ci95"] = {
                    "n_boot": int(bootstrap),
                    "pearson":  {"r":   float(bp[0]), "lo": float(bp[1]),
                                 "hi":  float(bp[2])},
                    "spearman": {"rho": float(bs[0]), "lo": float(bs[1]),
                                 "hi":  float(bs[2])},
                }
            except (ValueError, RuntimeWarning) as e:
                _LOG.debug("metric %s: bootstrap skipped: %s", m, e)
        report["metrics"][m] = block
        (mdata / "rolling.csv").write_text(roll.to_csv(), encoding="utf-8")
        save_dual_axis(commits, g, out=mvis / "dual_axis.png",
                       right_label=m, period=period)
        try:
            save_scatter(commits, g, out=mvis / "scatter.png", metric_label=m, period=period)
        except ValueError:
            pass
        save_lag_plot(lag, out=mvis / "lag.png", metric_label=m, period=period)
        try:
            reg_diag = save_regression(
                commits, g, out=mvis / "regression.png",
                metric_label=m, period=period,
            )
            block["regression_ols"] = reg_diag
        except (ValueError, np.linalg.LinAlgError) as e:
            _LOG.debug("metric %s: regression skipped: %s", m, e)
        try:
            save_rolling_corr(
                commits, g, out=mvis / "rolling_corr.png",
                window=rolling_window, metric_label=m, period=period,
            )
        except (ValueError, KeyError) as e:
            _LOG.debug("metric %s: rolling_corr skipped: %s", m, e)
        try:
            save_lag_heatmap(commits, g, out=mvis / "lag_heatmap.png",
                             metric_label=m, period=period)
        except (ValueError, KeyError) as e:
            _LOG.debug("metric %s: lag_heatmap skipped: %s", m, e)
        try:
            save_distribution(commits, g, out=mvis / "distribution.png",
                              metric_label=m, period=period)
        except (ValueError, KeyError) as e:
            _LOG.debug("metric %s: distribution skipped: %s", m, e)
        try:
            save_monthly(commits, g, out=mvis / "monthly.png",
                         metric_label=m, period=period)
        except (ValueError, KeyError) as e:
            _LOG.debug("metric %s: monthly skipped: %s", m, e)
        try:
            ccf_res = save_ccf(
                commits, g, out=mvis / "ccf.png", max_lag=lag_max,
                method="pearson", prewhiten=prewhiten, metric_label=m, period=period,
            )
            ccf_results[m] = ccf_res
            arr = np.array(ccf_res.values, dtype=float)
            ccf_block: dict[str, Any] = {
                "method": ccf_res.method,
                "prewhiten": prewhiten,
                "n_eff": int(ccf_res.n),
                "bartlett_ci95": float(ccf_res.bartlett_ci),
            }
            if np.isfinite(arr).any():
                k = int(np.nanargmax(np.abs(arr)))
                ccf_block["peak_lag"] = int(ccf_res.lags[k])
                ccf_block["peak_value"] = float(arr[k])
            else:
                ccf_block["peak_lag"] = None
                ccf_block["peak_value"] = None
            ccf_profile = _ccf_profile_rows(ccf_res)
            ccf_block["significant_count"] = sum(
                1 for row in ccf_profile if row["crosses_bartlett_ci95"]
            )
            block["ccf_profile"] = ccf_profile
            block["ccf"] = ccf_block
        except (ValueError, KeyError) as e:
            _LOG.debug("metric %s: ccf skipped: %s", m, e)
        if enable_acf:
            try:
                save_acf_pacf(
                    g, out=mvis / "acf_pacf.png", n_lags=min(120, lag_max * 2),
                    label=m, period=period,
                )
            except (ValueError, KeyError) as e:
                _LOG.debug("metric %s: acf_pacf skipped: %s", m, e)
        try:
            save_quantile_response(
                commits, g, out=mvis / "quantile_response.png",
                metric_label=m, n_bins=10, period=period,
            )
        except (ValueError, KeyError) as e:
            _LOG.debug("metric %s: quantile_response skipped: %s", m, e)
        try:
            save_joint_density(
                commits, g, out=mvis / "joint_density.png",
                metric_label=m, period=period,
            )
        except (ValueError, KeyError) as e:
            _LOG.debug("metric %s: joint_density skipped: %s", m, e)
        try:
            ma_rows = save_ma_correlation_curve(
                commits, g, out=mvis / "ma_corr_curve.png",
                metric_label=m, period=period,
            )
            block["ma_correlations"] = ma_rows
        except (ValueError, KeyError) as e:
            _LOG.debug("metric %s: ma_corr_curve skipped: %s", m, e)
        try:
            cs = c.shift(1)
            gs = g.reindex(c.index).shift(1)
            ppr, ppp, ppn = partial_correlation(c, g, [cs, gs], method="pearson")
            psr, psp, psn = partial_correlation(c, g, [cs, gs], method="spearman")
            block["partial_correlation_ar1"] = {
                "controls": ["commits_lag1", "metric_lag1"],
                "pearson":  {"r":   float(ppr) if np.isfinite(ppr) else None,
                              "p":  ppp, "n": int(ppn)},
                "spearman": {"rho": float(psr) if np.isfinite(psr) else None,
                              "p":  psp, "n": int(psn)},
            }
        except (ValueError, np.linalg.LinAlgError) as e:
            _LOG.debug("metric %s: partial_correlation skipped: %s", m, e)
        try:
            mi_b, n_mi, bins_mi = mutual_information_binned(c, g)
            mi_k, _ = mutual_information_ksg(c, g, k=5)
            block["mutual_information"] = {
                "binned_nats": float(mi_b) if np.isfinite(mi_b) else None,
                "binned_normalised": (
                    float(normalised_mi(mi_b, n_mi, bins_mi))
                    if np.isfinite(mi_b) and bins_mi >= 2 else None
                ),
                "binned_bins": int(bins_mi),
                "ksg_nats": float(mi_k) if np.isfinite(mi_k) else None,
                "n": int(n_mi),
            }
        except (ValueError, RuntimeWarning) as e:
            _LOG.debug("metric %s: mutual_information skipped: %s", m, e)
        try:
            mi_lag = save_mi_lag_curve(
                commits, g, out=mvis / "mi_lag.png",
                metric_label=m, max_lag=lag_max, method="binned",
                period=period,
            )
            block["mi_lag"] = mi_lag
        except (ValueError, KeyError) as e:
            _LOG.debug("metric %s: mi_lag skipped: %s", m, e)
        if enable_spectral:
            try:
                pg = save_periodogram(
                    commits, g, out=mvis / "periodogram.png",
                    label_a="commits", label_b=m, period=period,
                )
                if "commits" in pg and "commits_periodogram_top5" not in report:
                    report["commits_periodogram_top5"] = [
                        {"period_days": float(pp), "power": float(pw)}
                        for pp, pw in pg["commits"].top_k(5)
                    ]
                    report["commits_spectral_band_power"] = _spectral_band_power_rows(
                        pg["commits"],
                    )
                if m in pg:
                    block["periodogram_top5"] = [
                        {"period_days": float(pp), "power": float(pw)}
                        for pp, pw in pg[m].top_k(5)
                    ]
                    block["dominant_period_days"] = float(pg[m].dominant_period_days)
                    block["spectral_band_power"] = _spectral_band_power_rows(pg[m])
            except (ValueError, KeyError) as e:
                _LOG.debug("metric %s: periodogram skipped: %s", m, e)
        _LOG.info(
            "metric %s: n=%s r=%.3f [%.3f, %.3f] ρ=%.3f [%.3f, %.3f] "
            "best_lag=%s peak_rho=%.3f",
            m, n_aligned,
            float(r), float(lo), float(hi),
            float(sp_r), float(sp_lo), float(sp_hi),
            int(lag.best_lag), float(lag.best_value),
        )
        metric_frames[m] = g.reindex(idx)

    overview_dir = vis_dir / "overview"
    overview_dir.mkdir(parents=True, exist_ok=True)
    if metric_frames:
        cm_frame = pd.DataFrame(metric_frames)
        try:
            save_metric_correlation_matrix(
                cm_frame.assign(commits=commits),
                out=overview_dir / "metric_correlation_matrix.png",
                period=period,
            )
            mat = cross_metric_corr_matrix(cm_frame)
            report["cross_metric_correlation"] = {
                a: {
                    b: (None if pd.isna(mat.loc[a, b]) else float(mat.loc[a, b]))
                    for b in mat.columns
                }
                for a in mat.index
            }
        except (ValueError, KeyError) as e:
            _LOG.debug("metric_correlation_matrix skipped: %s", e)
        try:
            save_metrics_zscored_overview(
                commits, cm_frame, out=overview_dir / "metrics_zscored_overview.png",
                ma_window=30, period=period,
            )
        except (ValueError, KeyError) as e:
            _LOG.debug("metrics_zscored_overview skipped: %s", e)
        try:
            save_stacked_panel(
                commits, cm_frame, out=overview_dir / "stacked_panel.png",
                ma_window=30, period=period,
            )
        except (ValueError, KeyError) as e:
            _LOG.debug("stacked_panel skipped: %s", e)
    try:
        ssn_cal = _series_for_metric("ssn", since=since, until=until)
    except Exception as e:  # noqa: BLE001
        _LOG.debug("seasonal calendar: SSN unavailable (%s); commits-only", e)
        ssn_cal = None
    try:
        save_seasonal_calendar(
            commits, out=overview_dir / "seasonal_calendar.png",
            solar=ssn_cal, solar_label="SSN", period=period,
        )
    except (ValueError, KeyError) as e:
        _LOG.debug("seasonal_calendar skipped: %s", e)
    try:
        primary_metric_name = next(iter(metric_frames)) if metric_frames else None
        primary_metric = (
            metric_frames[primary_metric_name] if primary_metric_name else None
        )
        dow_summary = save_dow_response(
            commits, primary_metric,
            out=overview_dir / "dow_response.png",
            metric_label=primary_metric_name, period=period,
        )
        report["commits_summary"]["dow_response"] = dow_summary
    except (ValueError, KeyError) as e:
        _LOG.debug("dow_response skipped: %s", e)
    if lag_results:
        try:
            save_lag_grid(lag_results, out=overview_dir / "lag_grid.png", period=period)
        except (ValueError, KeyError) as e:
            _LOG.debug("lag_grid skipped: %s", e)
    if enable_acf:
        try:
            save_acf_pacf(
                commits, out=overview_dir / "commits_acf_pacf.png",
                n_lags=min(180, lag_max * 3), label="commits", period=period,
            )
        except (ValueError, KeyError) as e:
            _LOG.debug("commits acf/pacf skipped: %s", e)
    if enable_spectral:
        try:
            save_periodogram(
                commits, None, out=overview_dir / "commits_periodogram.png",
                label_a="commits", period=period,
            )
            commits_pg = lomb_scargle_periodogram(commits)
            if commits_pg.power.size:
                report["commits_dominant_period_days"] = float(commits_pg.dominant_period_days)
                report.setdefault(
                    "commits_spectral_band_power",
                    _spectral_band_power_rows(commits_pg),
                )
        except (ValueError, KeyError) as e:
            _LOG.debug("commits periodogram skipped: %s", e)

    per_repo_dir = vis_dir / "per_repo"
    per_repo_dir.mkdir(parents=True, exist_ok=True)
    if metric_frames:
        try:
            cm_frame = pd.DataFrame(metric_frames)
            df_pr = per_repo_associations(commits_map, cm_frame, method="spearman")
            (analysis_dir / "per_repo_summary.csv").write_text(
                df_pr.to_csv(index=False), encoding="utf-8"
            )
            top_rows = (
                df_pr.assign(absrho=df_pr["rho"].abs())
                .sort_values("absrho", ascending=False)
                .head(10)
                .drop(columns=["absrho"])
            )
            report["per_repo_topk"] = top_rows.to_dict(orient="records")
            try:
                save_repo_metric_spearman_heatmap(
                    df_pr,
                    out=per_repo_dir / "repo_metric_spearman_heatmap.png",
                    metric_order=list(metric_frames.keys()),
                    period=period,
                )
            except (ValueError, KeyError) as e:
                _LOG.debug("repo_metric_spearman_heatmap skipped: %s", e)
        except (ValueError, KeyError) as e:
            _LOG.debug("per-repo associations skipped: %s", e)
        try:
            ssn_t = _series_for_metric("ssn", since=since, until=until)
            save_top_repos_ma(
                commits_map, ssn_t,
                out=per_repo_dir / "top_repos_30d_ma.png",
                top_n=top_repos, window=30, period=period,
            )
        except (ValueError, KeyError) as e:
            _LOG.debug("top_repos_30d_ma skipped: %s", e)

    if len(umap) >= 2 and metric_frames:
        mu_dir = vis_dir / "multi_user"
        mu_dir.mkdir(parents=True, exist_ok=True)
        try:
            ssn_mu = _series_for_metric("ssn", since=since, until=until)
            save_multi_user_overview(
                umap, ssn_mu, out=mu_dir / "overview_30d_ma.png",
                window=30, period=period,
            )
        except (ValueError, KeyError) as e:
            _LOG.debug("multi-user overview skipped: %s", e)
        try:
            cm_frame = pd.DataFrame(metric_frames)
            mu_long = multi_user_associations(umap, cm_frame, method="spearman")
            (analysis_dir / "multi_user_associations.csv").write_text(
                mu_long.to_csv(index=False), encoding="utf-8",
            )
            save_multi_user_heatmap(
                mu_long, out=mu_dir / "user_metric_spearman_heatmap.png",
                metric_order=list(metric_frames.keys()), period=period,
            )
            report["multi_user_topk"] = (
                mu_long.assign(absrho=mu_long["rho"].abs())
                .sort_values("absrho", ascending=False)
                .head(10)
                .drop(columns=["absrho"])
                .to_dict(orient="records")
            )
        except (ValueError, KeyError) as e:
            _LOG.debug("multi-user heatmap/associations skipped: %s", e)
        try:
            save_multi_user_rank_matrix(
                umap, out=mu_dir / "user_user_rank_matrix.png",
                smoothing_window=30, method="spearman", period=period,
            )
        except (ValueError, KeyError) as e:
            _LOG.debug("multi-user rank matrix skipped: %s", e)
        try:
            ssn_mu = _series_for_metric("ssn", since=since, until=until)
            save_multi_user_cumulative(
                umap, ssn_mu, out=mu_dir / "cumulative_vs_solar.png", period=period,
            )
            save_multi_user_phase(
                umap, ssn_mu, out=mu_dir / "phase_by_ssn_quantile.png", period=period,
            )
        except (ValueError, KeyError) as e:
            _LOG.debug("multi-user cumulative/phase skipped: %s", e)

    (stats_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (analysis_dir / "summary.txt").write_text(_format_summary(report), encoding="utf-8")
    _write_methods(out_dir, report)
    try:
        written = write_analysis_tables(
            report, analysis_dir,
            lag_results=lag_results, ccf_results=ccf_results,
        )
        _LOG.info(
            "wrote %s analysis tables under %s: %s",
            len(written), analysis_dir / "tables",
            ", ".join(p.name for p in written),
        )
    except (OSError, ValueError) as e:
        _LOG.warning("analysis tables failed: %s", e)

    try:
        es = save_executive_summary(
            out_dir, out=out_dir / "visualizations" / "executive_summary.png",
        )
        report["executive_summary"] = str(es)
        (stats_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        _LOG.info("wrote %s (top-level summary card)", es)
    except (OSError, ValueError, FileNotFoundError) as e:
        _LOG.warning("executive summary failed: %s", e)

    if make_mosaic:
        try:
            mp = assemble_mosaic(out_dir, metrics=list(metrics))
            report["mosaic"] = str(mp)
            (stats_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        except (OSError, ValueError) as e:
            _LOG.warning("mosaic assembly failed: %s", e)

    t2 = time.perf_counter()
    n_png = sum(1 for _ in vis_dir.rglob("*.png")) if vis_dir.exists() else 0
    n_tables = sum(1 for _ in (analysis_dir / "tables").glob("*.csv"))
    _LOG.info(
        "done: statistics=%s | pngs=%s analysis_tables=%s | total wall %.1fs",
        stats_dir / "report.json",
        n_png,
        n_tables,
        t2 - t0,
    )
    return report
