"""
Plaintext (CSV) sidecars for every statistical block in ``report.json``.

The pipeline already writes a structured ``statistics/report.json`` and a
human-readable ``analysis/summary.txt``. This module additionally emits one
*tidy* CSV per analysis under ``analysis/tables/`` so every number that the
`sunspot` pipeline computes can be loaded into a spreadsheet, ``awk``-ed, or
diffed without having to traverse a JSON tree.

Each writer is **defensive**: missing fields produce empty / partial files
rather than failing the run. The full set of files written is returned by
:func:`write_analysis_tables` so the caller can log or persist them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

# Long-form columns reused across files.
_ASSOC_COLS = (
    "metric", "kind", "n", "value",
    "ci95_lo", "ci95_hi", "p", "stars",
)
_LAG_COLS = ("metric", "lag_days", "rho", "p", "fdr_significant")
_MA_COLS = (
    "metric", "window_days", "n", "n_eff",
    "pearson_r", "pearson_lo", "pearson_hi", "pearson_p",
    "spearman_rho", "spearman_lo", "spearman_hi", "spearman_p",
)


def _stars(p: float | None) -> str:
    if p is None:
        return ""
    try:
        pf = float(p)
    except (TypeError, ValueError):
        return ""
    if pf != pf:  # NaN
        return ""
    if pf < 0.001:
        return "***"
    if pf < 0.01:
        return "**"
    if pf < 0.05:
        return "*"
    if pf < 0.10:
        return "."
    return ""


def _df_to_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def _write_associations(report: dict[str, Any], out_dir: Path) -> Path | None:
    """
    Long-form per-metric associations: Pearson / Spearman / Kendall, with
    Fisher-z (Pearson) and Bonett–Wright (Spearman) 95 % CIs where available.
    """
    rows: list[dict[str, Any]] = []
    for m, blk in (report.get("metrics") or {}).items():
        if not isinstance(blk, dict) or "error" in blk:
            continue
        n = blk.get("n_aligned")
        for kind in ("pearson", "spearman", "kendall"):
            asso = next(
                (a for a in (blk.get("associations") or []) if a.get("kind") == kind),
                None,
            )
            if not asso:
                continue
            value = asso.get("value")
            p = asso.get("p")
            lo = hi = None
            if kind == "pearson":
                ci = blk.get("pearson_ci95") or {}
                value = ci.get("r", value)
                lo, hi, p = ci.get("lo"), ci.get("hi"), ci.get("p", p)
            elif kind == "spearman":
                ci = blk.get("spearman_ci95") or {}
                value = ci.get("rho", value)
                lo, hi, p = ci.get("lo"), ci.get("hi"), ci.get("p", p)
            rows.append({
                "metric": m, "kind": kind, "n": n, "value": value,
                "ci95_lo": lo, "ci95_hi": hi, "p": p, "stars": _stars(p),
            })
    if not rows:
        return None
    p = out_dir / "associations.csv"
    _df_to_csv(pd.DataFrame(rows, columns=list(_ASSOC_COLS)), p)
    return p


def _write_lag_profile(
    report: dict[str, Any],
    out_dir: Path,
    lag_results: dict[str, Any] | None,
) -> Path | None:
    """One row per (metric, lag): rho, p, FDR-significance flag."""
    rows: list[dict[str, Any]] = []
    for m, blk in (report.get("metrics") or {}).items():
        if not isinstance(blk, dict):
            continue
        for row in (blk.get("lag_profile") or []):
            rows.append({
                "metric": m,
                "lag_days": row.get("lag_days"),
                "rho": row.get("rho"),
                "p": row.get("p"),
                "fdr_significant": bool(row.get("fdr_significant")),
            })
    if not rows and lag_results:
        for m, res in lag_results.items():
            lags = list(getattr(res, "lags", []) or [])
            vals = list(getattr(res, "values", []) or [])
            ps = list(getattr(res, "p_values", []) or [])
            fdr_flags = (
                (report.get("metrics", {}).get(m) or {}).get("lag_fdr_significant_count")
            )
            # Legacy fallback for callers that pass in-memory lag results but
            # not the persisted per-lag report rows.
            for k, lag in enumerate(lags):
                v = vals[k] if k < len(vals) else None
                pv = ps[k] if k < len(ps) else None
                rows.append({
                    "metric": m,
                    "lag_days": int(lag),
                    "rho": float(v) if v is not None else None,
                    "p": float(pv) if pv is not None else None,
                    "fdr_significant": False,
                    "fdr_significant_count": fdr_flags,
                })
    if not rows:
        return None
    p = out_dir / "lag_profile.csv"
    df = pd.DataFrame(rows)
    for col in _LAG_COLS:
        if col not in df.columns:
            df[col] = None
    _df_to_csv(df, p)
    return p


def _write_ccf_profile(
    report: dict[str, Any],
    out_dir: Path,
    ccf_results: dict[str, Any] | None,
) -> Path | None:
    """One row per (metric, lag) cross-correlation value."""
    rows: list[dict[str, Any]] = []
    for m, blk in (report.get("metrics") or {}).items():
        if not isinstance(blk, dict):
            continue
        for row in (blk.get("ccf_profile") or []):
            rows.append({
                "metric": m,
                "lag_days": row.get("lag_days"),
                "ccf": row.get("ccf"),
                "bartlett_ci95": row.get("bartlett_ci95"),
                "crosses_bartlett_ci95": bool(row.get("crosses_bartlett_ci95")),
                "method": row.get("method"),
                "n_eff": row.get("n_eff"),
            })
    if not rows and ccf_results:
        for m, res in ccf_results.items():
            lags = list(getattr(res, "lags", []) or [])
            vals = list(getattr(res, "values", []) or [])
            band = float(getattr(res, "bartlett_ci", float("nan")))
            for k, lag in enumerate(lags):
                v = vals[k] if k < len(vals) else None
                fv = float(v) if v is not None else None
                rows.append({
                    "metric": m,
                    "lag_days": int(lag),
                    "ccf": fv,
                    "bartlett_ci95": band,
                    "crosses_bartlett_ci95": bool(fv is not None and abs(fv) > band),
                    "method": getattr(res, "method", None),
                    "n_eff": int(getattr(res, "n", 0) or 0),
                })
    if not rows:
        return None
    p = out_dir / "ccf_profile.csv"
    _df_to_csv(pd.DataFrame(rows), p)
    return p


def _write_spectral_band_power(report: dict[str, Any], out_dir: Path) -> Path | None:
    """One row per (series, named period band) with LS power fraction."""
    rows: list[dict[str, Any]] = []
    for row in (report.get("commits_spectral_band_power") or []):
        rows.append({"series": "commits", **row})
    for m, blk in (report.get("metrics") or {}).items():
        if not isinstance(blk, dict):
            continue
        for row in (blk.get("spectral_band_power") or []):
            rows.append({"series": m, **row})
    if not rows:
        return None
    p = out_dir / "spectral_band_power.csv"
    _df_to_csv(pd.DataFrame(rows), p)
    return p


def _write_ma_correlations(report: dict[str, Any], out_dir: Path) -> Path | None:
    """One row per (metric, window): Pearson + Spearman with CIs and p-values."""
    rows: list[dict[str, Any]] = []
    for m, blk in (report.get("metrics") or {}).items():
        if not isinstance(blk, dict):
            continue
        for r in (blk.get("ma_correlations") or []):
            rows.append({
                "metric": m,
                "window_days": int(r.get("window") or 0),
                "n": int(r.get("n") or 0),
                "n_eff": int(r.get("n_eff") or 0),
                "pearson_r": r.get("pearson_r"),
                "pearson_lo": r.get("pearson_lo"),
                "pearson_hi": r.get("pearson_hi"),
                "pearson_p": r.get("pearson_p"),
                "spearman_rho": r.get("spearman_rho"),
                "spearman_lo": r.get("spearman_lo"),
                "spearman_hi": r.get("spearman_hi"),
                "spearman_p": r.get("spearman_p"),
            })
    if not rows:
        return None
    p = out_dir / "ma_correlations.csv"
    _df_to_csv(pd.DataFrame(rows, columns=list(_MA_COLS)), p)
    return p


def _write_mi_lag(report: dict[str, Any], out_dir: Path) -> Path | None:
    """One row per (metric, lag) MI value, in nats."""
    rows: list[dict[str, Any]] = []
    for m, blk in (report.get("metrics") or {}).items():
        if not isinstance(blk, dict):
            continue
        ml = blk.get("mi_lag") or {}
        lags = ml.get("lags") or []
        vals = ml.get("values_nats") or []
        ns = ml.get("n_per_lag") or []
        for k, lag in enumerate(lags):
            rows.append({
                "metric": m,
                "lag_days": int(lag),
                "mi_nats": vals[k] if k < len(vals) else None,
                "n": int(ns[k]) if k < len(ns) and ns[k] is not None else None,
                "method": ml.get("method"),
                "bins_or_k": ml.get("bins_or_k"),
            })
    if not rows:
        return None
    p = out_dir / "mi_lag.csv"
    _df_to_csv(pd.DataFrame(rows), p)
    return p


def _write_mutual_information(report: dict[str, Any], out_dir: Path) -> Path | None:
    """One row per metric MI summary (binned-MM + KSG + normalised)."""
    rows: list[dict[str, Any]] = []
    for m, blk in (report.get("metrics") or {}).items():
        if not isinstance(blk, dict):
            continue
        mi = blk.get("mutual_information") or {}
        if not mi:
            continue
        rows.append({
            "metric": m,
            "n": mi.get("n"),
            "binned_nats": mi.get("binned_nats"),
            "binned_normalised": mi.get("binned_normalised"),
            "binned_bins": mi.get("binned_bins"),
            "ksg_nats": mi.get("ksg_nats"),
        })
    if not rows:
        return None
    p = out_dir / "mutual_information.csv"
    _df_to_csv(pd.DataFrame(rows), p)
    return p


def _write_regression_ols(report: dict[str, Any], out_dir: Path) -> Path | None:
    """One row per metric OLS diagnostics (R², DW, residual normality)."""
    rows: list[dict[str, Any]] = []
    for m, blk in (report.get("metrics") or {}).items():
        if not isinstance(blk, dict):
            continue
        rd = blk.get("regression_ols") or {}
        if not rd:
            continue
        rows.append({
            "metric": m,
            "n": rd.get("n"),
            "b0": rd.get("b0"),
            "b1": rd.get("b1"),
            "r2": rd.get("r2"),
            "sigma2": rd.get("sigma2"),
            "pearson_r": rd.get("pearson_r"),
            "pearson_lo": rd.get("pearson_lo"),
            "pearson_hi": rd.get("pearson_hi"),
            "pearson_p": rd.get("pearson_p"),
            "durbin_watson": rd.get("durbin_watson"),
            "normality_stat": rd.get("normality_stat"),
            "normality_p": rd.get("normality_p"),
        })
    if not rows:
        return None
    p = out_dir / "regression_ols.csv"
    _df_to_csv(pd.DataFrame(rows), p)
    return p


def _write_partial_correlation(report: dict[str, Any], out_dir: Path) -> Path | None:
    """One row per metric for AR(1)-controlled Pearson + Spearman partials."""
    rows: list[dict[str, Any]] = []
    for m, blk in (report.get("metrics") or {}).items():
        if not isinstance(blk, dict):
            continue
        pc = blk.get("partial_correlation_ar1") or {}
        if not pc:
            continue
        pe = pc.get("pearson") or {}
        sp = pc.get("spearman") or {}
        rows.append({
            "metric": m,
            "controls": ",".join(pc.get("controls", [])),
            "n": pe.get("n"),
            "pearson_r": pe.get("r"),
            "pearson_p": pe.get("p"),
            "spearman_rho": sp.get("rho"),
            "spearman_p": sp.get("p"),
        })
    if not rows:
        return None
    p = out_dir / "partial_correlation_ar1.csv"
    _df_to_csv(pd.DataFrame(rows), p)
    return p


def _write_cross_metric_matrix(report: dict[str, Any], out_dir: Path) -> Path | None:
    """Square pairwise Spearman matrix (the same data as the heatmap PNG)."""
    cm = report.get("cross_metric_correlation") or {}
    if not cm:
        return None
    cols = list(cm.keys())
    df = pd.DataFrame(
        [[cm.get(a, {}).get(b) for b in cols] for a in cols],
        index=cols, columns=cols,
    )
    df.index.name = "metric"
    p = out_dir / "cross_metric_spearman.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p)
    return p


def _write_periodogram_top(report: dict[str, Any], out_dir: Path) -> Path | None:
    """Top-5 Lomb–Scargle peaks for the commit series and each metric."""
    rows: list[dict[str, Any]] = []
    commits_top = report.get("commits_periodogram_top5") or []
    for k, r in enumerate(commits_top, start=1):
        rows.append({
            "series": "commits",
            "rank": k,
            "period_days": r.get("period_days"),
            "power": r.get("power"),
        })
    for m, blk in (report.get("metrics") or {}).items():
        if not isinstance(blk, dict):
            continue
        for k, r in enumerate(blk.get("periodogram_top5") or [], start=1):
            rows.append({
                "series": m,
                "rank": k,
                "period_days": r.get("period_days"),
                "power": r.get("power"),
            })
    if not rows:
        return None
    p = out_dir / "periodogram_top.csv"
    _df_to_csv(pd.DataFrame(rows), p)
    return p


def _write_commits_daily_summary(report: dict[str, Any], out_dir: Path) -> Path | None:
    """Flatten ``commits_summary`` into a single-row CSV (lists kept as-is)."""
    cs = report.get("commits_summary") or {}
    if not cs:
        return None
    flat = {k: v for k, v in cs.items() if not isinstance(v, list | dict)}
    p = out_dir / "commits_daily_summary.csv"
    _df_to_csv(pd.DataFrame([flat]), p)
    return p


def _write_per_repo_topk(report: dict[str, Any], out_dir: Path) -> Path | None:
    """Top-K per-repo Spearman pairs (FDR-flagged)."""
    pr = report.get("per_repo_topk") or []
    if not pr:
        return None
    p = out_dir / "per_repo_topk.csv"
    _df_to_csv(pd.DataFrame(pr), p)
    return p


def _write_multi_user_topk(report: dict[str, Any], out_dir: Path) -> Path | None:
    """Top-K (user, metric) Spearman pairs (FDR-flagged) — multi-user runs only."""
    mu = report.get("multi_user_topk") or []
    if not mu:
        return None
    p = out_dir / "multi_user_topk.csv"
    _df_to_csv(pd.DataFrame(mu), p)
    return p


def _write_cohort_user_summary(report: dict[str, Any], out_dir: Path) -> Path | None:
    """One row per login for cohort activity summaries."""
    rows = report.get("cohort_user_summary") or []
    if not rows:
        return None
    p = out_dir / "cohort_user_summary.csv"
    _df_to_csv(pd.DataFrame(rows), p)
    return p


_README = """\
# `analysis/tables/`

