"""Text and JSON-shaped report fragments for correlate output."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from sunspot.stats.correlation import CCFResult, LagResult, fdr_on_pvalues
from sunspot.stats.spectral import band_power

from ._constants import SPECTRAL_BANDS_DAYS


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

