"""
Multi-user comparison visualisations.

Provides:
- :func:`save_multi_user_overview`     — per-user MA + z(solar) overlay
- :func:`save_multi_user_heatmap`      — user × metric Spearman heatmap (FDR-flagged)
- :func:`save_multi_user_rank_matrix`  — pairwise user×user activity correlation
- :func:`save_multi_user_cumulative`   — cumulative commits vs z(solar)
- :func:`save_multi_user_phase`        — commit MA aligned to solar-cycle phase
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from sunspot.align.join import zscore  # noqa: E402
from sunspot.stats.multi_user import multi_user_rank_matrix  # noqa: E402
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


def _meta(*, period: Period, extras: list[str] | None = None) -> list[str]:
    parts: list[str] = []
    pl = period_label(period[0] if period else None, period[1] if period else None)
    if pl:
        parts.append(pl)
    if extras:
        parts.extend(extras)
    return parts


def _save(fig, out: Path, s: PlotStyle) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=s.dpi, bbox_inches="tight", facecolor=s.axis_bg)
    plt.close(fig)


def save_multi_user_overview(
    users_commits: dict[str, pd.Series],
    solar: pd.Series,
    *,
    out: Path,
    window: int = 30,
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """Two stacked panels: per-user MA on top, z(solar) below."""
    s = _push(style)
    if not users_commits:
        return
    indices = [v.index for v in users_commits.values()]
    idx = indices[0]
    for ix in indices[1:]:
        idx = idx.union(ix)
    idx = idx.sort_values()
    fig, axes = plt.subplots(2, 1, sharex=True, figsize=(13, 6.4), height_ratios=[1.4, 1.0])
    ax0, ax1 = axes
    for i, (u, v) in enumerate(users_commits.items()):
        c = v.reindex(idx, fill_value=0.0).astype(float)
        ma = c.rolling(window, min_periods=1).mean()
        ax0.plot(
            ma.index, ma.to_numpy(), color=s.palette[i % len(s.palette)],
            linewidth=s.line_width, label=f"{u}  (Σ={int(c.sum())})",
        )
    ax0.set_ylabel(f"commits / day ({window}d MA)")
    ax0.legend(loc="upper left", ncol=min(3, max(1, len(users_commits))))
    ax0.set_title(f"Per-user commit activity ({window}d MA)")
    sl = solar.name or "solar"
    z = zscore(solar.reindex(idx))
    ax1.fill_between(idx, 0.0, z.to_numpy(), color=s.palette[1], alpha=0.18)
    ax1.plot(
        idx, z.to_numpy(), color=s.palette[1], linewidth=s.line_width, label=f"z({sl})",
    )
    ax1.axhline(0.0, color=s.grid_color, linewidth=0.6)
    ax1.set_ylabel(f"z({sl})")
    ax1.legend(loc="upper right")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(
        fig, parts=_meta(period=period, extras=[f"users={len(users_commits)}"]), style=s,
    )
    _save(fig, Path(out), s)


def save_multi_user_heatmap(
    long_df: pd.DataFrame,
    *,
    out: Path,
    metric_order: list[str] | None = None,
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """User × metric Spearman heatmap; FDR-significant cells ringed."""
    s = _push(style)
    if long_df.empty:
        return
    users = sorted(long_df["user"].unique().tolist())
    if metric_order is None:
        metric_order = sorted(long_df["metric"].unique().tolist())
    arr = np.full((len(users), len(metric_order)), np.nan, dtype=float)
    sig = np.zeros_like(arr, dtype=bool)
    for i, u in enumerate(users):
        sub = long_df[long_df["user"] == u]
        for j, m in enumerate(metric_order):
            row = sub[sub["metric"] == m]
            if not row.empty:
                arr[i, j] = float(row["rho"].iloc[0])
                sig[i, j] = bool(row["q_significant"].iloc[0])
    mx = float(np.nanmax(np.abs(arr))) if np.isfinite(arr).any() else 1.0
    mx = mx if mx > 0 else 1.0
    fig, ax = plt.subplots(
        figsize=(2.0 + 0.95 * len(metric_order), 1.2 + 0.46 * len(users)),
    )
    im = ax.imshow(arr, cmap="RdBu_r", vmin=-mx, vmax=mx, aspect="auto")
    ax.set_xticks(range(len(metric_order)))
    ax.set_xticklabels(metric_order)
    ax.set_yticks(range(len(users)))
    ax.set_yticklabels(users)
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            v = arr[i, j]
            if np.isfinite(v):
                color = "white" if abs(v) > 0.55 else s.axis_fg
                ax.text(
                    j, i, f"{v:+.2f}", ha="center", va="center",
                    fontsize=s.base_size * 0.85, color=color,
                )
                if sig[i, j]:
                    ax.scatter(
                        j, i, marker="o", s=120, facecolors="none",
                        edgecolors=s.axis_fg, linewidths=1.2,
                    )
    ax.set_title("Per-user Spearman vs metric · FDR-significant ringed")
    fig.colorbar(im, ax=ax, label="ρ", fraction=0.046, pad=0.02)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(
        fig, parts=_meta(period=period, extras=[f"users={len(users)}", "○ = q<FDR"]), style=s,
    )
    _save(fig, Path(out), s)


def save_multi_user_rank_matrix(
    users_commits: dict[str, pd.Series],
    *,
    out: Path,
    smoothing_window: int = 30,
    method: str = "spearman",
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """Pairwise user×user correlation of smoothed commit activity."""
    s = _push(style)
    mat = multi_user_rank_matrix(
        users_commits, method=method, smoothing_window=smoothing_window,
    )
    if mat.empty:
        return
    arr = mat.to_numpy(dtype=float)
    n = len(mat.columns)
    fig, ax = plt.subplots(figsize=(1.6 + 0.7 * n, 1.4 + 0.6 * n))
    im = ax.imshow(arr, cmap="RdBu_r", vmin=-1.0, vmax=1.0)
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(mat.columns, rotation=45, ha="right")
    ax.set_yticklabels(mat.index)
    for i in range(n):
        for j in range(n):
            v = arr[i, j]
            if np.isfinite(v):
                color = "white" if abs(v) > 0.55 else s.axis_fg
                ax.text(
                    j, i, f"{v:+.2f}", ha="center", va="center",
                    fontsize=s.base_size * 0.85, color=color,
                )
    ax.set_title(f"Pairwise {method} of users (smoothing={smoothing_window}d)")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02, label=f"{method} ρ")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(
        fig, parts=_meta(period=period, extras=[f"smoothing={smoothing_window}d"]), style=s,
    )
    _save(fig, Path(out), s)


def save_multi_user_cumulative(
    users_commits: dict[str, pd.Series],
    solar: pd.Series,
    *,
    out: Path,
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """Cumulative commits over time for each user, z(solar) on right axis."""
    s = _push(style)
    if not users_commits:
        return
    indices = [v.index for v in users_commits.values()]
    idx = indices[0]
    for ix in indices[1:]:
        idx = idx.union(ix)
    idx = idx.sort_values()
    fig, ax0 = plt.subplots(figsize=(13, 4.6))
    for i, (u, v) in enumerate(users_commits.items()):
        c = v.reindex(idx, fill_value=0.0).astype(float).cumsum()
        ax0.plot(
            c.index, c.to_numpy(), color=s.palette[i % len(s.palette)],
            linewidth=s.line_width, label=f"{u}  (Σ={int(c.iloc[-1])})",
        )
    ax0.set_ylabel("cumulative commits")
    ax1 = ax0.twinx()
    sl = solar.name or "solar"
    z = zscore(solar.reindex(idx))
    ax1.plot(
        idx, z.to_numpy(), color=s.axis_fg, linewidth=s.line_width * 0.7,
        alpha=0.55, label=f"z({sl})",
    )
    ax1.set_ylabel(f"z({sl})")
    ax0.set_title("Cumulative commits per user with solar context")
    h0, l0 = ax0.get_legend_handles_labels()
    h1, l1 = ax1.get_legend_handles_labels()
    ax0.legend(h0 + h1, l0 + l1, loc="upper left", ncol=2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(fig, parts=_meta(period=period), style=s)
    _save(fig, Path(out), s)


def save_multi_user_phase(
    users_commits: dict[str, pd.Series],
    ssn: pd.Series,
    *,
    out: Path,
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """
    Per-user commit MA(30) versus z(SSN) using a *shared* x-axis of z(SSN)
    rank — a "solar-state" view that re-orders calendar days by activity level.
    Useful to ask: do users commit more on solar-quiet vs solar-active days?
    """
    s = _push(style)
    if not users_commits or ssn.dropna().empty:
        return
    z = zscore(ssn).dropna()
    if z.empty:
        return
    rank = z.rank() / len(z)
    fig, ax = plt.subplots(figsize=(11, 4.6))
    n_bins = 12
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    centers = (bins[:-1] + bins[1:]) / 2.0
    z_bin_means = np.array([
        z.iloc[((rank > bins[k]) & (rank <= bins[k + 1])).to_numpy()].mean()
        for k in range(n_bins)
    ])
    width = 1.0 / n_bins * 0.95
    for i, (u, v) in enumerate(users_commits.items()):
        c = v.reindex(z.index, fill_value=0.0).astype(float)
        means = np.array([
            c.iloc[((rank > bins[k]) & (rank <= bins[k + 1])).to_numpy()].mean()
            for k in range(n_bins)
        ])
        offset = (i - len(users_commits) / 2 + 0.5) * (width / max(1, len(users_commits)))
        ax.bar(
            centers + offset, means, width=width / max(1, len(users_commits)),
            color=s.palette[i % len(s.palette)], alpha=0.85, label=u,
        )
    ax.set_xlabel("solar-state quantile of z(SSN)  (0 = quiet, 1 = active)")
    ax.set_ylabel("mean commits / day in bin")
    ax.set_title("Mean commits per user, conditioned on z(SSN) quantile")
    ax.legend(loc="upper right", ncol=min(3, max(1, len(users_commits))))
    sec = ax.secondary_xaxis(
        "top",
        functions=(
            lambda q: np.interp(q, centers, z_bin_means),
            lambda v: np.interp(v, np.sort(z_bin_means), centers[np.argsort(z_bin_means)]),
        ),
    )
    sec.set_xlabel("mean z(SSN) per quantile bin")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(
        fig, parts=_meta(period=period, extras=[f"bins={n_bins}", f"users={len(users_commits)}"]),
        style=s,
    )
    _save(fig, Path(out), s)
