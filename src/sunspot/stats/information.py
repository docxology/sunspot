"""
Information-theoretic association measures.

Two complementary estimators are exposed for ``I(X; Y)`` between continuous
daily series:

- :func:`mutual_information_binned` — fast histogram (plug-in) estimator
  with the Miller–Madow finite-sample bias correction. Useful for screening
  many ``(commits, metric)`` pairs and inside lag scans.
- :func:`mutual_information_ksg` — Kraskov–Stögbauer–Grassberger (KSG-1)
  k-nearest-neighbour estimator. Distribution-free, picks up nonlinear
  structure that Pearson/Spearman miss; slower (O(n log n)).

The MI lag curve :func:`mutual_information_lag_curve` mirrors
:func:`sunspot.stats.correlation.lag_correlation_search` so callers can drop
it into the same plotting / reporting code paths.

All values are returned in **nats** (natural-log basis); divide by ``ln 2``
to get bits.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import log

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.special import digamma


@dataclass(frozen=True, slots=True)
class MILagResult:
    """
    Mutual-information lag profile.

    Attributes
    ----------
    lags
        Integer day shifts applied to ``a`` (positive = ``a`` leads ``b``).
    values
        ``I(a_shift; b)`` in nats per lag.
    method
        ``"binned"`` or ``"ksg"``.
    bins_or_k
        ``bins`` for histograms or ``k`` for KSG.
    n_per_lag
        Effective sample size at each lag (after dropping NaNs).
    best_lag
        Lag with maximum MI.
    best_value
        MI at ``best_lag``.
    """

    lags: np.ndarray
    values: np.ndarray
    method: str
    bins_or_k: int
    n_per_lag: np.ndarray
    best_lag: int
    best_value: float


def _clean(a: pd.Series, b: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    m = a.notna() & b.notna()
    x = a[m].to_numpy(dtype=float, copy=True)
    y = b[m].to_numpy(dtype=float, copy=True)
    return x, y


def _freedman_diaconis_bins(x: np.ndarray, *, lo: int = 8, hi: int = 64) -> int:
    """
    Freedman–Diaconis rule clamped to ``[lo, hi]`` and never below
    ``ceil(sqrt(n) / 2)`` so very flat samples still get a sensible grid.
    """
    n = x.size
    if n < 4:
        return lo
    q1, q3 = np.quantile(x, [0.25, 0.75])
    iqr = float(q3 - q1)
    if iqr <= 0.0:
        h = (x.max() - x.min()) / max(1.0, np.sqrt(n))
    else:
        h = 2.0 * iqr / np.cbrt(n)
    if h <= 0.0:
        return lo
    bins = int(np.ceil((x.max() - x.min()) / h))
    bins = max(bins, int(np.ceil(np.sqrt(n) / 2)))
    return int(np.clip(bins, lo, hi))


def mutual_information_binned(
    a: pd.Series,
    b: pd.Series,
    *,
    bins: int | str = "fd",
) -> tuple[float, int, int]:
    """
    Plug-in MI estimator on a 2-D histogram with Miller–Madow correction.

    Parameters
    ----------
    a, b
        Aligned numeric series. NaN pairs are dropped.
    bins
        Number of bins per axis, or ``"fd"`` for the Freedman–Diaconis rule
        applied to each axis (the larger of the two is used).

    Returns
    -------
    (mi_nats, n, bins_used)
        MI in nats, sample size after dropping NaNs, and the bin count
        actually used. ``mi_nats`` is non-negative (clipped at 0); returns
        ``(nan, 0, 0)`` for ``n < 4`` or constant input.
    """
    x, y = _clean(a, b)
    n = int(x.size)
    if n < 4:
        return (float("nan"), 0, 0)
    if np.allclose(x, x[0]) or np.allclose(y, y[0]):
        return (0.0, n, 0)
    if isinstance(bins, str):
        if bins.lower() != "fd":
            raise ValueError(f"unknown bins rule: {bins!r}")
        bx = _freedman_diaconis_bins(x)
        by = _freedman_diaconis_bins(y)
        b_used = max(bx, by)
    else:
        b_used = int(bins)
        if b_used < 2:
            raise ValueError("bins must be >= 2")
    counts, _, _ = np.histogram2d(x, y, bins=b_used)
    pxy = counts / counts.sum()
    px = pxy.sum(axis=1, keepdims=True)
    py = pxy.sum(axis=0, keepdims=True)
    nz = pxy > 0
    with np.errstate(divide="ignore", invalid="ignore"):
        mi = float(np.sum(pxy[nz] * (np.log(pxy[nz]) - np.log((px @ py)[nz]))))
    # Miller–Madow bias correction applied to the underlying entropies:
    #   I = H(X) + H(Y) - H(X,Y),
    #   ΔH(X) = (m_x - 1)/(2n), ΔH(Y) = (m_y - 1)/(2n), ΔH(X,Y) = (R̂ - 1)/(2n)
    # so ΔI = (m_x + m_y - R̂ - 1) / (2n) (typically negative, removing the
    # well-known positive plug-in bias for sparse joints).
    m_x = int(np.count_nonzero(px))
    m_y = int(np.count_nonzero(py))
    r_hat = int(np.count_nonzero(counts))
    mi += (m_x + m_y - r_hat - 1) / (2.0 * n)
    return (max(0.0, float(mi)), n, int(b_used))


def mutual_information_ksg(
    a: pd.Series,
    b: pd.Series,
    *,
    k: int = 5,
) -> tuple[float, int]:
    """
    Kraskov–Stögbauer–Grassberger (KSG-1) MI estimator using k-NN distances.

    KSG-1 is the standard reference: ``I(X; Y) = ψ(k) + ψ(N) - <ψ(n_x + 1) +
    ψ(n_y + 1)>`` where ``n_x`` (resp. ``n_y``) counts marginal points
    strictly within the joint Chebyshev k-NN distance. Distribution-free and
    typically lower-bias than histograms when ``n`` is small or the joint is
    not axis-aligned.

    Returns ``(mi_nats, n)``. NaN-input pairs are dropped. Returns
    ``(nan, 0)`` for ``n <= k+1``; clips to ``0`` if the estimate is negative
    (which can happen by construction for very weakly dependent samples).
    """
    x, y = _clean(a, b)
    n = int(x.size)
    if n <= k + 1:
        return (float("nan"), 0)
    if np.allclose(x, x[0]) or np.allclose(y, y[0]):
        return (0.0, n)
    # Add tiny iid jitter so identical daily values don't collapse marginal
    # distances to zero (stable across runs via fixed seed).
    rng = np.random.default_rng(0)
    sx = float(np.std(x)) or 1.0
    sy = float(np.std(y)) or 1.0
    x = x + rng.normal(0.0, 1e-10 * sx, size=n)
    y = y + rng.normal(0.0, 1e-10 * sy, size=n)

    pts = np.column_stack([x, y])
    tree = cKDTree(pts)
    # Chebyshev metric (p=inf) is the KSG default.
    dists, _ = tree.query(pts, k=k + 1, p=np.inf)
    eps = dists[:, k]  # distance to the k-th neighbour (excluding self)

    tree_x = cKDTree(x.reshape(-1, 1))
    tree_y = cKDTree(y.reshape(-1, 1))
    nx = np.array(
        tree_x.query_ball_point(x.reshape(-1, 1), eps - 1e-12, p=np.inf, return_length=True),
    ) - 1  # exclude self
    ny = np.array(
        tree_y.query_ball_point(y.reshape(-1, 1), eps - 1e-12, p=np.inf, return_length=True),
    ) - 1
    nx = np.clip(nx, 0, None)
    ny = np.clip(ny, 0, None)
    mi = digamma(k) + digamma(n) - float(np.mean(digamma(nx + 1) + digamma(ny + 1)))
    return (max(0.0, float(mi)), n)


def normalised_mi(mi_nats: float, n: int, bins: int) -> float:
    """
    Normalise MI by the smaller marginal entropy bound ``log(min(bins, n))``
    so values land in ``[0, 1]``. Returns ``nan`` when undefined.
    """
    if bins is None or bins < 2 or n < 2 or not (mi_nats == mi_nats):
        return float("nan")
    cap = log(min(bins, n))
    return float(mi_nats / cap) if cap > 0 else float("nan")


def mutual_information_lag_curve(
    a: pd.Series,
    b: pd.Series,
    *,
    max_lag: int = 30,
    method: str = "binned",
    bins: int | str = "fd",
    k: int = 5,
) -> MILagResult:
    """
    Mutual-information vs integer lag, mirroring
    :func:`sunspot.stats.correlation.lag_correlation_search`.

    For each ``ℓ ∈ [-max_lag, +max_lag]`` we compute ``I(a.shift(ℓ); b)``.
    Positive ``ℓ`` means **a leads b**, matching the sign convention of the
    lag-correlation search.

    Parameters
    ----------
    method
        ``"binned"`` (fast, default) or ``"ksg"`` (k-NN, slower but bias-low).
    bins
        Bin rule passed to :func:`mutual_information_binned`.
    k
        Neighbour count for the KSG estimator.
    """
    method = method.strip().lower()
    if method not in {"binned", "ksg"}:
        raise ValueError(f"unknown MI method: {method!r}")
    lags = np.arange(-int(max_lag), int(max_lag) + 1, dtype=int)
    out = np.full(lags.shape, np.nan, dtype=float)
    ns = np.zeros(lags.shape, dtype=int)
    bins_used = 0
    for i, lag in enumerate(lags):
        a_s = a.shift(int(lag))
        if method == "binned":
            mi, n, bu = mutual_information_binned(a_s, b, bins=bins)
            bins_used = bu or bins_used
        else:
            mi, n = mutual_information_ksg(a_s, b, k=k)
        out[i] = mi
        ns[i] = n
    if not np.any(np.isfinite(out)):
        best_lag = 0
        best_value = float("nan")
    else:
        idx = int(np.nanargmax(out))
        best_lag = int(lags[idx])
        best_value = float(out[idx])
    return MILagResult(
        lags=lags,
        values=out,
        method=method,
        bins_or_k=int(bins_used if method == "binned" else k),
        n_per_lag=ns,
        best_lag=best_lag,
        best_value=best_value,
    )