Plaintext CSV sidecars for every numeric block in
`statistics/report.json`. One file per analysis; long form unless the
underlying data is naturally square. Generated by
[`sunspot.tables.write_analysis_tables`](../../../src/sunspot/tables.py).

## File index

- **`associations.csv`** — one row per `(metric, kind)` where `kind` is
  `pearson | spearman | kendall`. Columns: `metric, kind, n, value,
  ci95_lo, ci95_hi, p, stars`. Pearson / Spearman CIs come from the
  Fisher-z and Bonett-Wright transforms respectively.
- **`lag_profile.csv`** — one row per `(metric, lag in
  [-lag_max, +lag_max])`. Columns: `metric, lag_days, rho, p,
  fdr_significant` (BH-FDR over lags, q=0.10).
- **`ccf_profile.csv`** — one row per `(metric, lag)` cross-correlation.
  Columns: `metric, lag_days, ccf, bartlett_ci95,
  crosses_bartlett_ci95, method, n_eff`.
- **`ma_correlations.csv`** — one row per `(metric, MA window)`.
  Columns: `metric, window_days, n, n_eff, pearson_r/lo/hi/p,
  spearman_rho/lo/hi/p`.
- **`mi_lag.csv`** — one row per `(metric, lag)` mutual-information
  point. Columns: `metric, lag_days, mi_nats, n, method, bins_or_k`.
