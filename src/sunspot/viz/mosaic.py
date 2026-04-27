"""Hierarchical graphical abstract: pack PNGs under ``visualizations/`` into one figure.

The mosaic is organised top-to-bottom into clearly labelled sections so a
reader can follow the chain commits → solar context → per-metric
juxtaposition → per-repo / multi-user breakdown without zooming in.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.gridspec import GridSpec  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from sunspot.viz.style import get_style  # noqa: E402

_LOG = logging.getLogger(__name__)

# Per-metric tiles drawn left → right per metric row, ordered for juxtaposition:
# timeline → distribution → response → causality → spectra.
PER_METRIC_TILES: tuple[str, ...] = (
    "dual_axis",
    "scatter",
    "joint_density",
    "regression",
    "rolling_corr",
    "ma_corr_curve",
    "quantile_response",
    "distribution",
    "lag",
    "lag_heatmap",
    "mi_lag",
    "ccf",
    "monthly",
    "acf_pacf",
    "periodogram",
)


def _imshow_or_blank(
    ax: plt.Axes,
    path: Path | None,
    label: str | None = None,
    *,
    fontsize: float = 11.0,
) -> bool:
    """Show ``path`` in ``ax`` preserving pixel aspect (no distortion).

    Source plot pixels keep their natural aspect; cells with mismatched
    proportions get neutral whitespace padding rather than stretched content.
    """
    ax.set_axis_off()
    if path is None or not path.is_file() or path.stat().st_size == 0:
        if label:
            ax.text(
                0.5, 0.5, f"missing\n{label}",
                ha="center", va="center", fontsize=fontsize, color="0.4",
            )
        return False
    try:
        img = mpimg.imread(str(path))
    except (OSError, ValueError) as e:
        _LOG.debug("mosaic read failed %s: %s", path, e)
        if label:
            ax.text(
                0.5, 0.5, f"unreadable\n{label}",
                ha="center", va="center", fontsize=fontsize, color="0.4",
            )
        return False
    # aspect="equal" preserves the source pixel ratio (no stretching).
    ax.imshow(img, aspect="equal", interpolation="lanczos")
    if label:
        ax.set_title(label, fontsize=fontsize, pad=3, fontweight="semibold")
    return True


def _section_header(fig, gs_row, *, title: str, subtitle: str = "") -> None:
    ax = fig.add_subplot(gs_row)
    ax.set_axis_off()
    ax.add_patch(
        Rectangle(
            (0.0, 0.0), 1.0, 1.0, transform=ax.transAxes,
            color="#EEF1F5", linewidth=0,
        ),
    )
    ax.text(
        0.006, 0.58, title,
        transform=ax.transAxes, fontsize=20, fontweight="bold",
        color="#0F1A2A", va="center",
    )
    if subtitle:
        ax.text(
            0.006, 0.20, subtitle,
            transform=ax.transAxes, fontsize=14, color="#445163",
            va="center", style="italic",
        )


def _read_report_summary(out_root: Path) -> tuple[str, str]:
    """Return (title_line, subtitle_line) from statistics/report.json."""
    fp = out_root / "statistics" / "report.json"
    if not fp.is_file():
        return ("sunspot — graphical abstract", "")
    try:
        rep = json.loads(fp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ("sunspot — graphical abstract", "")
    user = rep.get("user", "?")
    since = rep.get("since", "")
    until = rep.get("until", "")
    n_total = rep.get("commits_total")
    metrics = list((rep.get("metrics") or {}).keys())
    extra = rep.get("compare_user_logins") or []
    title = f"sunspot — {user}"
    if extra:
        title += "  vs  " + ", ".join(extra)
    bits = []
    if since and until:
        bits.append(f"{since} → {until}")
    if metrics:
        bits.append("metrics: " + ", ".join(metrics))
    if n_total is not None:
        try:
            bits.append(f"Σ commits = {int(float(n_total))}")
        except (TypeError, ValueError):
            pass
    # Top-3 |ρ| metrics across the run.
    rows = []
    for m, blk in (rep.get("metrics") or {}).items():
        if not isinstance(blk, dict):
            continue
        sp = (blk.get("spearman_ci95") or {}).get("rho")
        if sp is None:
            continue
        try:
            rows.append((abs(float(sp)), float(sp), m))
        except (TypeError, ValueError):
            continue
    rows.sort(reverse=True)
    if rows:
        top = "   ".join(f"ρ({m})={v:+.2f}" for _, v, m in rows[:3])
        bits.append("top |ρ|: " + top)
    return (title, "    ·    ".join(bits))


def _stars_for(p: float | None) -> str:
    """APA-style significance stars (kept local to avoid a viz.plots import cycle)."""
    if p is None:
        return ""
    try:
        f = float(p)
    except (TypeError, ValueError):
        return ""
    if f != f:  # NaN
        return ""
    if f < 0.001:
        return "***"
    if f < 0.01:
        return "**"
    if f < 0.05:
        return "*"
    if f < 0.10:
        return "·"
    return ""


def _exec_summary_payload(report: dict) -> dict:
    """Distill ``report.json`` into the per-metric numbers shown on the card."""
    cs = report.get("commits_summary") or {}
    metrics: list[dict] = []
    for m, blk in (report.get("metrics") or {}).items():
        if not isinstance(blk, dict) or "error" in blk:
            continue
        pe = (blk.get("pearson_ci95") or {})
        sp = (blk.get("spearman_ci95") or {})
        lag = (blk.get("lag") or {})
        ccf = (blk.get("ccf") or {})
        ma = blk.get("ma_correlations") or []
        ma_peak = None
        if ma:
            try:
                ma_peak = max(
                    ma,
                    key=lambda r: abs(
                        float(r.get("pearson_r")) if r.get("pearson_r") is not None else 0.0,
                    ),
                )
            except (TypeError, ValueError):
                ma_peak = None
        pc = (blk.get("partial_correlation_ar1") or {}).get("pearson") or {}
        mi = blk.get("mutual_information") or {}
        ml = blk.get("mi_lag") or {}
        reg = blk.get("regression_ols") or {}
        metrics.append({
            "metric": m,
            "n": blk.get("n_aligned"),
            "pearson_r": pe.get("r"),
            "pearson_p": pe.get("p"),
            "spearman_rho": sp.get("rho"),
            "spearman_p": sp.get("p"),
            "best_lag_d": lag.get("best_lag"),
            "best_lag_rho": lag.get("best"),
            "ccf_peak_value": ccf.get("peak_value"),
            "ccf_peak_lag": ccf.get("peak_lag"),
            "ma_peak_window": (ma_peak or {}).get("window") if ma_peak else None,
            "ma_peak_r": (ma_peak or {}).get("pearson_r") if ma_peak else None,
            "ma_peak_p": (ma_peak or {}).get("pearson_p") if ma_peak else None,
            "partial_pearson_r": pc.get("r"),
            "partial_pearson_p": pc.get("p"),
            "mi_binned_nats": mi.get("binned_nats"),
            "mi_normalised": mi.get("binned_normalised"),
            "mi_peak_lag_d": ml.get("best_lag"),
            "mi_peak_nats": ml.get("best_value_nats"),
            "regression_r2": reg.get("r2"),
            "regression_dw": reg.get("durbin_watson"),
            "dominant_period_days": blk.get("dominant_period_days"),
        })
    return {
        "user": report.get("user"),
        "since": report.get("since"),
        "until": report.get("until"),
        "compare_user_logins": report.get("compare_user_logins") or [],
        "commits_total": report.get("commits_total"),
        "commits_summary": cs,
        "metrics": metrics,
    }


def _draw_exec_summary(ax, payload: dict, *, font_scale: float = 1.0) -> None:
    """
    Render the executive-summary card on a single bare axis.

    ``font_scale`` multiplies all text sizes — use ~2.5 when embedding into the
    very wide mosaic canvas, 1.0 for the standalone PNG.
    """
    ax.set_axis_off()
    ax.add_patch(
        Rectangle(
            (0.0, 0.0), 1.0, 1.0, transform=ax.transAxes,
            color="#F4F7FB", linewidth=0,
        ),
    )

    def _fs(s: float) -> float:
        return max(6.0, s * font_scale)

    cs = payload.get("commits_summary") or {}
    user = payload.get("user", "?")
    since = payload.get("since", "?")
    until = payload.get("until", "?")
    extra = payload.get("compare_user_logins") or []
    user_label = user
    if extra:
        user_label += "  vs  " + ", ".join(extra)
    ax.text(
        0.005, 0.92,
        f"Executive summary  ·  {user_label}  ·  {since} → {until}",
        transform=ax.transAxes, fontsize=_fs(15), fontweight="bold",
        color="#0F1A2A", va="center",
    )
    total = payload.get("commits_total")
    try:
        total_s = f"{int(float(total)):,}" if total is not None else "n/a"
    except (TypeError, ValueError):
        total_s = "n/a"
    active = cs.get("days_with_commits")
    total_d = cs.get("total_days")
    frac = cs.get("active_days_fraction")
    streak_a = cs.get("longest_active_streak_days")
    streak_q = cs.get("longest_quiet_streak_days")
    week_share = cs.get("weekday_share")
    wend_share = cs.get("weekend_share")
    max_day = cs.get("max_day")
    max_date = cs.get("max_day_date")
    activity = (
        f"Σ commits = {total_s}    "
        f"active days = {active}/{total_d} "
        f"({(frac or 0.0) * 100:.1f} %)    "
        f"streaks: active = {streak_a or 0}d  quiet = {streak_q or 0}d    "
        f"weekday/weekend = {(week_share or 0.0) * 100:.0f}/{(wend_share or 0.0) * 100:.0f} %    "
        f"max = {int(max_day) if max_day == max_day else 0} on {max_date or 'n/a'}"
    )
    ax.text(
        0.005, 0.78, activity,
        transform=ax.transAxes, fontsize=_fs(11), color="#0F1A2A", va="center",
    )

    headers = (
        "metric", "n", "Pearson r [p]", "Spearman ρ [p]",
        "best lag", "MA peak |r|", "partial r (AR1)", "MI [nats] / lag", "R²·DW",
    )
    metrics = payload.get("metrics") or []
    if not metrics:
        ax.text(
            0.5, 0.40, "no per-metric results",
            transform=ax.transAxes, fontsize=_fs(12), color="#445163",
            ha="center", va="center", style="italic",
        )
        return
    n_rows = len(metrics) + 1  # +1 header
    col_x = [0.005, 0.060, 0.135, 0.260, 0.380, 0.475, 0.605, 0.730, 0.910]
    top_y = 0.66
    bottom_y = 0.03
    row_h = (top_y - bottom_y) / n_rows
    for x, h in zip(col_x, headers, strict=True):
        ax.text(
            x, top_y - row_h * 0.5, h,
            transform=ax.transAxes, fontsize=_fs(11), fontweight="bold",
            color="#0F1A2A", va="center",
        )
    ax.add_patch(Rectangle(
        (0.0, top_y - row_h - 0.005), 1.0, 0.003,
        transform=ax.transAxes, color="#9DB1CC", linewidth=0,
    ))

    def _f(v: float | None, fmt: str = "+.3f") -> str:
        if v is None:
            return "—"
        try:
            f = float(v)
        except (TypeError, ValueError):
            return "—"
        if f != f:
            return "—"
        return format(f, fmt)

    for i, mrow in enumerate(metrics, start=1):
        y = top_y - row_h * (i + 0.5)
        cells = [
            mrow.get("metric") or "?",
            (str(int(mrow["n"])) if mrow.get("n") not in (None, "") else "—"),
            f"{_f(mrow.get('pearson_r'))} {_stars_for(mrow.get('pearson_p'))}".strip(),
            f"{_f(mrow.get('spearman_rho'))} {_stars_for(mrow.get('spearman_p'))}".strip(),
            (
                f"{mrow.get('best_lag_d')}d  "
                f"ρ={_f(mrow.get('best_lag_rho'), '+.2f')}"
                if mrow.get('best_lag_d') is not None else "—"
            ),
            (
                f"{_f(mrow.get('ma_peak_r'), '+.2f')} @ MA{int(mrow.get('ma_peak_window'))}d "
                f"{_stars_for(mrow.get('ma_peak_p'))}"
                if mrow.get('ma_peak_window') is not None else "—"
            ),
            (
                f"{_f(mrow.get('partial_pearson_r'))} "
                f"{_stars_for(mrow.get('partial_pearson_p'))}"
            ).strip(),
            (
                (
                    f"{_f(mrow.get('mi_peak_nats'), '.2f')}"
                    + (
                        f" @ {mrow.get('mi_peak_lag_d')}d"
                        if mrow.get('mi_peak_lag_d') is not None else ""
                    )
                )
                if mrow.get('mi_peak_nats') is not None else "—"
            ),
            (
                f"{_f(mrow.get('regression_r2'), '+.2f')} · {_f(mrow.get('regression_dw'), '.2f')}"
                if mrow.get('regression_r2') is not None else "—"
            ),
        ]
        for x, c in zip(col_x, cells, strict=True):
            ax.text(
                x, y, c,
                transform=ax.transAxes, fontsize=_fs(11),
                color="#0F1A2A", va="center",
            )

    ax.text(
        0.995, 0.06,
        "*** p<.001  **  p<.01  *  p<.05  ·  p<.10",
        transform=ax.transAxes, fontsize=_fs(9), color="#445163",
        ha="right", va="center", style="italic",
    )


def save_executive_summary(out_root: Path, *, out: Path) -> Path:
    """
    Render a standalone executive-summary card derived from
    ``statistics/report.json``. Same payload that is embedded as the
    mosaic's executive-summary row, useful as a single-image abstract.
    """
    out_root = Path(out_root)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fp = out_root / "statistics" / "report.json"
    if not fp.is_file():
        raise FileNotFoundError(fp)
    rep = json.loads(fp.read_text(encoding="utf-8"))
    payload = _exec_summary_payload(rep)
    n_rows = max(2, len(payload.get("metrics") or [])) + 2
    fig = plt.figure(figsize=(15.0, 0.55 * n_rows + 1.6))
    ax = fig.add_subplot(1, 1, 1)
    _draw_exec_summary(ax, payload)
    fig.savefig(out, dpi=get_style().dpi, bbox_inches="tight", facecolor="#F4F7FB")
    plt.close(fig)
    return out


def assemble_mosaic(
    out_root: Path,
    *,
    metrics: list[str] | None = None,
    mosaic_name: str = "mosaic.png",
    write_svg: bool = True,
) -> Path:
    """
    Build ``visualizations/mosaic.png`` from PNGs under ``visualizations/``.

    Layout (top → bottom):

    1. **Banner** — title / period / Σ commits / top |ρ| (read from report.json).
    2. **Solar context** — full-width ``dynamics/commits_and_solar.png``.
    3. **Cross-metric overview** — correlation matrix, lag grid, z-overview,
       stacked panel, seasonal calendar, ACF/PACF, periodogram (split row).
    4. **Per-metric juxtaposition** — for each metric, a row of paired tiles
       (time / distribution / response / causality / spectra).
    5. **Per-repo** — Spearman heatmap + top repos.
    6. **Multi-user** — overview / heatmaps / cumulative / phase, when
       ``--compare-users`` was set.

    Returns the mosaic PNG path. Also writes ``mosaic_index.json`` listing
    the source files referenced (so reviewers can find each tile on disk).
    """
    out_root = Path(out_root)
    vis = out_root / "visualizations"
    vis.mkdir(parents=True, exist_ok=True)
    skip = {"dynamics", "overview", "per_repo", "multi_user"}
    if metrics is None:
        metrics = sorted(d.name for d in vis.iterdir() if d.is_dir() and d.name not in skip)
    n_metrics = len(metrics)
    n_cols = max(6, len(PER_METRIC_TILES))

    has_mu = (vis / "multi_user").is_dir() and any((vis / "multi_user").iterdir())

    # Row layout (each entry is height_ratio):
    # banner, dyn_section_hdr, dynamics, overview_hdr, overview1, overview2,
    # per_metric_hdr, *per_metric_rows, per_repo_hdr, per_repo, [multi_user_hdr, multi_user]
    # Each height_ratio is in row units; figure height scales linearly with the
    # sum. Per-metric tile rows are roughly square at the chosen column width;
    # wide overview / per-repo rows get more height to match the natural aspect
    # of their source plots and avoid awkward whitespace bands.
    sections: list[tuple[str, float]] = []
    sections.append(("banner", 0.65))
    sections.append(("exec_summary", 2.40))
    sections.append(("hdr_solar", 0.36))
    sections.append(("solar", 1.45))
    sections.append(("hdr_overview", 0.36))
    sections.append(("overview1", 1.55))
    sections.append(("overview2", 1.55))
    sections.append(("hdr_per_metric", 0.36))
    for _ in range(max(1, n_metrics)):
        sections.append(("metric_row", 1.20))
    sections.append(("hdr_per_repo", 0.36))
    sections.append(("per_repo", 2.30))
    if has_mu:
        sections.append(("hdr_multi_user", 0.36))
        sections.append(("multi_user", 2.30))

    height_ratios = [r for _, r in sections]
    rows = len(sections)
    # Larger per-cell footprint + higher DPI → readable axis text per tile.
    cell_w = 4.2
    fig = plt.figure(figsize=(cell_w * n_cols, sum(height_ratios) * 2.0))
    gs = GridSpec(rows, n_cols, figure=fig, height_ratios=height_ratios,
                  hspace=0.18, wspace=0.06)

    sources: dict[str, list[str]] = {
        "header": [], "overview": [], "per_metric": [], "per_repo": [], "multi_user": [],
    }

    row_iter = iter(range(rows))
    # 1) Banner.
    title, subtitle = _read_report_summary(out_root)
    banner_row = next(row_iter)
    ax_banner = fig.add_subplot(gs[banner_row, :])
    ax_banner.set_axis_off()
    ax_banner.add_patch(
        Rectangle(
            (0.0, 0.0), 1.0, 1.0, transform=ax_banner.transAxes,
            color="#0B5FA5", linewidth=0,
        ),
    )
    ax_banner.text(
        0.006, 0.64, title,
        transform=ax_banner.transAxes, fontsize=26, fontweight="bold",
        color="white", va="center",
    )
    ax_banner.text(
        0.006, 0.22, subtitle,
        transform=ax_banner.transAxes, fontsize=14, color="#E8F0FA",
        va="center", style="italic",
    )
    ax_banner.text(
        0.994, 0.18,
        "*** p<.001  **  p<.01  *  p<.05  ·  p<.10  ⁿˢ otherwise",
        transform=ax_banner.transAxes, fontsize=11, color="#E8F0FA",
        va="center", ha="right", style="italic",
    )

    # 1a) Executive summary card — the "headline numbers" the reader should
    # see before zooming into individual tiles. Drawn inline so the typography
    # scales with the (very wide) mosaic canvas instead of being baked into
    # a fixed-aspect PNG.
    exec_row = next(row_iter)
    ax_exec = fig.add_subplot(gs[exec_row, :])
    fp = out_root / "statistics" / "report.json"
    if fp.is_file():
        try:
            rep_for_card = json.loads(fp.read_text(encoding="utf-8"))
            _draw_exec_summary(
                ax_exec, _exec_summary_payload(rep_for_card), font_scale=2.0,
            )
        except (OSError, ValueError) as e:
            _LOG.debug("exec summary skipped: %s", e)
            ax_exec.set_axis_off()
    else:
        ax_exec.set_axis_off()

    # 2) Solar context section.
    _section_header(
        fig, gs[next(row_iter), :],
        title="Solar context",
        subtitle="daily commits with 7d / 30d MA, z(SSN) and z(F10.7)",
    )
    solar_row = next(row_iter)
    header = vis / "dynamics" / "commits_and_solar.png"
    ax_h = fig.add_subplot(gs[solar_row, :])
    if _imshow_or_blank(ax_h, header, "dynamics/commits_and_solar"):
        sources["header"].append(str(header.relative_to(out_root)))

    # 3) Cross-metric overview (two rows).
    _section_header(
        fig, gs[next(row_iter), :],
        title="Cross-metric overview",
        subtitle="how all metrics + commits relate, on shared axes",
    )
    ov = vis / "overview"
    overview_row1 = [
        ("overview/metric_correlation_matrix", ov / "metric_correlation_matrix.png"),
        ("overview/stacked_panel",             ov / "stacked_panel.png"),
        ("overview/seasonal_calendar",         ov / "seasonal_calendar.png"),
        ("overview/dow_response",              ov / "dow_response.png"),
    ]
    overview_row2 = [
        ("overview/metrics_zscored_overview",  ov / "metrics_zscored_overview.png"),
        ("overview/lag_grid",                  ov / "lag_grid.png"),
        ("overview/commits_acf_pacf",          ov / "commits_acf_pacf.png"),
        ("overview/commits_periodogram",       ov / "commits_periodogram.png"),
    ]
    for row, files in (
        (next(row_iter), overview_row1),
        (next(row_iter), overview_row2),
    ):
        for col, (lbl, p) in enumerate(files):
            span = max(1, n_cols // len(files))
            c0 = col * span
            c1 = c0 + span if col < len(files) - 1 else n_cols
            ax = fig.add_subplot(gs[row, c0:c1])
            if _imshow_or_blank(ax, p, lbl):
                sources["overview"].append(str(p.relative_to(out_root)))

    # 4) Per-metric juxtaposition.
    _section_header(
        fig, gs[next(row_iter), :],
        title="Per-metric juxtaposition",
        subtitle=(
            "left → right per metric: timeline · scatter / joint density · "
            "regression / rolling-r · quantile response / distribution · lag · "
            "CCF / monthly · ACF/PACF · periodogram"
        ),
    )
    for r_idx, m in enumerate(metrics):
        row = next(row_iter)
        for c, name in enumerate(PER_METRIC_TILES[:n_cols]):
            ax = fig.add_subplot(gs[row, c])
            p = vis / m / f"{name}.png"
            label = f"{m}/{name}" if r_idx == 0 else name
            if _imshow_or_blank(ax, p, label):
                sources["per_metric"].append(str(p.relative_to(out_root)))
            if c == 0:
                ax.text(
                    -0.10, 0.5, m.upper(),
                    transform=ax.transAxes, fontsize=18, fontweight="bold",
                    color="#0F1A2A", ha="right", va="center", rotation=90,
                )

    if not metrics:
        # leave one blank row so the grid is well-formed
        next(row_iter)

    # 5) Per-repo.
    _section_header(
        fig, gs[next(row_iter), :],
        title="Per-repo breakdown",
        subtitle="repo × metric Spearman (FDR-flagged) and top repos with z(SSN)",
    )
    repo_row = next(row_iter)
    pr = vis / "per_repo"
    repo_files = [
        ("per_repo/repo_metric_spearman_heatmap", pr / "repo_metric_spearman_heatmap.png"),
        ("per_repo/top_repos_30d_ma",             pr / "top_repos_30d_ma.png"),
    ]
    for col, (lbl, p) in enumerate(repo_files):
        span = max(1, n_cols // len(repo_files))
        c0 = col * span
        c1 = c0 + span if col < len(repo_files) - 1 else n_cols
        ax = fig.add_subplot(gs[repo_row, c0:c1])
        if _imshow_or_blank(ax, p, lbl):
            sources["per_repo"].append(str(p.relative_to(out_root)))

    # 6) Multi-user.
    if has_mu:
        _section_header(
            fig, gs[next(row_iter), :],
            title="Multi-user comparison",
            subtitle="per-user activity and pairwise structure",
        )
        mu_row = next(row_iter)
        mu = vis / "multi_user"
        mu_files = [
            ("multi_user/overview_30d_ma",       mu / "overview_30d_ma.png"),
            ("multi_user/user_metric_heatmap",   mu / "user_metric_spearman_heatmap.png"),
            ("multi_user/user_user_rank_matrix", mu / "user_user_rank_matrix.png"),
            ("multi_user/cumulative_vs_solar",   mu / "cumulative_vs_solar.png"),
            ("multi_user/phase_by_ssn_quantile", mu / "phase_by_ssn_quantile.png"),
        ]
        for col, (lbl, p) in enumerate(mu_files):
            span = max(1, n_cols // len(mu_files))
            c0 = col * span
            c1 = c0 + span if col < len(mu_files) - 1 else n_cols
            ax = fig.add_subplot(gs[mu_row, c0:c1])
            if _imshow_or_blank(ax, p, lbl):
                sources["multi_user"].append(str(p.relative_to(out_root)))

    out_png = vis / mosaic_name
    fig.savefig(out_png, dpi=get_style().dpi, bbox_inches="tight", facecolor="white")
    if write_svg:
        try:
            fig.savefig(out_png.with_suffix(".svg"), bbox_inches="tight", facecolor="white")
        except (OSError, ValueError) as e:
            _LOG.debug("mosaic svg write failed: %s", e)
    plt.close(fig)
    index = vis / "mosaic_index.json"
    payload = {"mosaic": str(out_png.relative_to(out_root)), **sources}
    index.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _LOG.info("wrote %s and %s (sections=%s, cols=%s)", out_png, index, rows, n_cols)
    return out_png


def _cohort_exec_payload(report: dict) -> dict[str, object]:
    return {
        "since": report.get("since"),
        "until": report.get("until"),
        "users": report.get("cohort_users") or [],
        "commits_by_user": report.get("commits_by_user") or {},
        "user_activity": report.get("user_activity") or {},
        "commits_total": report.get("commits_total"),
        "cs": report.get("commits_summary") or {},
        "topk": (report.get("multi_user_topk") or [])[:8],
        "pca": report.get("cohort_pca") or {},
    }


def _draw_cohort_exec(ax, payload: dict, *, font_scale: float = 1.0) -> None:
    ax.set_axis_off()
    ax.add_patch(
        Rectangle(
            (0.0, 0.0), 1.0, 1.0, transform=ax.transAxes,
            color="#F4F7FB", linewidth=0,
        ),
    )

    def _fs(x: float) -> float:
        return max(6.0, x * font_scale)

    ulist = list(payload.get("users") or [])
    s0, s1 = payload.get("since", "?"), payload.get("until", "?")
    ax.text(
        0.005, 0.92,
        f"Cohort summary  ·  {s0} → {s1}  ·  {len(ulist)} logins",
        transform=ax.transAxes, fontsize=_fs(15), fontweight="bold",
        color="#0F1A2A", va="center",
    )
    byu = payload.get("commits_by_user") or {}
    act = payload.get("user_activity") or {}
    y = 0.80
    ax.text(0.005, y, "User · Σ commits · active days", transform=ax.transAxes,
            fontsize=_fs(11), fontweight="bold", color="#0F1A2A")
    y -= 0.055
    for u in ulist[:16]:
        tot = byu.get(u, 0.0)
        ad = act.get(u, 0)
        ax.text(
            0.01, y, f"  {u:24s}  {int(float(tot)):>6d}  {int(ad):>5d}",
            transform=ax.transAxes, fontsize=_fs(10), color="#0F1A2A", va="center",
        )
        y -= 0.040
    if len(ulist) > 16:
        ax.text(0.01, y, f"  … +{len(ulist) - 16} more", transform=ax.transAxes,
                fontsize=_fs(9), color="#445163", va="center")
    y = max(0.10, y - 0.06)
    topk = payload.get("topk") or []
    if topk:
        ax.text(0.005, y, "Top |ρ| (user × metric, Spearman, BH-FDR)", transform=ax.transAxes,
                fontsize=_fs(11), fontweight="bold", color="#0F1A2A", va="center")
        y -= 0.05
        for row in topk[:6]:
            st = "*" if row.get("q_significant") else " "
            pv = row.get("p")
            try:
                p_str = f"{float(pv):.1e}" if pv is not None and pv == pv else "—"
            except (TypeError, ValueError):
                p_str = "—"
            ax.text(
                0.01, y,
                f"  {st} {str(row.get('user')):16s}  {str(row.get('metric')):6s}  "
                f"ρ={row.get('rho')!s}  p={p_str}",
                transform=ax.transAxes, fontsize=_fs(9), color="#0F1A2A", va="center",
            )
            y -= 0.034
    pca = payload.get("pca") or {}
    evr = pca.get("explained_variance_ratio") or []
    if evr:
        y = max(0.03, y - 0.04)
        ax.text(
            0.005, y,
            "PCA (weekly, z per user): "
            + "  ".join(f"PC{i+1}={100 * float(evr[i]):.1f}%"
                        for i in range(min(2, len(evr)))),
            transform=ax.transAxes, fontsize=_fs(9), color="#445163", style="italic",
        )


def save_cohort_executive_summary(out_root: Path, *, out: Path) -> Path:
    """Standalone PNG: cohort user table + top multi-user |ρ| + PCA var."""
    out_root = Path(out_root)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fp = out_root / "statistics" / "report.json"
    if not fp.is_file():
        raise FileNotFoundError(fp)
    rep = json.loads(fp.read_text(encoding="utf-8"))
    if rep.get("report_kind") != "cohort":
        raise ValueError("report is not a cohort run (report_kind != 'cohort')")
    pl = _cohort_exec_payload(rep)
    n_rows = min(20, 6 + len(pl.get("users") or [])) + 4
    fig = plt.figure(figsize=(15.0, 0.45 * n_rows + 0.5))
    ax = fig.add_subplot(1, 1, 1)
    _draw_cohort_exec(ax, pl, font_scale=1.0)
    fig.savefig(out, dpi=get_style().dpi, bbox_inches="tight", facecolor="#F4F7FB")
    plt.close(fig)
    return out


def assemble_cohort_mosaic(
    out_root: Path,
    *,
    mosaic_name: str = "mosaic.png",
    write_svg: bool = True,
) -> Path:
    """
    Build a *compact* mosaic: banner, cohort executive, dynamics compare,
    cohort analytics (PCA / dendrogram / heatmap), then multi_user tiles.
    No per-metric or per-repo sections.
    """
    out_root = Path(out_root)
    vis = out_root / "visualizations"
    vis.mkdir(parents=True, exist_ok=True)
    fp = out_root / "statistics" / "report.json"
    title = "sunspot — cohort"
    if fp.is_file():
        try:
            r = json.loads(fp.read_text(encoding="utf-8"))
            u = r.get("cohort_users") or []
            since, until = r.get("since", ""), r.get("until", "")
            title = f"sunspot cohort — {len(u)} logins  ·  {since} → {until}"
        except (OSError, ValueError):
            pass
    n_cols = 4
    sections: list[tuple[str, float]] = [
        ("banner", 0.5),
        ("exec", 2.0),
        ("hdr_dyn", 0.32),
        ("dyn", 0.9),
        ("hdr_cohort", 0.32),
        ("cohort_row", 1.1),
        ("hdr_mu", 0.32),
        ("mu", 1.2),
    ]
    hrat = [r for _, r in sections]
    rows = len(sections)
    fig = plt.figure(figsize=(n_cols * 4.0, sum(hrat) * 1.4))
    gs = GridSpec(rows, n_cols, figure=fig, height_ratios=hrat, hspace=0.16, wspace=0.06)
    it = iter(range(rows))
    r0 = next(it)
    axb = fig.add_subplot(gs[r0, :])
    axb.set_axis_off()
    axb.add_patch(
        Rectangle(
            (0.0, 0.0), 1.0, 1.0, transform=axb.transAxes,
            color="#0B5FA5", linewidth=0,
        ),
    )
    axb.text(
        0.01, 0.55, title, transform=axb.transAxes, fontsize=20,
        fontweight="bold", color="white", va="center",
    )
    re = next(it)
    axe = fig.add_subplot(gs[re, :])
    if fp.is_file():
        try:
            rep = json.loads(fp.read_text(encoding="utf-8"))
            _draw_cohort_exec(axe, _cohort_exec_payload(rep), font_scale=1.45)
        except (OSError, ValueError):
            axe.set_axis_off()
    else:
        axe.set_axis_off()
    _section_header(
        fig, gs[next(it), :], title="Activity vs solar (30d MA · z-SSN)",
    )
    rd = next(it)
    p_dyn = vis / "dynamics" / "compare_users_30d_ma.png"
    axd = fig.add_subplot(gs[rd, :])
    if _imshow_or_blank(axd, p_dyn, "dynamics/compare_users_30d_ma"):
        pass
    _section_header(
        fig, gs[next(it), :],
        title="Cohort structure",
        subtitle="PCA · hierarchy · weekly z-heatmap (users as rows)",
    )
    rco = next(it)
    cohort_imgs: list[tuple[str, Path]] = [
        ("pca", vis / "cohort" / "user_pca_scatter.png"),
        ("dendro", vis / "cohort" / "user_dendrogram.png"),
        ("wheat", vis / "cohort" / "user_weekly_heatmap.png"),
        ("users", vis / "cohort" / "user_summary.png"),
    ]
    cspan = max(1, n_cols // len(cohort_imgs))
    for j, (lbl, p) in enumerate(cohort_imgs):
        c0 = j * cspan
        c1 = c0 + cspan if j < len(cohort_imgs) - 1 else n_cols
        axc = fig.add_subplot(gs[rco, c0:c1])
        if _imshow_or_blank(axc, p, f"cohort/{lbl}"):
            pass
    _section_header(
        fig, gs[next(it), :],
        title="Multi-user vs metrics",
    )
    rmu = next(it)
    mu = vis / "multi_user"
    mfiles: list[tuple[str, Path]] = [
        ("mu/overview", mu / "overview_30d_ma.png"),
        ("mu/heatmap", mu / "user_metric_spearman_heatmap.png"),
        ("mu/corr", mu / "user_user_rank_matrix.png"),
        ("mu/cum", mu / "cumulative_vs_solar.png"),
    ]
    c_each = n_cols // len(mfiles)
    for j, (lbl, p) in enumerate(mfiles):
        c0 = j * c_each
        c1 = c0 + c_each if j < len(mfiles) - 1 else n_cols
        axm = fig.add_subplot(gs[rmu, c0:c1])
        _imshow_or_blank(axm, p, lbl)
    out_png = vis / mosaic_name
    fig.savefig(out_png, dpi=get_style().dpi, bbox_inches="tight", facecolor="white")
    if write_svg:
        try:
            fig.savefig(out_png.with_suffix(".svg"), bbox_inches="tight", facecolor="white")
        except (OSError, ValueError) as e:
            _LOG.debug("cohort mosaic svg: %s", e)
    plt.close(fig)
    idxp = vis / "mosaic_index.json"
    idxp.write_text(
        json.dumps(
            {
                "mosaic": str(out_png.relative_to(out_root)),
                "cohort_mosaic": True,
                "sections": [t for t, _ in sections],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return out_png
