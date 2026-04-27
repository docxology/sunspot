"""
Cohort (multi-user-only) run: no single-anchor per-metric deep dive.

Fetches an aligned window for all logins, writes ``data/commits/`` (wide +
per-user + aggregate rollups), geophysical user×metric stats, among-user
visuals (plus PCA, clustering), and a compact mosaic. Use the ``cohort`` CLI
or call :func:`run_cohort_report` with at least two logins.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import pandas as pd

from sunspot import __version__
from sunspot.cohort_presets import expand_preset
from sunspot.correlate import (  # private helpers, shared pipeline pieces
    _commits_daily_summary,
    _format_summary,
    _series_for_metric,
    _write_commit_rollups,
    _write_methods,
    _write_per_user_commits,
)
from sunspot.github.commits import public_commit_time_series
from sunspot.stats.multi_user import (
    cohort_dendrogram_leaves,
    multi_user_associations,
    multi_user_rank_matrix,
    pca_users_weekly,
)
from sunspot.tables import write_analysis_tables
from sunspot.viz.cohort import (
    save_cohort_dendrogram,
    save_cohort_pca_scatter,
    save_cohort_timeseries_heatmap,
    save_cohort_user_summary,
)
from sunspot.viz.mosaic import assemble_cohort_mosaic, save_cohort_executive_summary
from sunspot.viz.multi_user import (
    save_multi_user_cumulative,
    save_multi_user_heatmap,
    save_multi_user_overview,
    save_multi_user_phase,
    save_multi_user_rank_matrix,
)
from sunspot.viz.plots import save_compare_users_moving_averages
from sunspot.viz.style import set_style

_LOG = logging.getLogger(__name__)

DIR_STATISTICS = "statistics"
DIR_DATA = "data"
DIR_VIS = "visualizations"
DIR_ANALYSIS = "analysis"


def _cohort_user_summary(umap: dict[str, pd.Series]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for login, series in umap.items():
        s = series.astype(float).fillna(0.0)
        active_days = int((s > 0).sum())
        total_days = int(len(s))
        total = float(s.sum())
        rows.append({
            "login": login,
            "total_commits": total,
            "total_days": total_days,
            "active_days": active_days,
            "active_days_fraction": (active_days / total_days) if total_days else None,
            "mean_per_day": float(s.mean()) if total_days else None,
            "mean_per_active_day": (total / active_days) if active_days else None,
            "max_day": float(s.max()) if total_days else None,
            "max_day_date": (
                s.idxmax().date().isoformat()
                if total_days and float(s.max()) > 0.0 else None
            ),
        })
    return sorted(rows, key=lambda r: float(r["total_commits"]), reverse=True)


def default_cohort_dir(
    n_users: int, since, until, *, slug: str = "cohort",
) -> Path:
    """``output/correlate/{slug}_n{count}__{since}__{until}/``."""
    from datetime import date as date_cls

    if not isinstance(since, date_cls) or not isinstance(until, date_cls):
        raise TypeError("since and until must be date objects")
    return (
        Path("output")
        / "correlate"
        / f"{slug}_n{int(n_users)}__{since.isoformat()}__{until.isoformat()}"
    )


def run_cohort_report(
    logins: list[str],
    *,
    since,
    until,
    metrics: list[str],
    out_dir: Path,
    use_commit_cache: bool = True,
    make_mosaic: bool = True,
    style_overrides: dict[str, Any] | None = None,
    since_policy: str | None = None,
) -> dict[str, Any]:
    """
    Multi-user run only: writes ``data/commits/`` (``daily.csv`` = sum of users,
    ``by_user/``, wide matrix optional in report), ``analysis/``,
    ``statistics/report.json`` with ``report_kind`` = ``"cohort"``,
    ``visualizations/cohort/`` and ``visualizations/multi_user/`` (no
    ``{metric}/`` tiles, no per-repo).

    ``since_policy`` (from the CLI) is only recorded in the report for traceability:
    e.g. ``"union"`` = cohort window starts at the *earliest* first-commit date
    among logins; ``"intersection"`` = start at the *latest* (shortest common
    span).
    """
    from datetime import date as date_cls

    out_dir = Path(out_dir)
    raw = [x.strip() for x in logins if x and str(x).strip()]
    ulist = list(dict.fromkeys(raw))
    if len(ulist) < 2:
        raise ValueError("cohort needs at least two distinct logins")

    if style_overrides:
        applied = set_style(**style_overrides)
        _LOG.info(
            "viz style: font_scale=%.2f line_width=%.2f dpi=%d theme=%s",
            applied.font_scale, applied.line_width, applied.dpi, applied.theme,
        )

    idx = pd.date_range(pd.Timestamp(since), pd.Timestamp(until), freq="D")
    t0 = time.perf_counter()
    umap: dict[str, pd.Series] = {}
    for u in ulist:
        _LOG.info("cohort: fetching %s", u)
        cm = public_commit_time_series(
            u, since=since, until=until, use_commit_cache=use_commit_cache,
        )
        a = cm.get("__all__", pd.Series(dtype=float))
        s = a.reindex(idx).fillna(0.0)
        s.name = "commits"
        umap[u] = s
    t1 = time.perf_counter()
    _LOG.info("cohort: GitHub done in %.1fs (%s users)", t1 - t0, len(ulist))

    period = (since, until) if isinstance(since, date_cls) else (None, None)
    commits_sum = pd.concat(umap.values(), axis=1).fillna(0.0).sum(axis=1)
    commits_sum.name = "commits"

    stats_dir = out_dir / DIR_STATISTICS
    data_dir = out_dir / DIR_DATA
    vis_dir = out_dir / DIR_VIS
    analysis_dir = out_dir / DIR_ANALYSIS
    for d in (stats_dir, data_dir, vis_dir, analysis_dir):
        d.mkdir(parents=True, exist_ok=True)

    commits_dir = data_dir / "commits"
    commits_dir.mkdir(parents=True, exist_ok=True)
    commits_sum.to_csv(commits_dir / "daily.csv")
    # Wide matrix (one column per user) for external PCA / ML
    wide = pd.DataFrame(umap)
    wide.to_csv(commits_dir / "daily_users_wide.csv")
    (commits_dir / "cohort_logins.txt").write_text(
        "\n".join(ulist) + "\n", encoding="utf-8",
    )

    _write_per_user_commits(commits_dir, umap)
    user_summary = _cohort_user_summary(umap)
    user_summary_path = commits_dir / "user_summary.csv"
    pd.DataFrame(user_summary).to_csv(user_summary_path, index=False)
    csum = _commits_daily_summary(commits_sum)
    roll = _write_commit_rollups(commits_dir, commits_sum, csum)
    _LOG.info(
        "cohort: wrote commit rollups: %s; user summary: %s",
        ", ".join(p.name for p in roll),
        user_summary_path,
    )

    vis_dyn = vis_dir / "dynamics"
    vis_dyn.mkdir(parents=True, exist_ok=True)
    vis_cohort = vis_dir / "cohort"
    vis_cohort.mkdir(parents=True, exist_ok=True)
    mu_dir = vis_dir / "multi_user"
    mu_dir.mkdir(parents=True, exist_ok=True)

    try:
        ssn_z = _series_for_metric("ssn", since=since, until=until)
        save_compare_users_moving_averages(
            umap, ssn_z, out=vis_dyn / "compare_users_30d_ma.png",
            window=30, period=period,
        )
        _LOG.info("cohort: wrote %s", vis_dyn / "compare_users_30d_ma.png")
    except Exception as e:  # noqa: BLE001
        _LOG.warning("cohort: compare 30d MA failed: %s", e)

    metric_frames: dict[str, pd.Series] = {}
    for m in metrics:
        try:
            g = _series_for_metric(m, since=since, until=until)
            metric_frames[m] = g.reindex(idx)
        except Exception as e:  # noqa: BLE001
            _LOG.error("cohort: metric %s: %s", m, e)
    cm_frame = pd.DataFrame(metric_frames) if metric_frames else pd.DataFrame()

    zcu = [u for u in ulist if float(umap[u].sum()) < 1e-9]
    if zcu:
        _LOG.warning(
            "cohort: %d user(s) with no commits in [since, until]: %s",
            len(zcu),
            ", ".join(zcu),
        )
    report: dict[str, Any] = {
        "version": __version__,
        "report_kind": "cohort",
        "user": f"cohort({len(ulist)} users)",
        "cohort_users": ulist,
        "since": since.isoformat() if hasattr(since, "isoformat") else str(since),
        "until": until.isoformat() if hasattr(until, "isoformat") else str(until),
        **({"since_policy": str(since_policy)} if since_policy else {}),
        "compare_user_logins": [],
        "use_commit_cache": use_commit_cache,
        "requested_metrics": list(metrics),
        "commits_total": float(commits_sum.sum()),
        "commits_by_user": {u: float(umap[u].sum()) for u in ulist},
        "user_activity": {u: int((umap[u] > 0).sum()) for u in ulist},
        "cohort_user_summary": user_summary,
        "cohort_zero_commit_users": zcu,
        "commits_summary": csum,
        "metrics": {},
        "per_repo_repos": 0,
        "output_layout": {
            "root": str(out_dir),
            "statistics": str(stats_dir),
            "data": str(data_dir),
            "visualizations": str(vis_dir),
            "dynamics": str(vis_dyn),
            "analysis": str(analysis_dir),
        },
    }

    pca = pca_users_weekly(umap, n_components=2)
    if pca:
        report["cohort_pca"] = pca
        try:
            save_cohort_pca_scatter(
                pca, out=vis_cohort / "user_pca_scatter.png", period=period,
            )
        except Exception as e:  # noqa: BLE001
            _LOG.debug("cohort pca plot: %s", e)
    hro, cex = cohort_dendrogram_leaves(umap)
    if cex:
        report["cohort_clustering_excluded_users"] = cex
    if hro:
        report["cohort_dendrogram_leaves"] = hro
    try:
        save_cohort_dendrogram(umap, out=vis_cohort / "user_dendrogram.png", period=period)
    except Exception as e:  # noqa: BLE001
        _LOG.debug("cohort dendrogram: %s", e)
    try:
        save_cohort_timeseries_heatmap(
            umap, out=vis_cohort / "user_weekly_heatmap.png", period=period,
        )
    except Exception as e:  # noqa: BLE001
        _LOG.debug("cohort heatmap: %s", e)
    try:
        save_cohort_user_summary(
            user_summary, out=vis_cohort / "user_summary.png", period=period,
        )
    except Exception as e:  # noqa: BLE001
        _LOG.debug("cohort user summary plot: %s", e)

    if not cm_frame.empty:
        try:
            mu_long = multi_user_associations(umap, cm_frame, method="spearman")
            (analysis_dir / "multi_user_associations.csv").write_text(
                mu_long.to_csv(index=False), encoding="utf-8",
            )
            report["multi_user_topk"] = (
                mu_long.assign(absrho=mu_long["rho"].abs())
                .sort_values("absrho", ascending=False)
                .head(10)
                .drop(columns=["absrho"])
                .to_dict(orient="records")
            )
            save_multi_user_heatmap(
                mu_long, out=mu_dir / "user_metric_spearman_heatmap.png",
                metric_order=list(cm_frame.columns), period=period,
            )
        except Exception as e:  # noqa: BLE001
            _LOG.warning("cohort multi_user heatmap/assoc: %s", e)
    try:
        ssn_mu = _series_for_metric("ssn", since=since, until=until)
        save_multi_user_overview(
            umap, ssn_mu, out=mu_dir / "overview_30d_ma.png",
            window=30, period=period,
        )
        save_multi_user_rank_matrix(
            umap, out=mu_dir / "user_user_rank_matrix.png",
            smoothing_window=30, method="spearman", period=period,
        )
        save_multi_user_cumulative(
            umap, ssn_mu, out=mu_dir / "cumulative_vs_solar.png", period=period,
        )
        save_multi_user_phase(
            umap, ssn_mu, out=mu_dir / "phase_by_ssn_quantile.png", period=period,
        )
    except Exception as e:  # noqa: BLE001
        _LOG.debug("cohort multi_user overview: %s", e)

    # Pairwise user×user matrix in report
    rmat = multi_user_rank_matrix(umap, method="spearman", smoothing_window=30)
    if not rmat.empty:
        uu: dict[str, dict[str, float | None]] = {}
        for a in rmat.index:
            uu[str(a)] = {}
            for b in rmat.columns:
                v = rmat.loc[a, b]
                uu[str(a)][str(b)] = None if pd.isna(v) else float(v)
        report["user_user_spearman_smoothed_30d"] = uu

    (stats_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (analysis_dir / "summary.txt").write_text(
        "sunspot cohort run\n" + _format_summary(report) + "\n", encoding="utf-8",
    )
    _write_methods(out_dir, report)

    try:
        written_tables = write_analysis_tables(
            report, analysis_dir, lag_results=None, ccf_results=None,
        )
        _LOG.info(
            "cohort: wrote %s analysis tables under %s",
            len(written_tables),
            analysis_dir / "tables",
        )
    except (OSError, ValueError) as e:
        _LOG.warning("cohort analysis tables: %s", e)

    try:
        es = save_cohort_executive_summary(
            out_dir, out=vis_dir / "executive_summary.png",
        )
        report["executive_summary"] = str(es)
        (stats_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    except (OSError, ValueError, FileNotFoundError) as e:
        _LOG.warning("cohort executive summary: %s", e)

    if make_mosaic:
        try:
            mp = assemble_cohort_mosaic(out_dir)
            report["mosaic"] = str(mp)
            (stats_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        except (OSError, ValueError) as e:
            _LOG.warning("cohort mosaic: %s", e)

    t2 = time.perf_counter()
    n_png = sum(1 for _ in vis_dir.rglob("*.png")) if vis_dir.exists() else 0
    n_tables = sum(1 for _ in (analysis_dir / "tables").glob("*.csv"))
    _LOG.info(
        "cohort: done: statistics=%s | pngs=%s analysis_tables=%s | wall %.1fs",
        stats_dir / "report.json",
        n_png,
        n_tables,
        t2 - t0,
    )
    return report


__all__ = [
    "default_cohort_dir",
    "run_cohort_report",
    "expand_preset",
]
