"""Per-repository associations between commit activity and geophysical metrics."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from sunspot.stats.correlation import fdr_on_pvalues

_LOG = logging.getLogger(__name__)


def per_repo_associations(
    commits_by_repo: dict[str, pd.Series],
    metrics_frame: pd.DataFrame,
    *,
    method: str = "spearman",
    min_active_days: int = 10,
    fdr_q: float = 0.1,
) -> pd.DataFrame:
    """
    For every (repo, metric) pair, compute the rank or linear correlation over
    aligned UTC days. Returns a long-form DataFrame with columns:

    ``repo, metric, n, total_commits, rho, p, q_significant``

    ``q_significant`` is the BH-FDR flag at level ``fdr_q``, computed independently
    per metric across repos.
    """
    rows: list[dict[str, object]] = []
    metric_cols = list(metrics_frame.columns)
    for repo, s in commits_by_repo.items():
        if not repo or repo == "__all__":
            continue
        c = s.sort_index().astype(float)
        active = int((c > 0).sum())
        total = float(c.sum())
        if active < min_active_days:
            continue
        for m in metric_cols:
            g = metrics_frame[m].astype(float)
            common = c.index.intersection(g.index)
            cc = c.reindex(common).to_numpy(dtype=float)
            gg = g.reindex(common).to_numpy(dtype=float)
            mask = np.isfinite(cc) & np.isfinite(gg)
            cc = cc[mask]
            gg = gg[mask]
            if cc.size < 4 or float(np.std(cc)) == 0.0 or float(np.std(gg)) == 0.0:
                rows.append(
                    {
                        "repo": repo,
                        "metric": m,
                        "n": int(cc.size),
                        "total_commits": total,
                        "rho": float("nan"),
                        "p": float("nan"),
                    }
                )
                continue
            if method == "spearman":
                r = scipy_stats.spearmanr(cc, gg)
            elif method == "kendall":
                r = scipy_stats.kendalltau(cc, gg)
            else:
                r = scipy_stats.pearsonr(cc, gg)
            rows.append(
                {
                    "repo": repo,
                    "metric": m,
                    "n": int(cc.size),
                    "total_commits": total,
                    "rho": float(r.statistic if hasattr(r, "statistic") else r[0]),
                    "p": float(r.pvalue if hasattr(r, "pvalue") else r[1]),
                }
            )
    df = pd.DataFrame(rows)
    if df.empty:
        df["q_significant"] = pd.Series(dtype=bool)
        return df
    flags = np.zeros(len(df), dtype=bool)
    for m in metric_cols:
        sel = df["metric"].to_numpy() == m
        if not sel.any():
            continue
        ps = df.loc[sel, "p"].to_numpy(dtype=float)
        flags[sel] = fdr_on_pvalues(ps, q=fdr_q)
    df["q_significant"] = flags
    df = df.sort_values(["metric", "rho"], ascending=[True, False]).reset_index(drop=True)
    _LOG.debug("per-repo associations: %s rows over %s metrics", len(df), len(metric_cols))
    return df
