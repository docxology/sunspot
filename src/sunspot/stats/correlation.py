from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from sunspot.align.join import join_on_dates


@dataclass(frozen=True, slots=True)
class Association:
    kind: str
    value: float
    p: float | None = None  # p-value, when defined


def _safe_dropna(a: pd.Series, b: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    m = a.notna() & b.notna()
    x = a[m].to_numpy(dtype=float, copy=True)
    y = b[m].to_numpy(dtype=float, copy=True)
    return x, y


def association_metrics(a: pd.Series, b: pd.Series) -> list[Association]:
    x, y = _safe_dropna(a, b)
    if x.size < 2:
        return [
            Association("pearson", float("nan"), None),
            Association("spearman", float("nan"), None),
            Association("kendall", float("nan"), None),
        ]
    if np.all(x == x[0]) or np.all(y == y[0]):
        return [
            Association("pearson", float("nan"), None),
            Association("spearman", float("nan"), None),
            Association("kendall", float("nan"), None),
        ]
    pr = scipy_stats.pearsonr(x, y)
    sp = scipy_stats.spearmanr(x, y)
    kt = scipy_stats.kendalltau(x, y)
    return [
        Association("pearson", float(pr.statistic), float(pr.pvalue)),
        Association("spearman", float(sp.statistic), float(sp.pvalue)),
        Association(
            "kendall",
            float(kt.statistic),
            float(kt.pvalue) if kt.pvalue is not None else None,
        ),
    ]


@dataclass(frozen=True, slots=True)
class LagResult:
    lags: list[int]
    values: list[float]
    p_values: list[float | None] | None
    best_lag: int
    best_value: float


def lag_correlation_search(
    a: pd.Series,
    b: pd.Series,
    *,
    max_lag: int = 30,
    method: str = "pearson",
) -> LagResult:
    """
    Shift ``a`` by ``k`` days (positive means ``a`` leads ``b``).
    Align on intersection only; ignores rows with any NaN after shift.
    """
    lags: list[int] = []
    vals: list[float] = []
    ps: list[float | None] = []
    a = a.sort_index()
    b = b.sort_index()
    for k in range(-max_lag, max_lag + 1):
        aa = a.shift(k)
        x, y = _safe_dropna(aa, b)
        if x.size < 2 or np.all(x == x[0]) or np.all(y == y[0]):
            lags.append(k)
            vals.append(float("nan"))
            ps.append(None)
            continue
        if method == "spearman":
            r = scipy_stats.spearmanr(x, y)
            lags.append(k)
            vals.append(float(r.statistic))
            ps.append(float(r.pvalue))
        else:
            r = scipy_stats.pearsonr(x, y)
            lags.append(k)
            vals.append(float(r.statistic))
            ps.append(float(r.pvalue))
    arr = np.array(vals, dtype=float)
    if not np.isfinite(arr).any():
        return LagResult(
            lags=lags,
            values=vals,
            p_values=ps,
            best_lag=0,
            best_value=float("nan"),
        )
    best_i = int(np.nanargmax(np.abs(arr)))
    return LagResult(
        lags=lags,
        values=vals,
        p_values=ps,
        best_lag=lags[best_i],
        best_value=vals[best_i],
    )


def spearman_with_ci(
    a: pd.Series,
    b: pd.Series,
    *,
    alpha: float = 0.05,
) -> tuple[float, float, float, float | None, int]:
    """
    Spearman rho with Fisher z CI using the Bonett-Wright SE adjustment
    ``se = sqrt((1 + r^2/2) / (n - 3))``. Returns ``(rho, lo, hi, p, n)``.
    """
    x, y = _safe_dropna(a, b)
    n = int(x.size)
    if n < 4 or np.all(x == x[0]) or np.all(y == y[0]):
        return float("nan"), float("nan"), float("nan"), None, n
    sp = scipy_stats.spearmanr(x, y)
    r = float(sp.statistic)
    p = float(sp.pvalue)
    if abs(r) >= 1.0:
        return r, float("nan"), float("nan"), p, n
    z = 0.5 * np.log((1.0 + r) / (1.0 - r))
    se = float(np.sqrt((1.0 + r**2 / 2.0) / (n - 3)))
    crit = float(scipy_stats.norm.ppf(1.0 - alpha / 2.0))
    lo = float(np.tanh(z - crit * se))
    hi = float(np.tanh(z + crit * se))
    return r, lo, hi, p, n


def bootstrap_corr_ci(
    a: pd.Series,
    b: pd.Series,
    *,
    method: str = "spearman",
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int | None = 0,
) -> tuple[float, float, float, int]:
    """
    Percentile bootstrap CI for Pearson/Spearman/Kendall. Returns ``(point, lo, hi, n)``.

    Resamples *paired* (a, b) rows with replacement.
    """
    x, y = _safe_dropna(a, b)
    n = int(x.size)
    if n < 8 or np.all(x == x[0]) or np.all(y == y[0]):
        return float("nan"), float("nan"), float("nan"), n
    fn = {
        "pearson": lambda u, v: float(scipy_stats.pearsonr(u, v).statistic),
        "spearman": lambda u, v: float(scipy_stats.spearmanr(u, v).statistic),
        "kendall": lambda u, v: float(scipy_stats.kendalltau(u, v).statistic),
    }[method]
    rng = np.random.default_rng(seed)
    point = fn(x, y)
    out = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        try:
            out[i] = fn(x[idx], y[idx])
        except (ValueError, RuntimeWarning):
            out[i] = float("nan")
    finite = out[np.isfinite(out)]
    if finite.size < 2:
        return point, float("nan"), float("nan"), n
    lo = float(np.quantile(finite, alpha / 2.0))
    hi = float(np.quantile(finite, 1.0 - alpha / 2.0))
    return point, lo, hi, n


def ar1_prewhiten(
    a: pd.Series,
    b: pd.Series,
) -> tuple[pd.Series, pd.Series, float, float]:
    """
    Pre-whiten ``a`` and ``b`` by removing AR(1) structure jointly.

    Estimates ``phi_a = lag-1 autocorr(a)`` then filters both series with the
    same AR(1) filter ``y_t = x_t - phi_a * x_{t-1}`` (Box-Jenkins style;
    avoids spurious cross-correlation peaks driven by shared autocorrelation).

    Returns ``(a', b', phi_a, phi_b)`` with the first sample dropped.
    """
    a2 = a.sort_index().astype(float)
    b2 = b.sort_index().astype(float)
    common = a2.index.intersection(b2.index)
    a2 = a2.reindex(common)
    b2 = b2.reindex(common)
    av = a2.to_numpy(dtype=float)
    bv = b2.to_numpy(dtype=float)
    mask = np.isfinite(av) & np.isfinite(bv)
    if mask.sum() < 10:
        return a2.iloc[1:], b2.iloc[1:], float("nan"), float("nan")
    afm = av[mask]
    bfm = bv[mask]
    if np.std(afm) == 0.0 or np.std(bfm) == 0.0:
        return a2.iloc[1:], b2.iloc[1:], float("nan"), float("nan")
    phi_a = float(np.corrcoef(afm[:-1], afm[1:])[0, 1])
    phi_b = float(np.corrcoef(bfm[:-1], bfm[1:])[0, 1])
    af = av[1:] - phi_a * av[:-1]
    bf = bv[1:] - phi_a * bv[:-1]
    out_idx = common[1:]
    return (
        pd.Series(af, index=out_idx, name=a.name),
        pd.Series(bf, index=out_idx, name=b.name),
        phi_a,
        phi_b,
    )


@dataclass(frozen=True, slots=True)
class CCFResult:
    lags: list[int]
    values: list[float]
    bartlett_ci: float
    n: int
    method: str


def cross_correlation_function(
    a: pd.Series,
    b: pd.Series,
    *,
    max_lag: int = 60,
    method: str = "pearson",
    prewhiten: bool = False,
    alpha: float = 0.05,
) -> CCFResult:
    """
    Cross-correlation function with approximate confidence band ``±z * 1/sqrt(n)``
    (Bartlett's bound for large n). Positive lag means ``a`` leads ``b``.

    Set ``prewhiten=True`` to AR(1)-whiten both series (see :func:`ar1_prewhiten`)
    before computing the CCF — recommended when both series carry strong
    autocorrelation (true for solar / geomagnetic indices).
    """
    if prewhiten:
        a, b, _, _ = ar1_prewhiten(a, b)
    common = a.sort_index().index.intersection(b.sort_index().index)
    a = a.reindex(common).astype(float)
    b = b.reindex(common).astype(float)
    n_eff = int((a.notna() & b.notna()).sum())
    lags: list[int] = list(range(-max_lag, max_lag + 1))
    vals: list[float] = []
    for k in lags:
        ak = a.shift(k)
        x, y = _safe_dropna(ak, b)
        if x.size < 4 or np.all(x == x[0]) or np.all(y == y[0]):
            vals.append(float("nan"))
            continue
        if method == "spearman":
            v = float(scipy_stats.spearmanr(x, y).statistic)
        else:
            v = float(scipy_stats.pearsonr(x, y).statistic)
        vals.append(v)
    crit = float(scipy_stats.norm.ppf(1.0 - alpha / 2.0))
    ci = float(crit / np.sqrt(max(n_eff, 1)))
    return CCFResult(lags=lags, values=vals, bartlett_ci=ci, n=n_eff, method=method)


def partial_correlation(
    a: pd.Series,
    b: pd.Series,
    controls: list[pd.Series],
    *,
    method: str = "pearson",
) -> tuple[float, float | None, int]:
    """
    Partial correlation of ``a`` and ``b`` controlling for ``controls`` (list of
    Series). Computed by regressing ``a`` and ``b`` on the controls and
    correlating the residuals. Returns ``(coef, p, n)``.
    """
    cols = {"_a": a, "_b": b}
    for i, s in enumerate(controls):
        cols[f"c{i}"] = s
    df = pd.concat(cols, axis=1).dropna()
    n = int(len(df))
    if n < 4 or len(controls) == 0:
        return float("nan"), None, n
    cols_list = [df[f"c{i}"].to_numpy(dtype=float) for i in range(len(controls))]
    X = np.column_stack([np.ones(n), *cols_list])
    ya = df["_a"].to_numpy(dtype=float)
    yb = df["_b"].to_numpy(dtype=float)
    beta_a, *_ = np.linalg.lstsq(X, ya, rcond=None)
    beta_b, *_ = np.linalg.lstsq(X, yb, rcond=None)
    ra = ya - X @ beta_a
    rb = yb - X @ beta_b
    if np.std(ra) == 0.0 or np.std(rb) == 0.0:
        return float("nan"), None, n
    if method == "spearman":
        r = scipy_stats.spearmanr(ra, rb)
    else:
        r = scipy_stats.pearsonr(ra, rb)
    return float(r.statistic), float(r.pvalue), n


def acf_values(x: pd.Series, *, n_lags: int = 60) -> tuple[np.ndarray, float]:
    """
    Sample autocorrelation function for lags 0..n_lags. Returns ``(acf, ci_band)``
    where ``ci_band`` is the ±95% white-noise band ``1.96/sqrt(n)``.
    """
    v = x.dropna().to_numpy(dtype=float)
    n = v.size
    if n < 4:
        return np.array([], dtype=float), float("nan")
    v = v - v.mean()
    denom = float(np.dot(v, v))
    if denom == 0.0:
        return np.zeros(n_lags + 1), float(1.96 / np.sqrt(n))
    out = np.empty(n_lags + 1, dtype=float)
    for k in range(n_lags + 1):
        if k == 0:
            out[k] = 1.0
        else:
            out[k] = float(np.dot(v[:-k], v[k:]) / denom)
    return out, float(1.96 / np.sqrt(n))


def pacf_values(x: pd.Series, *, n_lags: int = 30) -> tuple[np.ndarray, float]:
    """
    Partial autocorrelation via Durbin–Levinson recursion (Yule–Walker).
    Returns ``(pacf, ci_band)``.
    """
    acf, ci = acf_values(x, n_lags=n_lags)
    if acf.size == 0:
        return np.array([], dtype=float), ci
    n_lags = acf.size - 1
    pacf = np.zeros(n_lags + 1, dtype=float)
    pacf[0] = 1.0
    if n_lags == 0:
        return pacf, ci
    phi: list[np.ndarray] = []
    pacf[1] = acf[1]
    phi.append(np.array([acf[1]]))
    for k in range(2, n_lags + 1):
        prev = phi[-1]
        denom = 1.0 - float(np.dot(prev, acf[1:k][::-1]))
        if abs(denom) < 1e-12:
            pacf[k] = 0.0
            phi.append(np.zeros(k))
            continue
        num = acf[k] - float(np.dot(prev, acf[1:k][::-1]))
        pkk = num / denom
        new = np.empty(k, dtype=float)
        new[:-1] = prev - pkk * prev[::-1]
        new[-1] = pkk
        pacf[k] = pkk
        phi.append(new)
    return pacf, ci


def durbin_watson(residuals: np.ndarray | pd.Series) -> float:
    """
    Durbin–Watson statistic for first-order autocorrelation of residuals.

    Returns ``d = Σ(e_t − e_{t−1})² / Σ e_t²`` in ``[0, 4]``:

    * ``d ≈ 2`` — no residual AR(1) structure
    * ``d < 2`` — positive AR(1) (common in time-series OLS)
    * ``d > 2`` — negative AR(1)

    Returns ``NaN`` on constant-zero residuals or ``n < 2``.
    """
    if isinstance(residuals, pd.Series):
        r = residuals.to_numpy(dtype=float)
    else:
        r = np.asarray(residuals, dtype=float)
    r = r[np.isfinite(r)]
    if r.size < 2:
        return float("nan")
    rss = float(np.dot(r, r))
    if rss <= 0.0:
        return float("nan")
    d = np.diff(r)
    return float(np.dot(d, d) / rss)


def pearson_with_ci(
    a: pd.Series,
    b: pd.Series,
    *,
    alpha: float = 0.05,
) -> tuple[float, float, float, float | None, int]:
    """
    Pearson r with Fisher z-transform CI. Returns ``(r, lo, hi, p, n)``.

    For ``n < 4`` returns NaN bounds. CI is two-sided at level ``1 - alpha``.
    """
    x, y = _safe_dropna(a, b)
    n = int(x.size)
    if n < 2 or np.all(x == x[0]) or np.all(y == y[0]):
        return float("nan"), float("nan"), float("nan"), None, n
    pr = scipy_stats.pearsonr(x, y)
    r = float(pr.statistic)
    p = float(pr.pvalue)
    if n < 4 or abs(r) >= 1.0:
        return r, float("nan"), float("nan"), p, n
    z = 0.5 * np.log((1.0 + r) / (1.0 - r))
    se = 1.0 / np.sqrt(n - 3)
    crit = float(scipy_stats.norm.ppf(1.0 - alpha / 2.0))
    lo = float(np.tanh(z - crit * se))
    hi = float(np.tanh(z + crit * se))
    return r, lo, hi, p, n


def lag_window_grid(
    commits: pd.Series,
    metric: pd.Series,
    *,
    lags: list[int] | None = None,
    windows: list[int] | None = None,
    method: str = "spearman",
) -> tuple[np.ndarray, list[int], list[int]]:
    """
    Spearman/Pearson over a (lag × rolling-window) grid.

    Returns ``(grid, lags, windows)`` where ``grid[i, j]`` is the median rolling
    correlation at ``lags[i]`` over rolling windows of size ``windows[j]`` days.
    """
    if lags is None:
        lags = list(range(-60, 61, 5))
    if windows is None:
        windows = [30, 90, 180, 365]
    a = commits.sort_index().astype(float)
    b = metric.sort_index().astype(float)
    common = a.index.intersection(b.index)
    a = a.reindex(common)
    b = b.reindex(common)
    out = np.full((len(lags), len(windows)), np.nan, dtype=float)
    for i, k in enumerate(lags):
        ak = a.shift(k)
        for j, w in enumerate(windows):
            min_p = max(3, w // 3)
            if method == "spearman":
                # rank then rolling Pearson on ranks
                ar = ak.rank()
                br = b.rank()
                roll = ar.rolling(w, min_periods=min_p).corr(br)
            else:
                roll = ak.rolling(w, min_periods=min_p).corr(b)
            arr = roll.to_numpy(dtype=float)
            arr = arr[np.isfinite(arr)]
            if arr.size:
                out[i, j] = float(np.median(arr))
    return out, list(lags), list(windows)


def cross_metric_corr_matrix(
    frame: pd.DataFrame,
    *,
    method: str = "spearman",
) -> pd.DataFrame:
    """Square correlation matrix over ``frame`` columns (NaN-safe pairwise)."""
    cols = list(frame.columns)
    n = len(cols)
    out = np.full((n, n), np.nan, dtype=float)
    for i in range(n):
        for j in range(i, n):
            x, y = _safe_dropna(frame.iloc[:, i], frame.iloc[:, j])
            if x.size < 2 or np.all(x == x[0]) or np.all(y == y[0]):
                v = float("nan")
            elif method == "spearman":
                v = float(scipy_stats.spearmanr(x, y).statistic)
            elif method == "kendall":
                v = float(scipy_stats.kendalltau(x, y).statistic)
            else:
                v = float(scipy_stats.pearsonr(x, y).statistic)
            out[i, j] = v
            out[j, i] = v
    return pd.DataFrame(out, index=cols, columns=cols)


def fdr_on_pvalues(p: np.ndarray, *, q: float = 0.1) -> np.ndarray:
    """
    Benjamini–Hochberg (two-sided). p entries may be NaN.
    """
    p = np.asarray(p, dtype=float)
    m = p.size
    order = np.argsort(np.where(p == p, p, 1.0))  # NaNs at end
    ranks = np.empty(m, dtype=int)
    ranks[order] = np.arange(1, m + 1)
    thresh = q * np.arange(1, m + 1) / m
    p_sorted = p[order]
    passed = p_sorted <= thresh
    if not np.any(passed):
        return np.zeros(m, dtype=bool)
    k = int(np.max(np.where(passed)))
    c = p_sorted[k]
    return p <= c


def rolling_pearson(
    a: pd.Series,
    b: pd.Series,
    window: int = 30,
) -> pd.Series:
    d = join_on_dates(a, b)
    if d.shape[1] != 2:
        raise ValueError("expected two series")
    d = d.sort_index()
    c1 = d.iloc[:, 0]
    c2 = d.iloc[:, 1]
    out = c1.rolling(window, min_periods=max(3, window // 3)).corr(c2)
    out.name = f"roll_pearson_{window}d"
    return out


def moving_average_correlation_curve(
    a: pd.Series,
    b: pd.Series,
    *,
    windows: list[int] | None = None,
    method: str = "pearson",
    alpha: float = 0.05,
) -> list[dict[str, float | int | str | None]]:
    """
    Correlation of ``MA_w(a)`` vs ``MA_w(b)`` for several smoothing windows ``w``.

    Each row reports ``{window, method, r, lo, hi, p, n_eff}`` where ``n_eff`` is
    a coarse Bartlett-style effective sample size ``n / w`` to flag the loss of
    independent observations from smoothing — raw p / CI are computed on the
    full smoothed series and should be interpreted alongside ``n_eff``.

    Parameters
    ----------
    windows : list[int]
        Smoothing windows (days). Defaults to ``[1, 7, 14, 30, 60, 90, 180, 365]``.
        ``window=1`` is the unsmoothed daily correlation.
    method : {'pearson', 'spearman'}
        Coefficient family. CIs use Fisher z (Pearson) or Bonett–Wright (Spearman).
    alpha : float
        Two-sided level (default 0.05).
    """
    if windows is None:
        windows = [1, 7, 14, 30, 60, 90, 180, 365]
    method = method.strip().lower()
    if method not in {"pearson", "spearman"}:
        raise ValueError(f"unknown method: {method!r}")
    out: list[dict[str, float | int | str | None]] = []
    common = a.index.intersection(b.index)
    a = a.reindex(common).sort_index().astype(float)
    b = b.reindex(common).sort_index().astype(float)
    n_total = int(min(a.notna().sum(), b.notna().sum()))
    for w in windows:
        if w <= 1:
            xa, xb = a, b
        else:
            xa = a.rolling(w, min_periods=max(3, w // 3)).mean()
            xb = b.rolling(w, min_periods=max(3, w // 3)).mean()
        if method == "pearson":
            r, lo, hi, p, n = pearson_with_ci(xa, xb, alpha=alpha)
        else:
            r, lo, hi, p, n = spearman_with_ci(xa, xb, alpha=alpha)
        n_eff = int(max(1, n_total // max(1, w)))
        out.append({
            "window": int(w),
            "method": method,
            "r": float(r),
            "lo": float(lo),
            "hi": float(hi),
            "p": (float(p) if p is not None else None),
            "n": int(n),
            "n_eff": int(n_eff),
        })
    return out
