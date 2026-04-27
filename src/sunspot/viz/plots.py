"""
Plot functions for the sunspot pipeline.

All plots share a configurable :class:`~sunspot.viz.style.PlotStyle`. Pass
``style=`` to override per-plot, or call :func:`sunspot.viz.style.set_style`
to change the global defaults. Most plots accept ``period=(since, until)`` so
they can render the analysis window as part of the metadata footer.
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
from sunspot.stats.correlation import (  # noqa: E402
    CCFResult,
    LagResult,
    acf_values,
    association_metrics,
    cross_correlation_function,
    cross_metric_corr_matrix,
    durbin_watson,
    lag_window_grid,
    moving_average_correlation_curve,
    pacf_values,
    pearson_with_ci,
)
from sunspot.stats.spectral import Periodogram, lomb_scargle_periodogram  # noqa: E402
from sunspot.viz.style import (  # noqa: E402
    PlotStyle,
    apply_rcparams,
    get_style,
    metadata_footer,
    period_label,
)

Period = tuple[date | None, date | None] | None


def _meta(
    n: int | None = None,
    *,
    period: Period = None,
    extras: list[str] | None = None,
) -> list[str]:
    """Build the standard metadata footer parts."""
    parts: list[str] = []
    pl = period_label(period[0] if period else None, period[1] if period else None)
    if pl:
        parts.append(pl)
    if n is not None:
        parts.append(f"n={n}")
    if extras:
        parts.extend(extras)
    return parts


def _save(fig, out: Path, style: PlotStyle) -> None:
    fig.savefig(out, dpi=style.dpi, bbox_inches="tight", facecolor=style.axis_bg)
    plt.close(fig)


def _push_style(style: PlotStyle | None) -> PlotStyle:
    s = style or get_style()
    apply_rcparams(s)
    return s


def _significance_stars(p: float | None) -> str:
    """Return APA-style significance stars for a p-value (``""`` if undefined)."""
    if p is None or not np.isfinite(p):
        return ""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    if p < 0.10:
        return "·"
    return "ⁿˢ"


def _p_label(p: float | None) -> str:
    """Compact ``p = 1.2e-04 ***`` formatter; empty when p is None/nan."""
    if p is None or not np.isfinite(p):
        return ""
    stars = _significance_stars(p)
    if p < 0.001:
        body = f"p<{1e-3:.0e}"
    elif p < 0.01:
        body = f"p={p:.3f}"
    else:
        body = f"p={p:.3f}"
    return f"{body} {stars}".strip()


def save_dual_axis(
    commits: pd.Series,
    solar: pd.Series,
    *,
    out: Path,
    right_label: str = "solar / geo",
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """Daily commits + z(metric) on twin y-axes (full UTC-day series)."""
    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    c = commits.sort_index().astype(float)
    sol = solar.sort_index().astype(float)
    common = c.index.intersection(sol.index)
    c = c.reindex(common)
    sol = sol.reindex(common)
    fig, ax0 = plt.subplots(figsize=(12, 4.2))
    ax0.plot(
        c.index, c.to_numpy(), color=s.palette[0],
        linewidth=s.line_width * 0.55, alpha=0.55, label="commits / day",
    )
    ax0.plot(
        c.index, c.rolling(30, min_periods=1).mean().to_numpy(),
        color=s.palette[0], linewidth=s.line_width, label="commits 30d MA",
    )
    ax0.set_ylabel("commits / day", color=s.palette[0])
    ax0.tick_params(axis="y", labelcolor=s.palette[0])
    ax1 = ax0.twinx()
    sc = zscore(sol)
    ax1.plot(
        sol.index, sc.to_numpy(), color=s.palette[1],
        linewidth=s.line_width, alpha=0.92, label=f"z({right_label})",
    )
    ax1.set_ylabel(f"z({right_label})", color=s.palette[1])
    ax1.tick_params(axis="y", labelcolor=s.palette[1])
    h0, l0 = ax0.get_legend_handles_labels()
    h1, l1 = ax1.get_legend_handles_labels()
    ax0.legend(h0 + h1, l0 + l1, loc="upper left")
    title = f"Commits and z({right_label}) — UTC daily"
    extras: list[str] = []
    try:
        r, lo, hi, p, _n = pearson_with_ci(c, sol)
        if np.isfinite(r):
            stars = _significance_stars(p)
            title += f"  ·  r={r:+.3f}{stars} [{lo:+.2f}, {hi:+.2f}]"
            extras.append(f"r={r:+.3f}, p={p:.2g}" if p is not None else f"r={r:+.3f}")
    except (ValueError, KeyError):
        pass
    ax0.set_title(title)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(
        fig, parts=_meta(int(c.notna().sum()), period=period, extras=extras), style=s,
    )
    _save(fig, out, s)


def _aligned_xy(commits: pd.Series, solar: pd.Series) -> tuple[pd.Series, pd.Series]:
    c = commits.sort_index()
    sol = solar.sort_index()
    common = c.index.intersection(sol.index)
    c = c.reindex(common)
    sol = sol.reindex(common)
    m = c.notna() & sol.notna()
    return c[m], sol[m]


def save_scatter(
    commits: pd.Series,
    solar: pd.Series,
    *,
    out: Path,
    metric_label: str = "metric",
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """Scatter with OLS line, hexbin density when n>500, and r/ρ/τ in title."""
    s = _push_style(style)
    out = Path(out)
    c, sol = _aligned_xy(commits, solar)
    if c.size == 0:
        raise ValueError("no overlapping data")
    asso = association_metrics(commits, solar)
    x = c.to_numpy()
    y = sol.to_numpy()
    n = int(x.size)
    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    if n > 500:
        hb = ax.hexbin(x, y, gridsize=40, cmap="Blues", mincnt=1)
        fig.colorbar(hb, ax=ax, label="count", fraction=0.046, pad=0.02)
        ax.scatter(x, y, s=6, color=s.palette[1], alpha=0.18, edgecolor="none")
    else:
        ax.scatter(x, y, s=18, color=s.palette[0], alpha=0.65, edgecolor="white", linewidth=0.4)
    if float(np.std(x)) > 0 and float(np.std(y)) > 0:
        coef = np.polyfit(x, y, 1)
        xs = np.linspace(float(x.min()), float(x.max()), 60)
        ax.plot(
            xs, coef[0] * xs + coef[1],
            color=s.palette[1], linewidth=s.line_width * 1.1,
            label=f"OLS: y={coef[0]:.3g}·x+{coef[1]:.3g}",
        )
        ax.legend(loc="upper left")
    by_kind = {a.kind: a for a in asso}
    pe = by_kind.get("pearson")
    sp = by_kind.get("spearman")
    kt = by_kind.get("kendall")
    parts: list[str] = []
    if pe is not None and np.isfinite(pe.value):
        parts.append(f"r={pe.value:+.3f}{_significance_stars(pe.p)}")
    if sp is not None and np.isfinite(sp.value):
        parts.append(f"ρ={sp.value:+.3f}{_significance_stars(sp.p)}")
    if kt is not None and np.isfinite(kt.value):
        parts.append(f"τ={kt.value:+.3f}{_significance_stars(kt.p)}")
    ax.set_title(f"commits vs {metric_label}  ·  " + ", ".join(parts))
    ax.set_xlabel("commits / day")
    ax.set_ylabel(metric_label)
    if pe is not None and pe.p is not None:
        ax.text(
            0.99, 0.02, _p_label(pe.p),
            transform=ax.transAxes, ha="right", va="bottom",
            fontsize=s.base_size * 0.9,
            bbox={"boxstyle": "round,pad=0.25", "facecolor": s.axis_bg,
                  "edgecolor": s.grid_color, "alpha": 0.85},
        )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(fig, parts=_meta(n, period=period,
                                     extras=["* p<.05  ** p<.01  *** p<.001"]), style=s)
    _save(fig, out, s)


def save_regression(
    commits: pd.Series,
    metric: pd.Series,
    *,
    out: Path,
    metric_label: str = "metric",
    period: Period = None,
    style: PlotStyle | None = None,
) -> dict[str, float | int | None]:
    """
    OLS ``commits ~ a + b · z(metric)`` with 95 % CI band and residual diagnostics.

    Returns a dictionary with the fitted coefficients (``b0``, ``b1``), the
    coefficient of determination (``r2``), Pearson r and its 95 % CI / p,
    residual variance (``sigma2``), the **Durbin–Watson** statistic for
    residual lag-1 autocorrelation (≈ 2 → no autocorrelation), and the
    **D'Agostino-Pearson** ``omnibus`` normality test (``stat``, ``p``).

    The diagnostics are also annotated as a small text block in the plot so
    the reader can spot heavy-tailed residuals or model mis-specification at
    a glance.
    """
    from scipy import stats as scipy_stats  # local import keeps top-level light

    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    c, sol = _aligned_xy(commits, metric)
    if c.size < 4:
        raise ValueError("insufficient overlapping data for regression")
    z = zscore(sol)
    x = z.to_numpy(dtype=float)
    y = c.to_numpy(dtype=float)
    n = int(x.size)
    xm = float(x.mean())
    ym = float(y.mean())
    sxx = float(np.sum((x - xm) ** 2))
    if sxx == 0.0:
        raise ValueError("zero variance in regressor")
    b1 = float(np.sum((x - xm) * (y - ym)) / sxx)
    b0 = ym - b1 * xm
    yhat = b0 + b1 * x
    resid = y - yhat
    dof = max(n - 2, 1)
    sigma2 = float(np.sum(resid**2) / dof)
    sst = float(np.sum((y - ym) ** 2))
    r2 = float(1.0 - (sigma2 * dof) / sst) if sst > 0 else float("nan")
    # Durbin–Watson for residual AR(1).
    dw = durbin_watson(resid)
    # D'Agostino–Pearson omnibus normality on residuals (n>=20 required).
    if n >= 20:
        try:
            norm_stat, norm_p = scipy_stats.normaltest(resid)
            norm_stat = float(norm_stat)
            norm_p = float(norm_p)
        except (ValueError, RuntimeWarning):
            norm_stat, norm_p = float("nan"), float("nan")
    else:
        norm_stat, norm_p = float("nan"), float("nan")
    xs = np.linspace(float(x.min()), float(x.max()), 200)
    se = np.sqrt(sigma2 * (1.0 / n + (xs - xm) ** 2 / sxx))
    ci = 1.96 * se
    r, lo, hi, p, _n = pearson_with_ci(c, sol)
    stars = _significance_stars(p)
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    ax.scatter(x, y, s=14, color=s.palette[0], alpha=0.55, edgecolor="white", linewidth=0.4)
    ax.plot(
        xs, b0 + b1 * xs, color=s.palette[1], linewidth=s.line_width * 1.2,
        label=f"OLS: ŷ = {b0:.2f} + {b1:.2f}·z",
    )
    ax.fill_between(
        xs, b0 + b1 * xs - ci, b0 + b1 * xs + ci,
        color=s.palette[1], alpha=0.18, label="95% CI",
    )
    title = f"commits ~ z({metric_label})  ·  r={r:+.3f}{stars}"
    if np.isfinite(lo):
        title += f" [{lo:+.3f}, {hi:+.3f}]"
    ax.set_title(title)
    ax.set_xlabel(f"z({metric_label})")
    ax.set_ylabel("commits / day")
    ax.legend(loc="upper left")
    diag_lines = [
        f"R² = {r2:+.3f}",
        f"DW  = {dw:.2f}" + ("" if 1.5 <= dw <= 2.5 else "  ⚠"),
    ]
    if np.isfinite(norm_p):
        n_stars = _significance_stars(norm_p)
        diag_lines.append(
            f"normality p = {norm_p:.2g}{(' ' + n_stars) if n_stars else ''}",
        )
    ax.text(
        0.01, 0.98, "\n".join(diag_lines),
        transform=ax.transAxes, ha="left", va="top",
        fontsize=s.base_size * 0.78, color=s.axis_fg,
        bbox={"boxstyle": "round,pad=0.30", "facecolor": s.axis_bg,
              "edgecolor": s.grid_color, "alpha": 0.85},
    )
    if p is not None and np.isfinite(p):
        ax.text(
            0.99, 0.02, _p_label(p),
            transform=ax.transAxes, ha="right", va="bottom",
            fontsize=s.base_size * 0.9,
            bbox={"boxstyle": "round,pad=0.25", "facecolor": s.axis_bg,
                  "edgecolor": s.grid_color, "alpha": 0.85},
        )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    inset = fig.add_axes([0.66, 0.62, 0.28, 0.25])
    inset.hist(resid, bins=30, color=s.palette[2], edgecolor="white", linewidth=0.4)
    inset.set_title("residuals", fontsize=s.base_size * 0.78)
    inset.tick_params(labelsize=s.base_size * 0.7)
    metadata_footer(fig, parts=_meta(n, period=period, extras=[f"σ²={sigma2:.2f}"]), style=s)
    _save(fig, out, s)
    return {
        "n": n,
        "b0": float(b0),
        "b1": float(b1),
        "r2": r2,
        "sigma2": sigma2,
        "pearson_r": float(r) if np.isfinite(r) else None,
        "pearson_p": float(p) if (p is not None and np.isfinite(p)) else None,
        "pearson_lo": float(lo) if np.isfinite(lo) else None,
        "pearson_hi": float(hi) if np.isfinite(hi) else None,
        "durbin_watson": dw,
        "normality_stat": norm_stat,
        "normality_p": norm_p,
    }


def save_rolling_corr(
    commits: pd.Series,
    metric: pd.Series,
    *,
    out: Path,
    window: int = 90,
    metric_label: str = "metric",
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """Rolling Pearson + Spearman with shared zero baseline."""
    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    a = commits.sort_index().astype(float)
    b = metric.sort_index().astype(float)
    common = a.index.intersection(b.index)
    a = a.reindex(common)
    b = b.reindex(common)
    min_p = max(3, window // 3)
    rp = a.rolling(window, min_periods=min_p).corr(b)
    rs = a.rank().rolling(window, min_periods=min_p).corr(b.rank())
    fig, ax = plt.subplots(figsize=(12, 3.8))
    ax.axhline(0.0, color=s.grid_color, linewidth=0.8)
    sig_thresh = float(1.96 / np.sqrt(max(window, 2)))
    ax.axhspan(
        -sig_thresh, sig_thresh, color=s.grid_color, alpha=0.30,
        label=f"|r|<{sig_thresh:.2f}  (≈ p≥.05 for n={window})",
    )
    ax.fill_between(rp.index, 0.0, rp.to_numpy(), color=s.palette[0], alpha=0.10)
    ax.plot(
        rp.index, rp.to_numpy(), color=s.palette[0],
        linewidth=s.line_width, label=f"Pearson r ({window}d)",
    )
    ax.plot(
        rs.index, rs.to_numpy(), color=s.palette[1],
        linewidth=s.line_width, label=f"Spearman ρ ({window}d)",
    )
    ax.set_ylim(-1.0, 1.0)
    ax.set_ylabel("rolling correlation")
    rp_arr = rp.to_numpy()
    finite = np.isfinite(rp_arr)
    n_fin = int(finite.sum())
    n_sig = int((np.abs(rp_arr[finite]) > sig_thresh).sum()) if n_fin else 0
    pct_sig = (100.0 * n_sig / n_fin) if n_fin else 0.0
    ax.set_title(
        f"Rolling correlation: commits vs {metric_label}  ·  "
        f"{n_sig}/{n_fin} windows |r|>{sig_thresh:.2f} ({pct_sig:.0f} %)",
    )
    ax.legend(loc="upper right")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(
        fig, parts=_meta(n_fin, period=period, extras=[f"window={window}d"]), style=s,
    )
    _save(fig, out, s)


def save_lag_heatmap(
    commits: pd.Series,
    metric: pd.Series,
    *,
    out: Path,
    lags: list[int] | None = None,
    windows: list[int] | None = None,
    metric_label: str = "metric",
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """Heatmap of median rolling Spearman across (lag × window)."""
    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    grid, lag_list, win_list = lag_window_grid(
        commits, metric, lags=lags, windows=windows, method="spearman",
    )
    if not np.isfinite(grid).any():
        raise ValueError("no finite cells in lag×window grid")
    mx = float(np.nanmax(np.abs(grid)))
    mx = mx if mx > 0 else 1.0
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    im = ax.imshow(
        grid, aspect="auto", origin="lower", cmap="RdBu_r", vmin=-mx, vmax=mx,
        extent=[-0.5, len(win_list) - 0.5, lag_list[0], lag_list[-1]],
    )
    ax.set_xticks(range(len(win_list)))
    ax.set_xticklabels([f"{w}d" for w in win_list])
    ax.set_xlabel("rolling window")
    ax.set_ylabel("lag (days); positive ⇒ commits lead")
    ax.set_title(f"Median rolling Spearman, commits vs {metric_label}")
    flat = np.where(np.isfinite(grid), grid, -np.inf)
    i_max, j_max = np.unravel_index(int(np.argmax(flat)), grid.shape)
    ax.scatter(
        j_max, lag_list[i_max], s=140,
        facecolors="none", edgecolors=s.axis_fg, linewidths=1.6,
        label=f"peak ρ={grid[i_max, j_max]:+.3f} @ lag={lag_list[i_max]}, w={win_list[j_max]}d",
    )
    ax.legend(loc="lower right")
    fig.colorbar(im, ax=ax, label="ρ", fraction=0.046, pad=0.02)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(
        fig, parts=_meta(period=period, extras=[
            f"lags ∈ [{lag_list[0]}, {lag_list[-1]}]",
            f"windows: {','.join(str(w) for w in win_list)}d",
        ]), style=s,
    )
    _save(fig, out, s)


def save_distribution(
    commits: pd.Series,
    metric: pd.Series,
    *,
    out: Path,
    metric_label: str = "metric",
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """Two-panel distributions: commits (log-y) and metric, with descriptive stats."""
    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    c = commits.dropna().astype(float)
    sm = metric.dropna().astype(float)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.0))
    axes[0].hist(c.to_numpy(), bins=40, color=s.palette[0], edgecolor="white", linewidth=0.5)
    axes[0].set_yscale("log")
    axes[0].set_title("commits / day  (log y)")
    axes[0].set_xlabel("commits")
    cstats = (
        f"n={c.size}, μ={c.mean():.2f}, σ={c.std():.2f}\n"
        f"median={c.median():.1f}, max={c.max():.0f}, p99={c.quantile(0.99):.1f}"
    )
    axes[0].text(
        0.97, 0.95, cstats, transform=axes[0].transAxes, ha="right", va="top",
        fontsize=s.base_size * 0.85,
        bbox=dict(facecolor="white", edgecolor=s.grid_color, alpha=0.9),
    )
    axes[1].hist(sm.to_numpy(), bins=40, color=s.palette[1], edgecolor="white", linewidth=0.5)
    axes[1].set_title(f"{metric_label} (daily)")
    axes[1].set_xlabel(metric_label)
    sstats = (
        f"n={sm.size}, μ={sm.mean():.2f}, σ={sm.std():.2f}\n"
        f"median={sm.median():.2f}, min={sm.min():.2f}, max={sm.max():.2f}"
    )
    axes[1].text(
        0.97, 0.95, sstats, transform=axes[1].transAxes, ha="right", va="top",
        fontsize=s.base_size * 0.85,
        bbox=dict(facecolor="white", edgecolor=s.grid_color, alpha=0.9),
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(fig, parts=_meta(period=period), style=s)
    _save(fig, out, s)


def save_monthly(
    commits: pd.Series,
    metric: pd.Series,
    *,
    out: Path,
    metric_label: str = "metric",
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """Monthly commit totals (bars) with metric monthly mean overlay (twin axis)."""
    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    c = commits.sort_index().astype(float)
    sm = metric.sort_index().astype(float)
    cm = c.resample("MS").sum()
    smm = sm.resample("MS").mean()
    fig, ax0 = plt.subplots(figsize=(12, 4.0))
    ax0.bar(
        cm.index, cm.to_numpy(), width=22.0,
        color=s.palette[0], alpha=0.85, label="commits / month",
    )
    ax0.set_ylabel("commits / month", color=s.palette[0])
    ax0.tick_params(axis="y", labelcolor=s.palette[0])
    ax1 = ax0.twinx()
    ax1.plot(
        smm.index, smm.to_numpy(), color=s.palette[1],
        linewidth=s.line_width * 1.1, label=f"{metric_label} monthly mean",
    )
    ax1.set_ylabel(metric_label, color=s.palette[1])
    ax1.tick_params(axis="y", labelcolor=s.palette[1])
    title = f"Monthly commits vs {metric_label}"
    extras: list[str] = [f"months={int(cm.size)}"]
    try:
        joint = pd.concat([cm.rename("commits"), smm.rename(metric_label)], axis=1).dropna()
        if len(joint) >= 4:
            r, lo, hi, p, _n = pearson_with_ci(joint["commits"], joint[metric_label])
            if np.isfinite(r):
                stars = _significance_stars(p)
                title += f"  ·  monthly r={r:+.3f}{stars} [{lo:+.2f}, {hi:+.2f}]"
                extras.append(f"monthly r p={p:.2g}" if p is not None else "")
    except (ValueError, KeyError):
        pass
    ax0.set_title(title)
    h0, _l0 = ax0.get_legend_handles_labels()
    h1, _l1 = ax1.get_legend_handles_labels()
    ax0.legend(h0 + h1, [_l0[0], _l1[0]], loc="upper left")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(
        fig, parts=_meta(int(cm.size), period=period, extras=[e for e in extras if e]),
        style=s,
    )
    _save(fig, out, s)


def save_metric_correlation_matrix(
    frame: pd.DataFrame,
    *,
    out: Path,
    method: str = "spearman",
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """Annotated heatmap of pairwise correlations between columns of ``frame``."""
    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    mat = cross_metric_corr_matrix(frame, method=method)
    arr = mat.to_numpy(dtype=float)
    side = 1.4 + 0.7 * len(mat.columns)
    fig, ax = plt.subplots(figsize=(side, side))
    im = ax.imshow(arr, cmap="RdBu_r", vmin=-1.0, vmax=1.0)
    ax.set_xticks(range(len(mat.columns)))
    ax.set_yticks(range(len(mat.index)))
    ax.set_xticklabels(mat.columns, rotation=45, ha="right")
    ax.set_yticklabels(mat.index)
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            v = arr[i, j]
            if np.isfinite(v):
                color = "white" if abs(v) > 0.55 else s.axis_fg
                ax.text(
                    j, i, f"{v:+.2f}", ha="center", va="center",
                    fontsize=s.base_size * 0.85, color=color,
                )
    ax.set_title(f"Pairwise {method} correlations")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label=f"{method} ρ")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(fig, parts=_meta(period=period, extras=[f"method={method}"]), style=s)
    _save(fig, out, s)


def save_metrics_zscored_overview(
    commits: pd.Series,
    metrics_frame: pd.DataFrame,
    *,
    out: Path,
    ma_window: int = 30,
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """Top: commits MA. Bottom: every metric z-scored on the same calendar axis."""
    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    c = commits.sort_index().astype(float)
    fig, axes = plt.subplots(2, 1, sharex=True, figsize=(13, 6.4), height_ratios=[1.0, 1.4])
    axes[0].plot(
        c.index, c.rolling(ma_window, min_periods=1).mean().to_numpy(),
        color=s.axis_fg, linewidth=s.line_width * 1.2, label=f"commits, {ma_window}d MA",
    )
    axes[0].fill_between(
        c.index, 0.0, c.rolling(ma_window, min_periods=1).mean().to_numpy(),
        color=s.axis_fg, alpha=0.10,
    )
    axes[0].set_ylabel(f"commits MA{ma_window}")
    axes[0].legend(loc="upper right")
    for i, col in enumerate(metrics_frame.columns):
        z = zscore(metrics_frame[col].astype(float))
        axes[1].plot(
            z.index, z.to_numpy(), color=s.palette[i % len(s.palette)],
            linewidth=s.line_width * 0.9, alpha=0.92, label=f"z({col})",
        )
    axes[1].axhline(0.0, color=s.grid_color, linewidth=0.6)
    axes[1].set_ylabel("z-score")
    axes[1].legend(loc="upper right", ncol=min(5, max(1, len(metrics_frame.columns))))
    axes[1].set_title("Solar / geo metrics (z-scored, daily)")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(
        fig, parts=_meta(int(c.notna().sum()), period=period,
                         extras=[f"metrics: {', '.join(metrics_frame.columns)}"]), style=s,
    )
    _save(fig, out, s)


def save_lag_grid(
    lag_results: dict[str, LagResult],
    *,
    out: Path,
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """Small-multiples grid of per-metric lag curves."""
    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    items = list(lag_results.items())
    n = len(items)
    if n == 0:
        return
    cols = min(3, n)
    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(4.6 * cols, 3.0 * rows), sharex=True)
    axes_arr = np.atleast_2d(axes).reshape(rows, cols)
    for k, (name, res) in enumerate(items):
        i, j = divmod(k, cols)
        ax = axes_arr[i, j]
        ax.axhline(0.0, color=s.grid_color, linewidth=0.6)
        ax.plot(res.lags, res.values, color=s.palette[k % len(s.palette)],
                linewidth=s.line_width)
        ax.axvline(res.best_lag, color=s.axis_fg, linewidth=s.line_width * 0.6,
                   linestyle="--")
        ax.set_title(
            f"{name}: best lag={res.best_lag}, ρ={res.best_value:+.3f}",
            fontsize=s.base_size,
        )
        ax.set_xlabel("lag (days)")
        ax.set_ylabel("ρ")
    for k in range(n, rows * cols):
        i, j = divmod(k, cols)
        axes_arr[i, j].set_axis_off()
    fig.suptitle("Per-metric lag-search curves (positive ⇒ commits lead)")
    fig.tight_layout(rect=(0, 0.04, 1, 0.97))
    metadata_footer(fig, parts=_meta(period=period), style=s)
    _save(fig, out, s)


def save_top_repos_ma(
    commits_by_repo: dict[str, pd.Series],
    solar: pd.Series,
    *,
    out: Path,
    top_n: int = 8,
    window: int = 30,
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """Top-N repos by total commits as ``window``-day MA, with z(solar) overlay."""
    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    items = [
        (k, v) for k, v in commits_by_repo.items()
        if k and k != "__all__" and v is not None and len(v)
    ]
    items.sort(key=lambda kv: float(kv[1].sum()), reverse=True)
    items = items[:top_n]
    if not items:
        return
    idx = items[0][1].index
    for _k, v in items[1:]:
        idx = idx.union(v.index)
    idx = idx.sort_values()
    fig, ax0 = plt.subplots(figsize=(13, 5.0))
    for i, (k, v) in enumerate(items):
        ma = v.reindex(idx, fill_value=0.0).rolling(window, min_periods=1).mean()
        ax0.plot(
            ma.index, ma.to_numpy(), color=s.palette[i % len(s.palette)],
            linewidth=s.line_width, label=k,
        )
    ax0.set_ylabel(f"commits / day ({window}d MA)")
    ax1 = ax0.twinx()
    z = zscore(solar.reindex(idx))
    ax1.plot(
        idx, z.to_numpy(), color=s.axis_fg, linewidth=s.line_width * 0.7,
        alpha=0.6, label=f"z({solar.name or 'solar'})",
    )
    ax1.set_ylabel("z(solar)")
    ax0.set_title(
        f"Top {len(items)} repos by total commits ({window}d MA) and z({solar.name or 'solar'})",
    )
    h0, l0 = ax0.get_legend_handles_labels()
    h1, l1 = ax1.get_legend_handles_labels()
    ax0.legend(h0 + h1, l0 + l1, loc="upper left", ncol=2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(fig, parts=_meta(period=period, extras=[f"top_n={len(items)}"]), style=s)
    _save(fig, out, s)


def save_repo_metric_spearman_heatmap(
    per_repo_df: pd.DataFrame,
    *,
    out: Path,
    metric_order: list[str] | None = None,
    top_n: int = 30,
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """Repo (rows) × metric (cols) Spearman heatmap with FDR-significance markers."""
    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if per_repo_df.empty:
        return
    if metric_order is None:
        metric_order = sorted(per_repo_df["metric"].unique().tolist())
    totals = (
        per_repo_df.groupby("repo")["total_commits"]
        .max()
        .sort_values(ascending=False)
        .head(top_n)
    )
    repos = totals.index.tolist()
    arr = np.full((len(repos), len(metric_order)), np.nan, dtype=float)
    sig = np.zeros_like(arr, dtype=bool)
    for i, r in enumerate(repos):
        sub = per_repo_df[per_repo_df["repo"] == r]
        for j, m in enumerate(metric_order):
            row = sub[sub["metric"] == m]
            if not row.empty:
                arr[i, j] = float(row["rho"].iloc[0])
                sig[i, j] = bool(row["q_significant"].iloc[0])
    mx = float(np.nanmax(np.abs(arr))) if np.isfinite(arr).any() else 1.0
    mx = mx if mx > 0 else 1.0
    fig, ax = plt.subplots(
        figsize=(2.0 + 0.85 * len(metric_order), 0.8 + 0.32 * len(repos)),
    )
    im = ax.imshow(arr, cmap="RdBu_r", vmin=-mx, vmax=mx, aspect="auto")
    ax.set_xticks(range(len(metric_order)))
    ax.set_xticklabels(metric_order)
    ax.set_yticks(range(len(repos)))
    ax.set_yticklabels(repos, fontsize=s.base_size * 0.78)
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            if np.isfinite(arr[i, j]) and sig[i, j]:
                ax.scatter(
                    j, i, marker="o", s=42, facecolors="none",
                    edgecolors=s.axis_fg, linewidths=1.3,
                )
    ax.set_title(
        f"Per-repo Spearman vs metric · FDR-flagged ringed (top {len(repos)} by commits)",
    )
    fig.colorbar(im, ax=ax, label="ρ", fraction=0.04, pad=0.02)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(
        fig, parts=_meta(period=period, extras=[f"top_n={len(repos)}", "○ = q<FDR"]), style=s,
    )
    _save(fig, out, s)


def save_commits_solar_dynamics(
    commits: pd.Series,
    ssn: pd.Series,
    f107: pd.Series,
    *,
    out: Path,
    title: str = "",
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """Daily commits with 7d/30d MA on top, z(SSN) and z(F10.7) below."""
    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    c = commits.sort_index().astype(float)
    common = c.index
    s_sn = ssn.reindex(common)
    s_f = f107.reindex(common)
    r7 = c.rolling(7, min_periods=1).mean()
    r30 = c.rolling(30, min_periods=1).mean()
    fig, axes = plt.subplots(2, 1, sharex=True, figsize=(13, 6.6), height_ratios=[1.0, 1.0])
    ax0, ax1 = axes
    ax0.plot(
        c.index, c.to_numpy(), color=s.palette[0],
        linewidth=s.line_width * 0.35, label="daily", alpha=0.5,
    )
    ax0.plot(
        r7.index, r7.to_numpy(), color=s.palette[3],
        linewidth=s.line_width, label="7d MA",
    )
    ax0.plot(
        r30.index, r30.to_numpy(), color=s.palette[1],
        linewidth=s.line_width * 1.2, label="30d MA",
    )
    ax0.set_ylabel("commits / day")
    ax0.set_title(title or "Commit activity and solar indices (UTC day)")
    ax0.legend(loc="upper right")
    z1 = zscore(s_sn)
    z2 = zscore(s_f)
    l1 = "z(SSN)" if s_sn.name is None else f"z({s_sn.name})"
    l2 = "z(F10.7)" if s_f.name is None else f"z({s_f.name})"
    ax1.plot(common, z1.to_numpy(), color=s.palette[2], linewidth=s.line_width, label=l1)
    ax1.plot(common, z2.to_numpy(), color=s.palette[4], linewidth=s.line_width, label=l2)
    ax1.axhline(0.0, color=s.grid_color, linewidth=0.6)
    ax1.set_ylabel("z (same window)")
    ax1.legend(loc="upper right")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(fig, parts=_meta(int(c.notna().sum()), period=period), style=s)
    _save(fig, out, s)


def save_compare_users_moving_averages(
    user_series: dict[str, pd.Series],
    solar: pd.Series,
    *,
    out: Path,
    window: int = 30,
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """Per-user MA overlay + z(solar) on the right axis."""
    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if not user_series:
        return
    alld: list[pd.Index] = [v.index for v in user_series.values()]
    idx = alld[0]
    for ix in alld[1:]:
        idx = idx.union(ix)
    idx = idx.sort_values()
    fig, ax0 = plt.subplots(figsize=(13, 4.6))
    for i, (un, v) in enumerate(user_series.items()):
        c = v.reindex(idx, fill_value=0.0).astype(float)
        ma = c.rolling(window, min_periods=1).mean()
        ax0.plot(
            ma.index, ma.to_numpy(), color=s.palette[i % len(s.palette)],
            linewidth=s.line_width, label=f"{un} ({window}d MA)",
        )
    ax0.set_ylabel(f"commits / day ({window}d MA)")
    ax1 = ax0.twinx()
    sl = solar.name or "solar"
    zv = zscore(solar.reindex(idx))
    ax1.plot(
        idx, zv.to_numpy(), color=s.axis_fg, linewidth=s.line_width * 0.7,
        alpha=0.55, label=f"z({sl})",
    )
    ax1.set_ylabel(f"z({sl})")
    ax0.set_title(f"Multi-user commit MA{window} and z({sl})")
    h0, l0 = ax0.get_legend_handles_labels()
    h1, l1 = ax1.get_legend_handles_labels()
    ax0.legend(h0 + h1, l0 + l1, loc="upper left", ncol=2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(
        fig, parts=_meta(period=period, extras=[f"users={len(user_series)}"]), style=s,
    )
    _save(fig, out, s)


def save_lag_plot(
    res: LagResult,
    out: Path,
    *,
    metric_label: str | None = None,
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """Single lag-search curve."""
    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axhline(0.0, color=s.grid_color, linewidth=0.6)
    ax.plot(res.lags, res.values, color=s.palette[0], linewidth=s.line_width)
    n_sig = 0
    if res.p_values is not None:
        sig_mask = np.array(
            [p is not None and np.isfinite(p) and p < 0.05 for p in res.p_values],
            dtype=bool,
        )
        if sig_mask.any():
            sig_x = np.array(res.lags)[sig_mask]
            sig_y = np.array(res.values)[sig_mask]
            ax.scatter(
                sig_x, sig_y, s=42, marker="o", facecolors="none",
                edgecolors=s.palette[2], linewidths=1.4,
                label=f"p<.05 ({int(sig_mask.sum())} lag(s))", zorder=4,
            )
            n_sig = int(sig_mask.sum())
    best_p: float | None = None
    if res.p_values is not None:
        try:
            best_p = res.p_values[res.lags.index(res.best_lag)]
        except (ValueError, IndexError):
            best_p = None
    star = _significance_stars(best_p)
    ax.axvline(
        res.best_lag, color=s.palette[1], linewidth=s.line_width,
        linestyle="--",
        label=f"peak ρ={res.best_value:+.3f}{star} @ lag={res.best_lag}d",
    )
    ax.set_xlabel("lag (days); positive ⇒ commits lead")
    ax.set_ylabel("correlation")
    ax.set_title(
        f"Lag search{' · ' + metric_label if metric_label else ''}"
        + (f"  ·  {n_sig} lag(s) p<.05" if n_sig else "")
    )
    ax.legend(loc="upper right")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(
        fig, parts=_meta(
            extras=[f"|lag|≤{max(abs(res.lags[0]), abs(res.lags[-1]))}d"], period=period,
        ), style=s,
    )
    _save(fig, out, s)


# -------------------------------- new: spectral / acf / ccf ------------------


def save_ccf(
    commits: pd.Series,
    metric: pd.Series,
    *,
    out: Path,
    max_lag: int = 60,
    method: str = "pearson",
    prewhiten: bool = True,
    metric_label: str = "metric",
    period: Period = None,
    style: PlotStyle | None = None,
) -> CCFResult:
    """Cross-correlation function with Bartlett ±95% bands. Returns the result."""
    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    res = cross_correlation_function(
        commits, metric, max_lag=max_lag, method=method, prewhiten=prewhiten,
    )
    fig, ax = plt.subplots(figsize=(11, 4.0))
    ax.axhline(0.0, color=s.grid_color, linewidth=0.6)
    ax.fill_between(
        res.lags, -res.bartlett_ci, res.bartlett_ci,
        color=s.palette[2], alpha=0.18, label="Bartlett 95% band",
    )
    arr = np.array(res.values, dtype=float)
    color_pos = s.palette[0]
    color_neg = s.palette[1]
    for k, v in zip(res.lags, arr, strict=True):
        if not np.isfinite(v):
            continue
        ax.vlines(
            k, 0, v,
            color=color_pos if v >= 0 else color_neg,
            linewidth=s.line_width * 1.0,
        )
    finite = arr[np.isfinite(arr)]
    n_sig = int((np.abs(finite) > res.bartlett_ci).sum()) if finite.size else 0
    if finite.size:
        i = int(np.nanargmax(np.abs(arr)))
        peak = float(arr[i])
        peak_star = "***" if abs(peak) > res.bartlett_ci else "ⁿˢ"
        ax.scatter(
            res.lags[i], peak, s=70, color=s.axis_fg, zorder=3,
            label=f"peak |ρ|={abs(peak):.3f}{peak_star} @ lag={res.lags[i]}d",
        )
    ax.set_xlabel("lag (days); positive ⇒ commits lead")
    ax.set_ylabel(f"{method} correlation")
    title_pw = " · AR(1)-prewhitened" if prewhiten else ""
    sig_tag = f"  ·  {n_sig} lag(s) outside Bartlett band" if n_sig else ""
    ax.set_title(f"CCF: commits vs {metric_label}{title_pw}{sig_tag}")
    ax.legend(loc="upper right")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(
        fig, parts=_meta(res.n, period=period, extras=[
            f"|lag|≤{max_lag}d", f"method={method}",
            f"prewhiten={prewhiten}",
        ]), style=s,
    )
    _save(fig, out, s)
    return res


def save_acf_pacf(
    series: pd.Series,
    *,
    out: Path,
    n_lags: int = 60,
    label: str = "series",
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """Two stacked panels: ACF and PACF with ±95% white-noise bands."""
    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    acf, ci = acf_values(series, n_lags=n_lags)
    pacf, _ = pacf_values(series, n_lags=min(n_lags, 30))
    fig, axes = plt.subplots(2, 1, figsize=(11, 5.4), sharex=False)
    for ax, arr, name in (
        (axes[0], acf, "ACF"), (axes[1], pacf, "PACF"),
    ):
        if arr.size == 0:
            ax.set_title(f"{name}: insufficient data")
            continue
        ax.axhline(0.0, color=s.grid_color, linewidth=0.6)
        ax.axhline(ci, color=s.palette[2], linewidth=0.8, linestyle="--", alpha=0.8)
        ax.axhline(-ci, color=s.palette[2], linewidth=0.8, linestyle="--", alpha=0.8)
        ax.fill_between(
            range(arr.size), -ci, ci, color=s.palette[2], alpha=0.10,
        )
        ax.vlines(
            range(arr.size), 0.0, arr,
            color=s.palette[0], linewidth=s.line_width * 1.0,
        )
        ax.set_title(f"{name} of {label}")
        ax.set_xlabel("lag (days)")
        ax.set_ylabel(name.lower())
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(
        fig, parts=_meta(int(series.dropna().size), period=period,
                         extras=[f"n_lags={n_lags}"]), style=s,
    )
    _save(fig, out, s)


def save_periodogram(
    series_a: pd.Series,
    series_b: pd.Series | None = None,
    *,
    out: Path,
    label_a: str = "commits",
    label_b: str = "metric",
    period: Period = None,
    style: PlotStyle | None = None,
) -> dict[str, Periodogram]:
    """Lomb–Scargle periodograms for one or two series, period (days) on x."""
    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pa = lomb_scargle_periodogram(series_a)
    res: dict[str, Periodogram] = {label_a: pa}
    fig, ax = plt.subplots(figsize=(11, 4.0))
    if pa.power.size:
        ax.semilogx(
            pa.periods_days, pa.power, color=s.palette[0],
            linewidth=s.line_width, label=f"{label_a} (peak={pa.dominant_period_days:.0f}d)",
        )
        ax.axvline(pa.dominant_period_days, color=s.palette[0], alpha=0.4, linestyle="--")
    if series_b is not None:
        pb = lomb_scargle_periodogram(series_b)
        res[label_b] = pb
        if pb.power.size:
            ax.semilogx(
                pb.periods_days, pb.power, color=s.palette[1],
                linewidth=s.line_width,
                label=f"{label_b} (peak={pb.dominant_period_days:.0f}d)",
            )
            ax.axvline(pb.dominant_period_days, color=s.palette[1], alpha=0.4, linestyle="--")
    for marker, lbl in (
        (7.0, "7d"), (27.0, "27d (Carrington)"),
        (365.25, "1yr"), (365.25 * 11, "11yr (solar cycle)"),
    ):
        ax.axvline(marker, color=s.grid_color, linewidth=0.7, alpha=0.7)
        ax.text(
            marker, ax.get_ylim()[1] * 0.98, lbl,
            rotation=90, va="top", ha="right",
            fontsize=s.base_size * 0.7, color=s.axis_fg, alpha=0.6,
        )
    ax.set_xlabel("period (days, log)")
    ax.set_ylabel("normalised LS power")
    ax.set_title("Lomb–Scargle periodogram")
    if ax.get_legend_handles_labels()[0]:
        ax.legend(loc="upper right")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(
        fig, parts=_meta(pa.n, period=period, extras=["LS-normalised"]), style=s,
    )
    _save(fig, out, s)
    return res


# ---------------------------------------------------------------------------
# Juxtaposition plots: explicit GitHub-activity vs solar-metric views.
# ---------------------------------------------------------------------------


def save_quantile_response(
    commits: pd.Series,
    metric: pd.Series,
    *,
    out: Path,
    metric_label: str,
    n_bins: int = 10,
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """
    Mean (and median) commits per quantile bin of the metric, with bootstrap
    95 % CI bars. Answers: "do GitHub days happen more often when the metric is
    high vs low?" with non-parametric robustness.
    """
    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    c = commits.sort_index().astype(float)
    g = metric.sort_index().astype(float)
    common = c.index.intersection(g.index)
    c = c.reindex(common)
    g = g.reindex(common)
    mask = c.notna() & g.notna()
    c = c[mask].to_numpy()
    g = g[mask].to_numpy()
    if c.size < n_bins * 5:
        raise ValueError(f"too few aligned points ({c.size}) for {n_bins} quantile bins")
    qs = np.linspace(0.0, 1.0, n_bins + 1)
    edges = np.quantile(g, qs)
    edges = np.unique(edges)
    if edges.size < 3:
        raise ValueError("metric has insufficient quantile structure")
    bin_idx = np.clip(np.searchsorted(edges, g, side="right") - 1, 0, edges.size - 2)
    centers = 0.5 * (edges[:-1] + edges[1:])
    rng = np.random.default_rng(0)
    means: list[float] = []
    medians: list[float] = []
    los: list[float] = []
    his: list[float] = []
    counts: list[int] = []
    for k in range(edges.size - 1):
        sel = c[bin_idx == k]
        counts.append(int(sel.size))
        if sel.size == 0:
            means.append(np.nan)
            medians.append(np.nan)
            los.append(np.nan)
            his.append(np.nan)
            continue
        means.append(float(sel.mean()))
        medians.append(float(np.median(sel)))
        boot = rng.choice(sel, size=(400, sel.size), replace=True).mean(axis=1)
        los.append(float(np.quantile(boot, 0.025)))
        his.append(float(np.quantile(boot, 0.975)))
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    centers_arr = np.asarray(centers, dtype=float)
    ax.errorbar(
        centers_arr, means,
        yerr=[np.asarray(means) - np.asarray(los), np.asarray(his) - np.asarray(means)],
        fmt="o-", color=s.palette[0], linewidth=s.line_width,
        markersize=6, capsize=3, label="mean (95 % bootstrap CI)",
    )
    ax.plot(
        centers_arr, medians, "s--", color=s.palette[1],
        linewidth=s.line_width * 0.75, markersize=5, alpha=0.85, label="median",
    )
    overall = float(np.nanmean(c))
    ax.axhline(
        overall, color=s.axis_fg, linewidth=0.8, linestyle=":",
        alpha=0.55, label=f"grand mean = {overall:.2f}",
    )
    bar_ax = ax.twinx()
    bar_ax.bar(
        centers_arr, counts, width=np.diff(edges) * 0.85,
        color=s.grid_color, alpha=0.45, zorder=0,
    )
    bar_ax.set_ylabel("n in bin")
    bar_ax.tick_params(axis="y", colors=s.axis_fg, labelsize=s.base_size * 0.8)
    ax.set_xlabel(f"{metric_label} (binned by quantile)")
    ax.set_ylabel("commits / day")
    ax.set_title(f"Commits response to {metric_label} ({n_bins} quantile bins)")
    ax.legend(loc="upper left", framealpha=0.9)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(
        fig, parts=_meta(int(c.size), period=period, extras=[f"bins={edges.size - 1}"]), style=s,
    )
    _save(fig, out, s)


def save_joint_density(
    commits: pd.Series,
    metric: pd.Series,
    *,
    out: Path,
    metric_label: str,
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """Joint hexbin density with marginal histograms — clear at-a-glance covariation."""
    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    c = commits.sort_index().astype(float)
    g = metric.sort_index().astype(float)
    common = c.index.intersection(g.index)
    c = c.reindex(common)
    g = g.reindex(common)
    mask = c.notna() & g.notna()
    c = c[mask].to_numpy()
    g = g[mask].to_numpy()
    if c.size < 20:
        raise ValueError(f"too few aligned points ({c.size}) for joint density")
    fig = plt.figure(figsize=(8.5, 7.2))
    gs = fig.add_gridspec(
        2, 2, width_ratios=(4.2, 1.0), height_ratios=(1.0, 4.2),
        wspace=0.05, hspace=0.05,
    )
    ax_main = fig.add_subplot(gs[1, 0])
    ax_top = fig.add_subplot(gs[0, 0], sharex=ax_main)
    ax_right = fig.add_subplot(gs[1, 1], sharey=ax_main)
    cmap = "viridis" if s.theme == "light" else "inferno"
    hb = ax_main.hexbin(g, c, gridsize=32, cmap=cmap, mincnt=1)
    if float(np.std(g)) > 0:
        slope, intercept = np.polyfit(g, c, 1)
        xs = np.linspace(g.min(), g.max(), 80)
        ax_main.plot(
            xs, slope * xs + intercept, color=s.palette[1],
            linewidth=s.line_width, alpha=0.85, label="OLS",
        )
    r, lo, hi, p, _ = pearson_with_ci(pd.Series(c), pd.Series(g))
    ax_main.set_title(
        f"r = {r:+.3f}  [{lo:+.2f}, {hi:+.2f}]   p = "
        + ("nan" if p is None or not np.isfinite(p) else f"{p:.2e}"),
        fontsize=s.base_size,
    )
    ax_main.set_xlabel(metric_label)
    ax_main.set_ylabel("commits / day")
    if ax_main.get_legend_handles_labels()[0]:
        ax_main.legend(loc="upper left")
    ax_top.hist(g, bins=40, color=s.palette[0], alpha=0.85)
    ax_top.tick_params(axis="x", labelbottom=False)
    ax_top.set_ylabel("count")
    ax_right.hist(c, bins=40, orientation="horizontal", color=s.palette[2], alpha=0.85)
    ax_right.tick_params(axis="y", labelleft=False)
    ax_right.set_xlabel("count")
    cbar = fig.colorbar(hb, ax=ax_right, fraction=0.18, pad=0.06, shrink=0.85)
    cbar.set_label("days per cell", fontsize=s.base_size * 0.85)
    metadata_footer(
        fig, parts=_meta(int(c.size), period=period, extras=["hexbin + marginals"]), style=s,
    )
    _save(fig, out, s)


def save_seasonal_calendar(
    commits: pd.Series,
    *,
    out: Path,
    solar: pd.Series | None = None,
    solar_label: str = "SSN",
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """
    Year × ordinal-day heatmap of commits, with an optional solar mean strip
    on top so seasonal commit patterns sit directly above the contemporaneous
    solar level.
    """
    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    c = commits.sort_index().astype(float).fillna(0.0)
    if c.empty:
        raise ValueError("seasonal_calendar: empty commit series")
    years = sorted({d.year for d in c.index})
    n_years = len(years)
    if n_years == 0:
        raise ValueError("seasonal_calendar: no usable years")
    grid = np.full((n_years, 366), np.nan, dtype=float)
    for i, y in enumerate(years):
        sub = c[(c.index.year == y)]
        for d, v in sub.items():
            grid[i, d.timetuple().tm_yday - 1] = v
    has_solar = solar is not None and not solar.dropna().empty
    if has_solar:
        annual_solar = (
            solar.dropna()
            .groupby(solar.dropna().index.year)
            .mean()
            .reindex(years)
            .to_numpy()
        )
    else:
        annual_solar = None
    if annual_solar is not None:
        fig = plt.figure(figsize=(13, max(3.0, 0.42 * n_years + 1.4)))
        gs = fig.add_gridspec(2, 1, height_ratios=(1.0, max(2.0, 0.42 * n_years)), hspace=0.12)
        ax_top = fig.add_subplot(gs[0, 0])
        ax = fig.add_subplot(gs[1, 0], sharex=None)
        ax_top.bar(
            np.arange(n_years), annual_solar,
            color=s.palette[1], alpha=0.85, label=f"annual mean {solar_label}",
        )
        ax_top.set_xticks(np.arange(n_years))
        ax_top.set_xticklabels([str(y) for y in years], rotation=0)
        ax_top.set_ylabel(solar_label)
        ax_top.legend(loc="upper right", framealpha=0.9)
        ax_top.set_title("Annual solar context (top) above commit calendar (bottom)")
    else:
        fig, ax = plt.subplots(figsize=(13, max(2.6, 0.42 * n_years + 1.0)))
        ax.set_title("Commit calendar (year × day-of-year)")
    cmap = "magma" if s.theme == "light" else "viridis"
    finite = grid[np.isfinite(grid)]
    vmax = float(np.quantile(finite, 0.985)) if finite.size else 1.0
    vmax = vmax if vmax > 0 else 1.0
    im = ax.imshow(
        grid, aspect="auto", cmap=cmap, vmin=0.0, vmax=vmax,
        interpolation="nearest", origin="lower",
    )
    ax.set_yticks(range(n_years))
    ax.set_yticklabels([str(y) for y in years])
    month_starts = [
        pd.Timestamp(2001, m, 1).timetuple().tm_yday - 1 for m in range(1, 13)
    ]
    ax.set_xticks(month_starts)
    ax.set_xticklabels(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul",
         "Aug", "Sep", "Oct", "Nov", "Dec"],
    )
    ax.set_xlabel("month")
    ax.set_ylabel("year")
    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label(f"commits / day  (vmax = {vmax:.1f})")
    fig.subplots_adjust(left=0.06, right=0.97, top=0.92, bottom=0.10)
    metadata_footer(
        fig, parts=_meta(int(c.notna().sum()), period=period,
                         extras=[f"years={n_years}"] + ([solar_label] if has_solar else [])),
        style=s,
    )
    _save(fig, out, s)


def save_stacked_panel(
    commits: pd.Series,
    metrics_frame: pd.DataFrame,
    *,
    out: Path,
    ma_window: int = 30,
    period: Period = None,
    style: PlotStyle | None = None,
) -> None:
    """
    Vertical small-multiples: top panel is commit MA, then one panel per
    metric. All panels share an x-axis so eyes can drop straight down for
    direct juxtaposition between commit episodes and solar/geomagnetic
    context.
    """
    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    c = commits.sort_index().astype(float)
    cols = list(metrics_frame.columns)
    if not cols:
        raise ValueError("stacked_panel: no metrics in frame")
    common = c.index
    for col in cols:
        common = common.intersection(metrics_frame[col].index)
    if common.empty:
        raise ValueError("stacked_panel: no common index")
    c = c.reindex(common)
    n = 1 + len(cols)
    fig, axes = plt.subplots(n, 1, sharex=True, figsize=(13.5, 1.4 * n + 1.0))
    if n == 1:
        axes = [axes]
    ax0 = axes[0]
    raw = c.fillna(0.0)
    ma = raw.rolling(ma_window, min_periods=1).mean()
    ax0.plot(
        raw.index, raw.to_numpy(), color=s.palette[0],
        linewidth=s.line_width * 0.4, alpha=0.4, label="commits / day",
    )
    ax0.plot(
        ma.index, ma.to_numpy(), color=s.palette[0],
        linewidth=s.line_width * 1.2, label=f"commits MA{ma_window}",
    )
    ax0.set_ylabel("commits")
    ax0.legend(loc="upper left", framealpha=0.9)
    palette = s.palette[1:] if len(s.palette) > 1 else s.palette
    for i, col in enumerate(cols):
        a = axes[i + 1]
        g = metrics_frame[col].reindex(common).astype(float)
        color = palette[i % len(palette)]
        a.plot(g.index, g.to_numpy(), color=color, linewidth=s.line_width, alpha=0.95)
        a.set_ylabel(col)
        a.axhline(0.0, color=s.grid_color, linewidth=0.6)
        try:
            r, lo, hi, p, nn = pearson_with_ci(c, g)
            a.text(
                0.005, 0.92,
                f"r vs commits = {r:+.2f}  [{lo:+.2f}, {hi:+.2f}]   n={int(nn)}",
                transform=a.transAxes, fontsize=s.base_size * 0.78,
                color=s.axis_fg, alpha=0.9,
            )
        except Exception:  # noqa: BLE001
            pass
    axes[-1].set_xlabel("date")
    fig.suptitle(
        "Commits and metrics on a shared timeline — direct juxtaposition",
        fontsize=s.base_size * 1.1, y=0.995,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.985))
    metadata_footer(
        fig, parts=_meta(int(c.size), period=period,
                         extras=[f"MA={ma_window}d", f"panels={n}"]),
        style=s,
    )
    _save(fig, out, s)


def save_ma_correlation_curve(
    commits: pd.Series,
    metric: pd.Series,
    *,
    out: Path,
    metric_label: str,
    windows: list[int] | None = None,
    period: Period = None,
    style: PlotStyle | None = None,
) -> list[dict[str, float | int | str | None]]:
    """
    Correlation of ``MA_w(commits)`` vs ``MA_w(metric)`` as a function of the
    smoothing window ``w``. Both Pearson r (Fisher-z 95 % CI) and Spearman ρ
    (Bonett–Wright 95 % CI) are drawn so the reader can compare linear vs
    rank-based behaviour as the daily noise is averaged out.

    The function also returns the underlying rows for reuse (e.g. emitting
    them into ``report.json``) so the caller does not have to recompute.
    """
    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if windows is None:
        windows = [1, 3, 7, 14, 30, 60, 90, 180, 365]
    rows_p = moving_average_correlation_curve(
        commits, metric, windows=windows, method="pearson",
    )
    rows_s = moving_average_correlation_curve(
        commits, metric, windows=windows, method="spearman",
    )
    fig, ax = plt.subplots(figsize=(11.0, 4.4))
    ax.axhline(0.0, color=s.grid_color, linewidth=0.8)
    xs = [int(r["window"]) for r in rows_p]

    def _yline(rows: list[dict[str, float | int | str | None]]) -> tuple[
        list[float], list[float], list[float]
    ]:
        ys = [float(r["r"]) for r in rows]
        lo = [float(r["lo"]) for r in rows]
        hi = [float(r["hi"]) for r in rows]
        return ys, lo, hi

    yp, lop, hip = _yline(rows_p)
    ys_, los_, his_ = _yline(rows_s)

    color_p = s.palette[0]
    color_s = s.palette[2 % len(s.palette)]
    ax.fill_between(
        xs, lop, hip, color=color_p, alpha=0.18, linewidth=0,
        label="Pearson 95 % CI (Fisher z)",
    )
    ax.plot(
        xs, yp, color=color_p, linewidth=s.line_width, marker="o",
        label="Pearson r",
    )
    ax.fill_between(
        xs, los_, his_, color=color_s, alpha=0.18, linewidth=0,
        label="Spearman 95 % CI (Bonett–Wright)",
    )
    ax.plot(
        xs, ys_, color=color_s, linewidth=s.line_width, marker="s",
        linestyle="--", label="Spearman ρ",
    )

    for x, row in zip(xs, rows_p, strict=True):
        stars = _significance_stars(row.get("p"))
        if stars and stars != "ⁿˢ":
            ax.text(
                x, float(row["r"]),
                f" {stars}",
                fontsize=s.base_size * 0.85, color=color_p,
                va="bottom", ha="left",
            )

    ax.set_xscale("log")
    ax.set_xticks(xs)
    ax.set_xticklabels([str(w) for w in xs])
    ax.set_xlabel("moving-average window  w  (days, log scale)")
    ax.set_ylabel("correlation of MAₐ(commits) vs MAₐ(metric)")
    ax.set_ylim(-1.0, 1.0)
    ax.grid(True, which="both", color=s.grid_color, linewidth=0.5, alpha=0.35)
    ax.legend(loc="lower right", framealpha=0.9, fontsize=s.base_size * 0.85)

    n_top = int(rows_p[0]["n"]) if rows_p else 0
    best = max(rows_p, key=lambda r: abs(float(r["r"]))) if rows_p else None
    best_label = (
        f"max |r|={abs(float(best['r'])):.2f} @ MA{int(best['window'])}d "
        f"({_p_label(best.get('p'))})"
        if best else "no data"
    )
    ax.set_title(
        f"Moving-average correlations: commits vs {metric_label}  ·  {best_label}",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    metadata_footer(
        fig,
        parts=_meta(
            n_top, period=period,
            extras=[
                f"windows={','.join(str(w) for w in xs)}d",
                "stars: *** p<.001 ** p<.01 * p<.05",
            ],
        ),
        style=s,
    )
    _save(fig, out, s)
    rows: list[dict[str, float | int | str | None]] = []
    for rp, rs in zip(rows_p, rows_s, strict=True):
        rows.append({
            "window": rp["window"],
            "n": rp["n"],
            "n_eff": rp["n_eff"],
            "pearson_r": rp["r"],
            "pearson_lo": rp["lo"],
            "pearson_hi": rp["hi"],
            "pearson_p": rp["p"],
            "spearman_rho": rs["r"],
            "spearman_lo": rs["lo"],
            "spearman_hi": rs["hi"],
            "spearman_p": rs["p"],
        })
    return rows


def save_dow_response(
    commits: pd.Series,
    metric: pd.Series | None = None,
    *,
    out: Path,
    metric_label: str | None = None,
    period: Period = None,
    style: PlotStyle | None = None,
) -> dict[str, list[float]]:
    """
    Day-of-week response: bar chart of mean commits per weekday plus, when a
    ``metric`` is supplied, a heatmap of mean commits over (DOW × metric
    tercile). This makes the dominant weekly seasonality of commits visible
    next to any conditional dependence on the geophysical metric.

    Returns a small dict ``{"dow_means": [Mon..Sun], "weekday": .., "weekend": ..}``
    so callers can persist the same numbers in ``report.json``.
    """
    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    c = commits.dropna().astype(float)
    c.index = pd.to_datetime(c.index)
    dow = c.index.dayofweek
    means = [float(c[dow == k].mean()) if int((dow == k).sum()) else float("nan")
             for k in range(7)]
    counts = [int((dow == k).sum()) for k in range(7)]
    weekday = float(c[dow < 5].mean()) if int((dow < 5).sum()) else float("nan")
    weekend = float(c[dow >= 5].mean()) if int((dow >= 5).sum()) else float("nan")
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    if metric is None:
        fig, ax = plt.subplots(figsize=(10.0, 4.0))
        bars = ax.bar(
            labels, means, color=s.palette[0], edgecolor=s.axis_fg, linewidth=0.6,
        )
        for b, v, n in zip(bars, means, counts, strict=True):
            ax.text(
                b.get_x() + b.get_width() / 2, b.get_height(),
                f"{v:.2f}\nn={n}",
                ha="center", va="bottom", fontsize=s.base_size * 0.78, color=s.axis_fg,
            )
        ax.axhline(weekday, color=s.palette[1 % len(s.palette)],
                   linewidth=1.0, linestyle="--", label=f"weekday mean={weekday:.2f}")
        ax.axhline(weekend, color=s.palette[2 % len(s.palette)],
                   linewidth=1.0, linestyle=":", label=f"weekend mean={weekend:.2f}")
        ax.set_ylabel("mean commits / day")
        ax.legend(loc="upper right", framealpha=0.9)
        ax.set_title("Commits — day-of-week mean response")
    else:
        m = metric.dropna().astype(float)
        df = pd.concat({"c": c, "g": m}, axis=1).dropna()
        if len(df) < 7:
            raise ValueError("dow_response: not enough overlap with metric")
        q1, q2 = df["g"].quantile([1 / 3, 2 / 3]).to_list()
        bins = pd.cut(
            df["g"], bins=[-np.inf, q1, q2, np.inf],
            labels=["low", "mid", "high"], include_lowest=True,
        )
        df["bin"] = bins
        df["dow"] = df.index.dayofweek
        grid = df.groupby(["dow", "bin"], observed=True)["c"].mean().unstack("bin")
        grid = grid.reindex(index=range(7), columns=["low", "mid", "high"])
        fig, (ax0, ax1) = plt.subplots(
            1, 2, figsize=(14.0, 4.4),
            gridspec_kw={"width_ratios": [1.0, 1.4]},
        )
        bars = ax0.bar(
            labels, means, color=s.palette[0], edgecolor=s.axis_fg, linewidth=0.6,
        )
        for b, v in zip(bars, means, strict=True):
            ax0.text(
                b.get_x() + b.get_width() / 2, b.get_height(),
                f"{v:.2f}",
                ha="center", va="bottom", fontsize=s.base_size * 0.8, color=s.axis_fg,
            )
        ax0.set_ylabel("mean commits / day")
        ax0.set_title("DOW marginal mean")

        z = grid.to_numpy(dtype=float)
        im = ax1.imshow(z, aspect="auto", cmap="magma", origin="upper")
        ax1.set_xticks(range(3))
        ax1.set_xticklabels([f"low\n≤{q1:.2g}", f"mid\n({q1:.2g},{q2:.2g}]",
                             f"high\n>{q2:.2g}"])
        ax1.set_yticks(range(7))
        ax1.set_yticklabels(labels)
        ax1.set_xlabel(f"{metric_label} tercile")
        ax1.set_title(f"Mean commits — DOW × {metric_label} tercile")
        for i in range(z.shape[0]):
            for j in range(z.shape[1]):
                v = z[i, j]
                if np.isfinite(v):
                    ax1.text(
                        j, i, f"{v:.2f}",
                        ha="center", va="center",
                        color=("white" if v < np.nanmean(z) else "black"),
                        fontsize=s.base_size * 0.85,
                    )
        fig.colorbar(im, ax=ax1, fraction=0.04, pad=0.02, label="mean commits")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    extras = [f"weekday/weekend ratio={weekday/weekend:.2f}"
              if (weekend and weekend > 0) else "weekend=0"]
    metadata_footer(
        fig, parts=_meta(int(c.size), period=period, extras=extras), style=s,
    )
    _save(fig, out, s)
    return {
        "dow_means": means,
        "dow_counts": [float(x) for x in counts],
        "weekday_mean": weekday,
        "weekend_mean": weekend,
    }


def save_mi_lag_curve(
    commits: pd.Series,
    metric: pd.Series,
    *,
    out: Path,
    metric_label: str,
    max_lag: int = 30,
    method: str = "binned",
    bins: int | str = "fd",
    k: int = 5,
    period: Period = None,
    style: PlotStyle | None = None,
) -> dict[str, object]:
    """
    Mutual-information vs integer day-lag, the nonlinear analogue to the lag
    correlation curve. Two curves are drawn — the chosen primary estimator
    (``binned`` or ``ksg``) and a faint reference of the other so the reader
    can sanity-check the shape.

    The peak lag and its MI value are annotated. Returns the underlying
    arrays so callers can persist them in ``report.json``.

    Parameters
    ----------
    method
        Primary estimator: ``"binned"`` (Freedman–Diaconis bins, Miller–Madow
        corrected) or ``"ksg"`` (Kraskov k-NN, k=5).
    """
    from sunspot.stats.information import mutual_information_lag_curve

    s = _push_style(style)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    primary = mutual_information_lag_curve(
        commits, metric, max_lag=max_lag, method=method, bins=bins, k=k,
    )
    other = "ksg" if method == "binned" else "binned"
    try:
        secondary = mutual_information_lag_curve(
            commits, metric, max_lag=max_lag, method=other, bins=bins, k=k,
        )
    except Exception:  # pragma: no cover — secondary is decorative only
        secondary = None

    fig, ax = plt.subplots(figsize=(8.6, 4.2))
    ax.axhline(0.0, color=s.grid_color, linewidth=0.6)
    color_p = s.palette[5 % len(s.palette)]
    ax.plot(
        primary.lags, primary.values, color=color_p, linewidth=s.line_width,
        marker="o", markersize=3.2, label=f"I({method})  · nats",
    )
    if secondary is not None and np.any(np.isfinite(secondary.values)):
        ax.plot(
            secondary.lags, secondary.values, color=s.axis_fg,
            linewidth=s.line_width * 0.6, alpha=0.45, linestyle="--",
            label=f"I({other})  · reference",
        )
    if np.isfinite(primary.best_value):
        ax.axvline(
            primary.best_lag, color=s.palette[1 % len(s.palette)],
            linewidth=s.line_width, linestyle=":",
            label=f"peak I={primary.best_value:.3f} nat @ lag={primary.best_lag}d",
        )
    ax.set_xlabel("lag (days); positive ⇒ commits lead")
    ax.set_ylabel("mutual information  I(commits, " + metric_label + ")  [nats]")
    ax.set_title(
        f"MI vs lag · commits ↔ {metric_label}  ·  primary={method}",
    )
    ax.legend(loc="upper right", framealpha=0.92)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    n_top = int(np.max(primary.n_per_lag)) if primary.n_per_lag.size else 0
    detail = (
        f"bins={primary.bins_or_k}" if method == "binned"
        else f"k={primary.bins_or_k}"
    )
    extras = [f"|lag|≤{max_lag}d", f"estimator={method}/{detail}"]
    metadata_footer(fig, parts=_meta(n_top, period=period, extras=extras), style=s)
    _save(fig, out, s)
    return {
        "method": primary.method,
        "bins_or_k": primary.bins_or_k,
        "lags": [int(x) for x in primary.lags],
        "values_nats": [float(v) if np.isfinite(v) else None for v in primary.values],
        "n_per_lag": [int(x) for x in primary.n_per_lag],
        "best_lag": int(primary.best_lag),
        "best_value_nats": (
            float(primary.best_value) if np.isfinite(primary.best_value) else None
        ),
    }
