"""
Cohort-level plots: PCA of users, weekly activity heatmap, and dendrogram.

Used when ``run_cohort_report`` is invoked (no single-user per-metric run).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.cluster.hierarchy import dendrogram  # noqa: E402

from sunspot.stats.multi_user import cohort_correlation_dendrogram_data  # noqa: E402
from sunspot.viz.style import (  # noqa: E402
    PlotStyle,
    apply_rcparams,
    get_style,
    metadata_footer,
    period_label,
)

Period = tuple[date | None, date | None] | None


def _push(style: PlotStyle | None) -> PlotStyle:
    s = style or get_style()
    apply_rcparams(s)
    return s


def _meta(period: Period, extras: list[str] | None) -> list[str]:
    pl = period_label(period[0] if period else None, period[1] if period else None)
    parts = [p for p in [pl, *(extras or [])] if p]
    return parts


def _save(fig: Any, out: Path, s: PlotStyle) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=s.dpi, bbox_inches="tight", facecolor=s.axis_bg)
    plt.close(fig)


def save_cohort_pca_scatter(
    pca: dict[str, object],
    *,
    out: Path,
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """User × user scatter on PC1 vs PC2 (from :func:`pca_users_weekly`)."""
    s = _push(style)
    sc = pca.get("pc_scores") or {}
    if not sc:
        return
    users = list(pca.get("user_order") or sc.keys())
    evr = pca.get("explained_variance_ratio") or [0.0, 0.0]
    e0 = evr[0] if len(evr) else 0.0
    e1 = evr[1] if len(evr) > 1 else 0.0
    fig, ax = plt.subplots(figsize=(7.0, 6.0))
    for i, u in enumerate(users):
        row = sc.get(u) or [0.0, 0.0]
        x, y = float(row[0]), float(row[1]) if len(row) > 1 else 0.0
        ax.scatter(x, y, color=s.palette[i % len(s.palette)], s=50, zorder=2)
        ax.annotate(
            u, (x, y), textcoords="offset points", xytext=(3, 3),
            fontsize=s.base_size * 0.8, color=s.axis_fg,
        )
    ax.axhline(0.0, color=s.grid_color, linewidth=0.5)
    ax.axvline(0.0, color=s.grid_color, linewidth=0.5)
    ax.set_xlabel(f"PC1  ({e0 * 100:.1f} % var)")
    ax.set_ylabel(f"PC2  ({e1 * 100:.1f} % var)")
    ax.set_title("Users in weekly-activity PC space (rows z-scored before SVD)")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(
        fig, parts=_meta(period, [f"users={len(users)}", f"weeks={pca.get('n_weeks')}"]),
        style=s,
    )
    _save(fig, Path(out), s)


def save_cohort_dendrogram(
    users_commits: dict[str, pd.Series],
    *,
    out: Path,
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """Average linkage, correlation distance on weekly sums."""
    s = _push(style)
    if len(users_commits) < 2:
        return
    data = cohort_correlation_dendrogram_data(users_commits)
    if not data or data.get("linkage") is None:
        return
    z = data["linkage"]
    assert isinstance(z, np.ndarray)
    labels = data["labels"]
    assert isinstance(labels, list)
    excluded = data.get("excluded", [])
    assert isinstance(excluded, list)
    extras = [f"n={len(labels)}"]
    if excluded:
        extras.append(f"excl={len(excluded)} (no week-to-week var.)")
    fig, ax = plt.subplots(figsize=(0.4 * len(labels) + 2, 3.2))
    dendrogram(z, ax=ax, labels=labels, leaf_rotation=45.0)
    ax.set_title("Users · hierarchical (average, correlation on weekly sums)")
    fig.tight_layout(rect=(0, 0.2, 1, 1))
    metadata_footer(fig, parts=_meta(period, extras), style=s)
    _save(fig, Path(out), s)


def save_cohort_timeseries_heatmap(
    users_commits: dict[str, pd.Series],
    *,
    out: Path,
    max_cols: int = 260,
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """
    Weekly sums, z-scored per user, downsampled to ``max_cols`` if needed
    (column mean preserved).
    """
    s = _push(style)
    if not users_commits:
        return
    df = pd.concat(users_commits, axis=1).sort_index().astype(float).fillna(0.0)
    w = df.resample("W-MON", label="left", closed="left").sum()
    x = w.T.to_numpy(dtype=float)
    m = x.mean(axis=1, keepdims=True)
    sd = x.std(axis=1, keepdims=True)
    sd = np.where(sd < 1e-12, 1.0, sd)
    z = (x - m) / sd
    t = z.shape[1]
    if t > max_cols:
        n_blk = t // max_cols + (1 if t % max_cols else 0)
        chunk = t // n_blk
        ar = [z[:, i * chunk : (i + 1) * chunk].mean(axis=1) for i in range(n_blk)]
        arr = np.column_stack(ar)
    else:
        arr = z
    users = [str(c) for c in w.columns.tolist()]
    fig, ax = plt.subplots(figsize=(10.0, 0.4 * len(users) + 1.0))
    im = ax.imshow(
        arr, aspect="auto", cmap="coolwarm", vmin=-2.0, vmax=2.0,
        interpolation="nearest",
    )
    ax.set_yticks(range(len(users)))
    ax.set_yticklabels(users)
    ax.set_xlabel("time (week columns; pooled if long)")
    ax.set_title("Weekly commit sums · per-user z-score")
    fig.colorbar(im, ax=ax, label="z", fraction=0.035, pad=0.02)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(
        fig, parts=_meta(period, [f"users={len(users)}", f"raw_weeks={t}"]),
        style=s,
    )
    _save(fig, Path(out), s)


def save_cohort_user_summary(
    user_summary: list[dict[str, object]],
    *,
    out: Path,
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """Horizontal bars for per-user total commits and active-day counts."""
    s = _push(style)
    if not user_summary:
        return
    rows = sorted(
        user_summary,
        key=lambda r: float(r.get("total_commits") or 0.0),
        reverse=True,
    )
    users = [str(r.get("login")) for r in rows]
    totals = np.array([float(r.get("total_commits") or 0.0) for r in rows], dtype=float)
    active = np.array([float(r.get("active_days") or 0.0) for r in rows], dtype=float)
    y = np.arange(len(rows))
    fig, axes = plt.subplots(
        1, 2, figsize=(12.5, max(3.2, 0.38 * len(rows) + 1.4)), sharey=True,
    )
    ax0, ax1 = axes
    ax0.barh(y, totals, color=s.palette[0], alpha=0.88)
    ax0.set_yticks(y)
    ax0.set_yticklabels(users)
    ax0.invert_yaxis()
    ax0.set_xlabel("total commits")
    ax0.set_title("Cohort commits by user")
    ax1.barh(y, active, color=s.palette[2], alpha=0.88)
    ax1.set_xlabel("active days")
    ax1.set_title("Active days in window")
    for ax in axes:
        ax.grid(axis="x", alpha=0.45)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(fig, parts=_meta(period, [f"users={len(rows)}"]), style=s)
    _save(fig, Path(out), s)