- **`mutual_information.csv`** — one row per metric. Columns:
  `metric, n, binned_nats, binned_normalised, binned_bins, ksg_nats`.
- **`regression_ols.csv`** — one row per metric. Columns:
  `metric, n, b0, b1, r2, sigma2, pearson_*, durbin_watson,
  normality_stat, normality_p`.
- **`partial_correlation_ar1.csv`** — one row per metric, AR(1)-
  controlled partials. Columns: `metric, controls, n, pearson_r,
  pearson_p, spearman_rho, spearman_p`.
- **`cross_metric_spearman.csv`** — square pairwise Spearman matrix
  across metrics + commits, indexed by metric.
- **`periodogram_top.csv`** — top-5 Lomb-Scargle peaks per series.
  Columns: `series, rank, period_days, power`.
- **`spectral_band_power.csv`** — named Lomb-Scargle period-band power
  fractions. Columns: `series, band, min_period_days, max_period_days,
  power_fraction`.
- **`commits_daily_summary.csv`** — one-row commit activity stats; a
  flattening of `report["commits_summary"]`.
- **`per_repo_topk.csv`** — top-K |rho| repo x metric pairs, FDR-flagged.
- **`multi_user_topk.csv`** — top-K |rho| user x metric pairs (only
  written when `--compare-users` is set).
