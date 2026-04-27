"""
Cross-user statistics for comparing multiple GitHub commit histories against
geophysical metrics, and against each other.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from sunspot.stats.correlation import fdr_on_pvalues

_LOG = logging.getLogger(__name__)


def multi_user_associations(
    users_commits: dict[str, pd.Series],
    metrics_frame: pd.DataFrame,
    *,
    method: str = "spearman",
    fdr_q: float = 0.1,
    min_active_days: int = 30,
) -> pd.DataFrame:
    """
    For every (user, metric) pair, compute rank/linear correlation over aligned
    UTC days. Returns long-form DataFrame with columns:

    ``user, metric, n, total_commits, active_days, rho, p, q_significant``

    ``q_significant`` is the BH-FDR flag at level ``fdr_q``, computed
    independently per metric across users.
    """
    rows: list[dict[str, object]] = []
    metric_cols = list(metrics_frame.columns)
    for user, s in users_commits.items():
        c = s.sort_index().astype(float)
        active = int((c > 0).sum())
        total = float(c.sum())
        if active < min_active_days:
            _LOG.debug("multi-user: skip %s (active=%d < %d)", user, active, min_active_days)
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
                rows.append({
                    "user": user, "metric": m, "n": int(cc.size),
                    "total_commits": total, "active_days": active,
                    "rho": float("nan"), "p": float("nan"),
                })
                continue
            if method == "spearman":
                r = scipy_stats.spearmanr(cc, gg)
            elif method == "kendall":
                r = scipy_stats.kendalltau(cc, gg)
            else:
                r = scipy_stats.pearsonr(cc, gg)
            rows.append({
                "user": user, "metric": m, "n": int(cc.size),
                "total_commits": total, "active_days": active,
                "rho": float(r.statistic if hasattr(r, "statistic") else r[0]),
                "p": float(r.pvalue if hasattr(r, "pvalue") else r[1]),
            })
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
    return df


def multi_user_rank_matrix(
    users_commits: dict[str, pd.Series],
    *,
    method: str = "spearman",
    smoothing_window: int | None = 30,
) -> pd.DataFrame:
    """
    Pairwise correlation matrix between users' commit-activity time series.

    With ``smoothing_window`` (days) applied as a centered rolling mean before
    correlation, this surfaces *trend* alignment across users instead of raw
    daily-noise alignment.
    """
    if not users_commits:
        return pd.DataFrame()
    df = pd.concat(users_commits, axis=1).astype(float).fillna(0.0)
    if smoothing_window and smoothing_window > 1:
        min_p = max(2, smoothing_window // 4)
        df = df.rolling(smoothing_window, center=True, min_periods=min_p).mean()
    cols = list(df.columns)
    out = pd.DataFrame(index=cols, columns=cols, dtype=float)
    for i, a in enumerate(cols):
        for j, b in enumerate(cols):
            if j < i:
                out.loc[a, b] = out.loc[b, a]
                continue
            x = df[a].to_numpy(dtype=float)
            y = df[b].to_numpy(dtype=float)
            mask = np.isfinite(x) & np.isfinite(y)
            x, y = x[mask], y[mask]
            if x.size < 4 or float(np.std(x)) == 0.0 or float(np.std(y)) == 0.0:
                out.loc[a, b] = float("nan")
                continue
            if method == "spearman":
                v = float(scipy_stats.spearmanr(x, y).statistic)
            else:
                v = float(scipy_stats.pearsonr(x, y).statistic)
            out.loc[a, b] = v
    return out


def pca_users_weekly(
    users_commits: dict[str, pd.Series],
    *,
    n_components: int = 2,
) -> dict[str, object] | None:
    """
    Weekly-aggregate each user's daily series, z-score per user (row),
    then SVD. Rows are users, columns are week bins. Returns a dict with
    ``user_order``, ``pc_scores`` (user × component), and
    ``explained_variance_ratio`` (length n_components, sums to 1 for kept k).
    """
    if not users_commits or len(users_commits) < 2:
        return None
    df = pd.concat(users_commits, axis=1).sort_index().astype(float).fillna(0.0)
    w = (
        df.resample("W-MON", label="left", closed="left")
        .sum()
    )
    if w.shape[1] < 2 or w.shape[0] < 2:
        return None
    X = w.T.to_numpy(dtype=float)
    n_u, t = X.shape
    row_m = X.mean(axis=1, keepdims=True)
    row_s = X.std(axis=1, keepdims=True)
    row_s = np.where(row_s < 1e-12, 1.0, row_s)
    Xc = (X - row_m) / row_s
    k = int(min(n_components, n_u, t))
    if k < 1:
        return None
    uu, s, _v = np.linalg.svd(Xc, full_matrices=False)
    scores = uu[:, :k] * s[:k]
    tot = float((s**2).sum()) or 1.0
    evr = (s**2)[:k] / tot
    lab = [str(x) for x in w.columns.tolist()]
    return {
        "user_order": lab,
        "n_weeks": int(t),
        "pc_scores": {lab[i]: [float(scores[i, j]) for j in range(k)] for i in range(n_u)},
        "explained_variance_ratio": [float(evr[j]) for j in range(k)],
    }


def _cohort_weekly_sums(
    users_commits: dict[str, pd.Series],
) -> pd.DataFrame | None:
    """Resample to weekly (Mon) sums; one column per user, index = week start."""
    if not users_commits:
        return None
    df = pd.concat(users_commits, axis=1).sort_index().astype(float).fillna(0.0)
    w = df.resample("W-MON", label="left", closed="left").sum()
    if w.empty or w.shape[0] < 1:
        return None
    return w


def cohort_correlation_dendrogram_data(
    users_commits: dict[str, pd.Series],
    *,
    min_row_std: float = 0.0,
) -> dict[str, object] | None:
    """
    Build average-linkage clustering on *correlation* distance between user rows
    of weekly commit sums. Users with no variation across weeks (e.g. all zeros
    in the date window) are **excluded**; ``pdist(..., 'correlation')`` would
    otherwise yield non-finite distances.

    Returns ``None`` only if the weekly frame is missing or has fewer than two
    time bins. Otherwise a dict with:

    * ``"linkage"`` — tree matrix for :func:`scipy.cluster.hierarchy.dendrogram`, or
      ``None`` if fewer than two users have varying weekly series
    * ``"labels"`` — cluster leaf names (only users used in the tree), or empty
    * ``"excluded"`` — logins dropped from the distance (constant weekly vector)
    """
    if not users_commits or len(users_commits) < 1:
        return None
    w = _cohort_weekly_sums(users_commits)
    if w is None or w.shape[0] < 2:
        return None
    x = w.T.to_numpy(dtype=float)
    col_labels = [str(c) for c in w.columns.tolist()]
    row_std = x.std(axis=1, dtype=float, ddof=0)
    keep = row_std > float(min_row_std)
    if not np.all(keep):
        excluded = [col_labels[i] for i in range(len(col_labels)) if not keep[i]]
        _LOG.warning(
            "cohort clustering: excluding %d user(s) (no cross-week "
            "variation in weekly commit sums, unusable for correlation "
            "distance): %s",
            len(excluded),
            ", ".join(excluded),
        )
    else:
        excluded = []
    n_k = int(np.count_nonzero(keep))
    if n_k < 2:
        _LOG.warning(
            "cohort clustering: need ≥2 users with varying weekly series; have %d",
            n_k,
        )
        return {
            "linkage": None,
            "labels": [col_labels[i] for i, k in enumerate(keep) if k],
            "excluded": excluded,
        }
    x = x[keep, :]
    kept_labels = [col_labels[i] for i, k in enumerate(keep) if k]
    m = x.mean(axis=1, keepdims=True)
    s = x.std(axis=1, keepdims=True, ddof=0)
    s = np.where(s < 1e-12, 1.0, s)
    xc = (x - m) / s
    from scipy.cluster.hierarchy import linkage
    from scipy.spatial.distance import pdist

    d = pdist(xc, metric="correlation")
    if not np.all(np.isfinite(d)):
        _LOG.debug(
            "cohort clustering: sanitizing %d non-finite correlation distances",
            int(np.size(d) - np.isfinite(d).sum()),
        )
        d = np.where(np.isfinite(d), d, 1.0)
    z = linkage(d, method="average")
    return {"linkage": z, "labels": kept_labels, "excluded": excluded}


def cohort_dendrogram_leaves(
    users_commits: dict[str, pd.Series],
) -> tuple[list[str] | None, list[str]]:
    """
    Return (leaf order for hierarchical clustering, excluded logins) or
    (``None``, excluded) if no tree could be built.
    """
    data = cohort_correlation_dendrogram_data(users_commits, min_row_std=0.0)
    if data is None:
        return None, []
    excl = [str(x) for x in (data.get("excluded") or [])]
    z = data.get("linkage")
    lab = data.get("labels")
    if z is None or not isinstance(lab, list) or len(lab) < 2:
        return None, excl
    from scipy.cluster.hierarchy import leaves_list

    assert isinstance(z, np.ndarray)
    order_idx = list(leaves_list(z))
    labels = [str(x) for x in lab]
    return [labels[i] for i in order_idx], excl


def hierarchical_user_order(
    users_commits: dict[str, pd.Series],
) -> list[str] | None:
    """
    Leave order from average-linkage on correlation distance between per-user
    *weekly* commit-sum vectors. Users with a constant series (e.g. no commits
    in window) are omitted from the tree; see
    :func:`cohort_correlation_dendrogram_data`.
    """
    leaves, _ex = cohort_dendrogram_leaves(users_commits)
    return leaves
