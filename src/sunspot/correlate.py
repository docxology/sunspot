"""High-level: join commit activity with geophysical series and emit artifacts."""

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
from sunspot.align.join import clip_to_window, join_on_dates, zscore
from sunspot.datasets import load_omni2_daily, load_silso_daily_tot_v2
from sunspot.github.commit_cache import commit_series_dir, github_data_dir
from sunspot.github.commits import public_commit_time_series
from sunspot.stats.correlation import (
    CCFResult,
    LagResult,
    association_metrics,
    bootstrap_corr_ci,
    cross_metric_corr_matrix,
    fdr_on_pvalues,
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
from sunspot.stats.spectral import band_power, lomb_scargle_periodogram
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

_LOG = logging.getLogger(__name__)

SPECTRAL_BANDS_DAYS: dict[str, tuple[float, float]] = {
    "weekly": (6.0, 8.0),
    "solar_rotation": (24.0, 31.0),
    "annual": (330.0, 400.0),
    "solar_cycle": (3650.0, 4380.0),
}

OUTPUT_ROOT = Path("output")

DIR_STATISTICS = "statistics"
DIR_DATA = "data"
DIR_VIS = "visualizations"
DIR_ANALYSIS = "analysis"


def default_correlate_dir(user: str, since: date, until: date) -> Path:
    """Default run directory: ``output/correlate/{user}__{since}__{until}/``."""
    safe_user = user.replace("\\", "_").replace("/", "_")
    slug = f"{safe_user}__{since.isoformat()}__{until.isoformat()}"
    return OUTPUT_ROOT / "correlate" / slug


def _safe_login(name: str) -> str:
    """Sanitize a GitHub login or repo full-name segment for use as a filename."""
    return name.replace("\\", "_").replace("/", "_")


def _safe_repo_filename(full_name: str) -> str:
    return full_name.replace("/", "__")


def _write_per_repo_commits(
    commits_dir: Path,
    commits_map: dict[str, pd.Series],
    *,
    since: date,
    until: date,
) -> list[dict[str, Any]]:
    """Write ``data/commits/by_repo/*.csv`` and return a small manifest list."""
    base = commits_dir / "by_repo"
    base.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    for k, s in commits_map.items():
        if not k or k == "__all__":
            continue
        s2 = s.sort_index()
        tot = float(s2.sum()) if len(s2) else 0.0
        fn = f"{_safe_repo_filename(k)}.csv"
        (base / fn).write_text(s2.to_csv(), encoding="utf-8")
        manifest.append({"repo": k, "file": f"by_repo/{fn}", "commits_in_window": tot})
    (commits_dir / "manifest.json").write_text(
        json.dumps(
            {"since": since.isoformat(), "until": until.isoformat(), "repos": manifest},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def _write_commit_rollups(
    commits_dir: Path,
    commits: pd.Series,
    summary: dict[str, Any],
) -> list[Path]:
    """
    Write weekly / monthly / day-of-week roll-ups and a one-row daily summary
    CSV next to ``commits/daily.csv``. Returns the paths written.
    """
    commits_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    weekly = commits.resample("W-MON", label="left", closed="left").sum().rename("commits")
    weekly.index = weekly.index.rename("week_starting")
    p = commits_dir / "weekly.csv"
    weekly.to_csv(p)
    paths.append(p)

    monthly = commits.resample("MS").sum().rename("commits")
    monthly.index = monthly.index.rename("month_starting")
    p = commits_dir / "monthly.csv"
    monthly.to_csv(p)
    paths.append(p)

    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    s = commits.sort_index().astype(float).fillna(0.0)
    dow = pd.to_datetime(s.index).dayofweek
    rows = []
    for k, lab in enumerate(labels):
        sel = s[dow == k]
        n_days = int(sel.size)
        rows.append({
            "dow": lab,
            "n_days": n_days,
            "mean": float(sel.mean()) if n_days else float("nan"),
            "median": float(sel.median()) if n_days else float("nan"),
            "total": float(sel.sum()) if n_days else 0.0,
        })
    p = commits_dir / "dow_means.csv"
    pd.DataFrame(rows).to_csv(p, index=False)
    paths.append(p)

    serialisable = {
        k: v for k, v in summary.items()
        if not isinstance(v, list | dict)
    }
    p = commits_dir / "summary.csv"
    pd.DataFrame([serialisable]).to_csv(p, index=False)
    paths.append(p)

    return paths


def _write_per_user_commits(
    commits_dir: Path,
    user_series: dict[str, pd.Series],
) -> list[dict[str, Any]]:
    """Write ``data/commits/by_user/{login}.csv`` for compare-users runs."""
    base = commits_dir / "by_user"
    base.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    for login, s in user_series.items():
        if not login:
            continue
        s2 = s.sort_index().astype(float).rename("commits")
        fn = f"{_safe_login(login)}.csv"
        s2.to_csv(base / fn)
        manifest.append({
            "user": login,
            "file": f"by_user/{fn}",
            "commits_in_window": float(s2.sum()),
            "active_days": int((s2 > 0).sum()),
        })
    (base / "manifest.json").write_text(
        json.dumps({"users": manifest}, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def _years_between(s0: date, s1: date) -> list[int]:
    return list(range(s0.year, s1.year + 1))


def _series_for_metric(m: str, *, since: date, until: date) -> pd.Series:
    m = m.strip().lower()
    if m == "ssn":
        sil = load_silso_daily_tot_v2()
        s = clip_to_window(sil["ssn"], since, until)
        s.name = "ssn"
        return s
    if m in {"f107", "dst", "ap", "r_ssn"}:
        years = _years_between(since, until)
        d = load_omni2_daily(years, cache=True)
        dcol = {"f107": "f107", "dst": "dst", "ap": "ap_nT", "r_ssn": "r_ssn"}[m]
        s = clip_to_window(d[dcol], since, until)
        s.name = m
        return s
    raise ValueError(f"unknown metric: {m!r}")


def _write_methods(out_root: Path, report: dict[str, Any] | None = None) -> None:
    cdir = commit_series_dir()
    gdb = github_data_dir()
    report = report or {}
    metric_names = list((report.get("metrics") or {}).keys()) or list(
        report.get("requested_metrics") or [],
    )
    metrics = ", ".join(metric_names) or "run metrics"
    lag_max = report.get("lag_max", "max_lag")
    rolling_window = report.get("rolling_window", 90)
    bootstrap = report.get("bootstrap", 0)
    prewhiten = report.get("prewhiten", True)
    enable_acf = not report.get("acf_disabled", False)
    enable_spectral = not report.get("spectral_disabled", False)
    methods = f"""\
# Methods (sunspot)

## Run settings

- Window: `{report.get("since", "?")}` to `{report.get("until", "?")}`.
- Metrics: `{metrics}`.
- Rolling window: `{rolling_window}` days.
- Lag search: `±{lag_max}` days; lag-profile BH-FDR uses `q=0.10`.
- Bootstrap iterations: `{bootstrap}`.
- CCF AR(1) pre-whitening: `{prewhiten}`.
- ACF/PACF panels: `{enable_acf}`. Lomb-Scargle panels: `{enable_spectral}`.

## Inputs

- **GitHub commits** — public, non-fork repositories of the user; per-repo time series
  retrieved via the REST `commits` endpoint, normalized to UTC dates, then aggregated
  to a daily count. Per-repo series are cached on disk under
  `{cdir}/` (portable; see `output/github_data/README.md`). Commit SHA dedup uses
  `{gdb / "github_cache.sqlite3"}` unless `SUNSPOT_CACHE` is set. Legacy cache hits may
  still read `~/.cache/sunspot/commit_series/`.
- **SILSO daily total sunspot number V2.0** (`ssn`) — Brussels SIDC.
- **NASA SPDF OMNI2 daily** — F10.7 cm radio flux (`f107`), Dst index (`dst`),
  ap-index in nT (`ap`), and OMNI's daily R sunspot number (`r_ssn`); aggregated
  from hourly via arithmetic mean.

## Statistics

- Per metric: Pearson r (with 95% Fisher-z CI), Spearman rho (Bonett-Wright CI),
  Kendall tau, plus a lag search in `±{lag_max}` days (Spearman). Best lag,
  minimum profile p, and per-lag FDR flags are recorded.
- Optional percentile bootstrap CIs (paired resampling) when --bootstrap > 0.
- Rolling Pearson and Spearman over the configured `{rolling_window}` day window.
- Lag x window grid (heatmap) over lag in [-60, 60] step 5 and windows of
  30, 90, 180, 365 days.
- Cross-correlation function (CCF) with Bartlett +/- 95% bands; AR(1)
  pre-whitening follows this run's `prewhiten={prewhiten}` setting.
- ACF and PACF (Durbin-Levinson) for commits and each metric.
- Lomb-Scargle periodogram for commits and each metric (peak periods and named
  band-power fractions reported when spectral output is enabled).
- Cross-metric pairwise Spearman matrix.
- Per-repo Spearman with Benjamini-Hochberg FDR control across repos within
  each metric (q = 0.10).
- Multi-user mode: per-user x metric Spearman heatmap with FDR, user x user
  rank matrix on smoothed activity, cumulative-commits-vs-solar, and a
  solar-quantile phase plot.

## Caveats

- Public commits only; squashes and force-pushes can re-time history.
- Solar/geomagnetic indices have annual to decadal cycles; high autocorrelation
  inflates raw p-values. Treat all coefficients as exploratory.
- Detrending and seasonal models are not applied here.
"""
    (out_root / DIR_ANALYSIS).mkdir(parents=True, exist_ok=True)
    (out_root / DIR_ANALYSIS / "methods.md").write_text(methods, encoding="utf-8")


def _fmtf(v: Any, spec: str = ".3f") -> str:
    try:
        f = float(v) if v is not None else float("nan")
    except (TypeError, ValueError):
        return "nan"
    return format(f, spec)


def _format_summary(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"user={report.get('user')}")
    lines.append(f"range_utc={report.get('since')}..{report.get('until')}")
    lines.append(f"tool_version={report.get('version')}")
    lines.append(f"repos_total={report.get('per_repo_repos')}")
    lines.append(f"commits_total={report.get('commits_total')}")
    cs = report.get("commits_summary") or {}
    if cs:
        lines.append("")
        lines.append("Daily commit activity:")
        lines.append(
            f"  total_days={cs.get('total_days')}"
            f"  active_days={cs.get('days_with_commits')}"
            f" ({(cs.get('active_days_fraction') or 0.0) * 100:.1f}%)"
            f"  first/last_active={cs.get('first_commit_date')}..{cs.get('last_commit_date')}",
        )
        lines.append(
            f"  mean/day={_fmtf(cs.get('mean_per_day'))}"
            f"  mean/active_day={_fmtf(cs.get('mean_per_active_day'))}"
            f"  median/day={_fmtf(cs.get('median_per_day'))}"
            f"  p95={_fmtf(cs.get('p95_per_day'))}"
            f"  max={_fmtf(cs.get('max_day'), '.0f')} on {cs.get('max_day_date')}",
        )
        lines.append(
            f"  streaks: longest_active={cs.get('longest_active_streak_days')}d"
            f"  longest_quiet={cs.get('longest_quiet_streak_days')}d",
        )
        dows = cs.get("dow_means_mon_to_sun") or []
        if dows:
            labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            parts = "  ".join(f"{lab}={_fmtf(v, '.2f')}"
                              for lab, v in zip(labels, dows, strict=True))
            lines.append(f"  DOW mean/day:  {parts}")
        lines.append(
            f"  share weekday={(cs.get('weekday_share') or 0.0) * 100:.1f}%"
            f"  weekend={(cs.get('weekend_share') or 0.0) * 100:.1f}%",
        )
    lines.append("")
    lines.append("Per-metric (commits vs metric, exploratory only — not causal):")
    lines.append("")
    mets = report.get("metrics") or {}
    for name, block in mets.items():
        if "error" in block:
            lines.append(f"  {name}: {block['error']}")
            continue
        n = block.get("n_aligned")
        ci = block.get("pearson_ci95") or {}
        sci = block.get("spearman_ci95") or {}
        asso = block.get("associations") or []
        pe = next((a for a in asso if a.get("kind") == "pearson"), {})
        kt = next((a for a in asso if a.get("kind") == "kendall"), {})
        lag = block.get("lag") or {}
        ccf = block.get("ccf") or {}
        lines.append(
            f"  {name}: n={n}  Pearson r={_fmtf(pe.get('value'))}"
            f" [{_fmtf(ci.get('lo'))}, {_fmtf(ci.get('hi'))}]"
            f"  p={_fmtf(pe.get('p'), '.2g')}",
        )
        lines.append(
            f"      Spearman rho={_fmtf(sci.get('rho'))}"
            f" [{_fmtf(sci.get('lo'))}, {_fmtf(sci.get('hi'))}]"
            f"  p={_fmtf(sci.get('p'), '.2g')}"
            f"   |   Kendall tau={_fmtf(kt.get('value'))}"
            f"  p={_fmtf(kt.get('p'), '.2g')}",
        )
        bs = block.get("bootstrap_ci95")
        if bs:
            bp = bs.get("pearson") or {}
            br = bs.get("spearman") or {}
            lines.append(
                f"      bootstrap (n_boot={bs.get('n_boot')}):"
                f"  r={_fmtf(bp.get('r'))} [{_fmtf(bp.get('lo'))}, {_fmtf(bp.get('hi'))}]"
                f"   rho={_fmtf(br.get('rho'))} [{_fmtf(br.get('lo'))}, {_fmtf(br.get('hi'))}]",
            )
        nfdr = block.get("lag_fdr_significant_count")
        lines.append(
            f"      best lag={lag.get('best_lag')} d"
            f"  peak rho={_fmtf(lag.get('best'))}"
            f"   profile_p_min={_fmtf(lag.get('profile_p_min'), '.2g')}"
            f"   FDR-significant lags={nfdr if nfdr is not None else 'n/a'}",
        )
        if ccf:
            pv = ccf.get("peak_value")
            pl = ccf.get("peak_lag")
            peak_str = (
                f"peak {_fmtf(pv)} @ lag={pl}d" if pv is not None and pl is not None
                else "peak n/a"
            )
            lines.append(
                f"      CCF ({'AR1-pw' if ccf.get('prewhiten') else 'raw'}):"
                f" {peak_str}"
                f"   ±95% Bartlett band=±{_fmtf(ccf.get('bartlett_ci95'))}"
                f"   n_eff={ccf.get('n_eff')}",
            )
        ma = block.get("ma_correlations") or []
        if ma:
            top = max(ma, key=lambda r: abs(float(r.get("pearson_r") or 0.0)))
            lines.append(
                "      MA-r:  " + "  ".join(
                    f"w{int(r['window']):>3}d r={_fmtf(r.get('pearson_r'), '+.2f')}"
                    for r in ma
                ),
            )
            lines.append(
                f"             (peak |r|={_fmtf(abs(float(top.get('pearson_r') or 0.0)), '.2f')}"
                f" @ MA{int(top.get('window'))}d, p={_fmtf(top.get('pearson_p'), '.2g')})",
            )
        pc = block.get("partial_correlation_ar1") or {}
        if pc:
            ppe = pc.get("pearson") or {}
            psp = pc.get("spearman") or {}
            lines.append(
                f"      partial (controls={','.join(pc.get('controls', []))}):"
                f"  r={_fmtf(ppe.get('r'))}  p={_fmtf(ppe.get('p'), '.2g')}"
                f"   ρ={_fmtf(psp.get('rho'))}  p={_fmtf(psp.get('p'), '.2g')}"
                f"   n={ppe.get('n')}",
            )
        mi = block.get("mutual_information") or {}
        ml = block.get("mi_lag") or {}
        if mi or ml:
            seg = []
            if mi.get("binned_nats") is not None:
                seg.append(
                    f"binned={_fmtf(mi.get('binned_nats'), '.3f')} nat"
                    f" (norm={_fmtf(mi.get('binned_normalised'), '.2f')},"
                    f" bins={mi.get('binned_bins')})",
                )
            if mi.get("ksg_nats") is not None:
                seg.append(f"KSG={_fmtf(mi.get('ksg_nats'), '.3f')} nat")
            if ml.get("best_value_nats") is not None:
                seg.append(
                    f"peak={_fmtf(ml.get('best_value_nats'), '.3f')} nat"
                    f" @ lag={ml.get('best_lag')}d",
                )
            if seg:
                lines.append("      MI:    " + "  ".join(seg))
        rd = block.get("regression_ols") or {}
        if rd:
            seg = [
                f"R²={_fmtf(rd.get('r2'), '+.3f')}",
                f"DW={_fmtf(rd.get('durbin_watson'), '.2f')}",
            ]
            if rd.get("normality_p") is not None:
                seg.append(f"norm-p={_fmtf(rd.get('normality_p'), '.2g')}")
            lines.append("      OLS:   " + "  ".join(seg))
        dom = block.get("dominant_period_days")
        if dom is not None:
            lines.append(f"      dominant period (LS): {_fmtf(dom, '.1f')} d")
    cm = report.get("cross_metric_correlation") or {}
    if cm:
        lines.append("")
        lines.append("Cross-metric Spearman (top |rho| pairs):")
        pairs: list[tuple[str, str, float]] = []
        cols = list(cm.keys())
        for i, a in enumerate(cols):
            for b in cols[i + 1 :]:
                v = cm.get(a, {}).get(b)
                if v is None or v != v:  # skip NaN
                    continue
                pairs.append((a, b, float(v)))
        pairs.sort(key=lambda t: abs(t[2]), reverse=True)
        for a, b, v in pairs[:6]:
            lines.append(f"  {a:>6} vs {b:<6}  rho={v:+.3f}")
    pr = report.get("per_repo_topk") or []
    if pr:
        lines.append("")
        lines.append("Per-repo top |Spearman rho| (FDR-flagged with *):")
        for row in pr:
            star = "*" if row.get("q_significant") else " "
            lines.append(
                f"  {star} {row.get('repo'):<48} {row.get('metric'):<6}"
                f" rho={_fmtf(row.get('rho'), '+.3f')}"
                f"  n={int(row.get('n', 0))}"
                f"  total={_fmtf(row.get('total_commits'), '.0f')}"
            )
    mu = report.get("multi_user_topk") or []
    if mu:
        lines.append("")
        lines.append("Multi-user top |Spearman rho| (FDR-flagged with *):")
        for row in mu:
            star = "*" if row.get("q_significant") else " "
            lines.append(
                f"  {star} {row.get('user'):<24} {row.get('metric'):<6}"
                f" rho={_fmtf(row.get('rho'), '+.3f')}"
                f"  n={int(row.get('n', 0))}"
                f"  total={_fmtf(row.get('total_commits'), '.0f')}"
            )
    return "\n".join(lines) + "\n"


def _commits_daily_summary(commits: pd.Series) -> dict[str, Any]:
    """
    Daily-grain summary of the commits series.

    Returns counts (total/active days, fraction), central tendency
    (mean per day, mean per active day, median, p95, max + date), spread
    (std), longest active and quiet streaks (in days), DOW means
    (Mon..Sun), weekday vs weekend means, and the first/last commit dates
    observed in the window.
    """
    s = commits.sort_index().astype(float).fillna(0.0)
    total_days = int(len(s))
    active_mask = s > 0
    days_with_commits = int(active_mask.sum())
    mean_per_day = float(s.mean()) if total_days else float("nan")
    median_per_day = float(s.median()) if total_days else float("nan")
    std_per_day = float(s.std(ddof=1)) if total_days > 1 else float("nan")
    p95_per_day = float(s.quantile(0.95)) if total_days else float("nan")
    if days_with_commits:
        mean_per_active_day = float(s[active_mask].mean())
        max_idx = s.idxmax()
        max_day = float(s.loc[max_idx])
        max_day_date = pd.Timestamp(max_idx).date().isoformat()
        first_active = pd.Timestamp(active_mask[active_mask].index[0]).date().isoformat()
        last_active = pd.Timestamp(active_mask[active_mask].index[-1]).date().isoformat()
    else:
        mean_per_active_day = float("nan")
        max_day = float("nan")
        max_day_date = None
        first_active = None
        last_active = None

    longest_active = 0
    longest_quiet = 0
    cur_a = 0
    cur_q = 0
    for v in active_mask.to_numpy():
        if v:
            cur_a += 1
            longest_active = max(longest_active, cur_a)
            cur_q = 0
        else:
            cur_q += 1
            longest_quiet = max(longest_quiet, cur_q)
            cur_a = 0

    dow = pd.to_datetime(s.index).dayofweek
    dow_means = [
        (float(s[dow == k].mean()) if int((dow == k).sum()) else float("nan"))
        for k in range(7)
    ]
    weekday_mask = dow < 5
    weekend_mask = dow >= 5
    weekday_total = float(s[weekday_mask].sum())
    weekend_total = float(s[weekend_mask].sum())
    grand = weekday_total + weekend_total
    return {
        "total_days": total_days,
        "days_with_commits": days_with_commits,
        "active_days_fraction": (
            days_with_commits / total_days if total_days else float("nan")
        ),
        "first_commit_date": first_active,
        "last_commit_date": last_active,
        "mean_per_day": mean_per_day,
        "median_per_day": median_per_day,
        "std_per_day": std_per_day,
        "p95_per_day": p95_per_day,
        "max_day": max_day,
        "max_day_date": max_day_date,
        "mean_per_active_day": mean_per_active_day,
        "longest_active_streak_days": int(longest_active),
        "longest_quiet_streak_days": int(longest_quiet),
        "dow_means_mon_to_sun": dow_means,
        "weekday_total": weekday_total,
        "weekend_total": weekend_total,
        "weekday_share": (weekday_total / grand) if grand > 0 else float("nan"),
        "weekend_share": (weekend_total / grand) if grand > 0 else float("nan"),
        "weekday_mean": float(s[weekday_mask].mean()) if int(weekday_mask.sum()) else float("nan"),
        "weekend_mean": float(s[weekend_mask].mean()) if int(weekend_mask.sum()) else float("nan"),
    }


def _spearman_p_array(lag: LagResult) -> np.ndarray:
    if lag.p_values is None:
        return np.array([], dtype=float)
    return np.array(
        [float(x) if x is not None else float("nan") for x in lag.p_values],
        dtype=float,
    )


def _json_float(value: float | int | None) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if np.isfinite(out) else None


def _lag_profile_rows(lag: LagResult, *, fdr_q: float = 0.1) -> list[dict[str, Any]]:
    ps = _spearman_p_array(lag)
    if ps.size and np.isfinite(ps).any():
        fdr = fdr_on_pvalues(ps, q=fdr_q)
    else:
        fdr = np.zeros(len(lag.lags), dtype=bool)
    rows: list[dict[str, Any]] = []
    for i, lag_days in enumerate(lag.lags):
        p = None
        if lag.p_values is not None and i < len(lag.p_values):
            p = _json_float(lag.p_values[i])
        rows.append({
            "lag_days": int(lag_days),
            "rho": _json_float(lag.values[i] if i < len(lag.values) else None),
            "p": p,
            "fdr_significant": bool(fdr[i]) if i < len(fdr) else False,
        })
    return rows


def _ccf_profile_rows(ccf: CCFResult) -> list[dict[str, Any]]:
    band = float(ccf.bartlett_ci)
    rows: list[dict[str, Any]] = []
    for i, lag_days in enumerate(ccf.lags):
        value = _json_float(ccf.values[i] if i < len(ccf.values) else None)
        rows.append({
            "lag_days": int(lag_days),
            "ccf": value,
            "bartlett_ci95": band,
            "crosses_bartlett_ci95": bool(value is not None and abs(value) > band),
            "method": ccf.method,
            "n_eff": int(ccf.n),
        })
    return rows


def _spectral_band_power_rows(periodogram) -> list[dict[str, Any]]:  # noqa: ANN001
    rows: list[dict[str, Any]] = []
    for name, (lo, hi) in SPECTRAL_BANDS_DAYS.items():
        rows.append({
            "band": name,
            "min_period_days": lo,
            "max_period_days": hi,
            "power_fraction": _json_float(
                band_power(periodogram, min_period_days=lo, max_period_days=hi),
            ),
        })
    return rows


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

    t0 = time.perf_counter()
    _LOG.info("phase: fetch GitHub public commit timeseries")
    commits_map = public_commit_time_series(
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
            cm2 = public_commit_time_series(
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