- **`cohort_user_summary.csv`** — one row per cohort login: total commits,
  active days, active fraction, mean/day, mean/active-day, and max day.

All values mirror those in `statistics/report.json` exactly; the CSV
form exists to make `awk`, `pandas`, and spreadsheet workflows trivial.
"""


def write_analysis_tables(
    report: dict[str, Any],
    analysis_dir: Path,
    *,
    lag_results: dict[str, Any] | None = None,
    ccf_results: dict[str, Any] | None = None,
) -> list[Path]:
    """
    Emit one CSV per analysis under ``analysis_dir/tables/``.

    Parameters
    ----------
    report
        The dict written to ``statistics/report.json``.
    analysis_dir
        The run's ``analysis/`` directory; ``tables/`` is created inside it.
    lag_results, ccf_results
        Optional legacy per-metric ``LagResult`` / ``CCFResult`` containers.
        Current reports persist lag/CCF profile rows directly; these arguments
        remain as a fallback for older callers.

    Returns
    -------
    list[Path]
        Files actually written, in deterministic order.
    """
    tables_dir = Path(analysis_dir) / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    (tables_dir / "README.md").write_text(_README, encoding="utf-8")

    written: list[Path] = []
    writers = (
        _write_associations,
        lambda r, d: _write_lag_profile(r, d, lag_results),
        lambda r, d: _write_ccf_profile(r, d, ccf_results),
        _write_ma_correlations,
        _write_mi_lag,
        _write_mutual_information,
        _write_regression_ols,
        _write_partial_correlation,
        _write_cross_metric_matrix,
        _write_periodogram_top,
        _write_spectral_band_power,
        _write_commits_daily_summary,
        _write_per_repo_topk,
        _write_multi_user_topk,
        _write_cohort_user_summary,
    )
    for w in writers:
        try:
            p = w(report, tables_dir)
        except (KeyError, ValueError, TypeError):
            p = None
        if p is not None:
            written.append(p)
    return written
