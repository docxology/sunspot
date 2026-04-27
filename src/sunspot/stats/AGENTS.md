# AGENTS — `stats`

## `correlation.py`

| name | kind | signature / description |
|------|------|-------------------------|
| `Association` | dataclass | `kind: str`, `value: float`, `p: float \| None` |
| `association_metrics` | function | `(a, b) -> list[Association]` — Pearson / Spearman / Kendall; NaN-safe; constant input → all NaN |
| `LagResult` | dataclass | `lags`, `values`, `p_values`, `best_lag`, `best_value` |
| `CCFResult` | dataclass | `lags`, `values`, `n`, `bartlett_ci`, `method` — cross-correlation profile with Bartlett ±95 % bands |
| `lag_correlation_search` | function | `(a, b, *, max_lag=30, method='spearman') -> LagResult` — shifts `a` by `k` days |
| `pearson_with_ci` | function | `(a, b, *, alpha=0.05) -> (r, lo, hi, p, n)` — Pearson r with Fisher-z 95 % CI |
| `spearman_with_ci` | function | `(a, b, *, alpha=0.05) -> (rho, lo, hi, p, n)` — Spearman ρ with Bonett–Wright Fisher-z CI |
| `bootstrap_corr_ci` | function | `(a, b, *, method='pearson', n_boot=1000, seed=0, alpha=0.05) -> (point, lo, hi)` — percentile bootstrap CI |
| `ar1_prewhiten` | function | `(a, b) -> (ax, bx)` — joint AR(1) residualisation, drops the burned-in lag |
| `cross_correlation_function` | function | `(a, b, *, max_lag=60, method='pearson', prewhiten=True) -> CCFResult` — CCF with Bartlett ±95 % envelope |
| `partial_correlation` | function | `(a, b, controls: list[Series], *, method='pearson') -> (rho, p, n)` — Pearson or Spearman partial correlation via OLS residuals |
| `acf_values` / `pacf_values` | function | `(x, n_lags=60) -> ndarray` — autocorrelation / partial autocorrelation up to `n_lags` |
| `lag_window_grid` | function | `(commits, metric, *, lags, windows, method='spearman') -> (grid, lags, windows)` — median rolling correlation across a `lag × window` grid |
| `cross_metric_corr_matrix` | function | `(frame, *, method='spearman') -> DataFrame` — square pairwise NaN-safe matrix |
| `rolling_pearson` | function | `(a, b, window) -> Series` — uses `align.join_on_dates` |
| `moving_average_correlation_curve` | function | `(a, b, *, windows=None, method='pearson', alpha=0.05) -> list[dict]` — for each smoothing window `w` returns `{window, method, r, lo, hi, p, n, n_eff}`. CIs use Fisher z (Pearson) or Bonett–Wright (Spearman); `n_eff = n // w` is a Bartlett-style independence proxy for interpreting p / CI after smoothing. Default windows `[1, 7, 14, 30, 60, 90, 180, 365]`. |
| `durbin_watson` | function | `(residuals) -> float` — DW statistic for first-order residual AR(1); `≈2` = no AR(1), `<2` = positive AR(1), `>2` = negative; accepts ndarray or Series. Returns `NaN` for constant/short input. |
| `fdr_on_pvalues` | function | Benjamini–Hochberg; returns bool mask of length `m` |

## `information.py`

| name | kind | signature / description |
|------|------|-------------------------|
| `MILagResult` | dataclass | `lags`, `values` (nats), `method`, `bins_or_k`, `n_per_lag`, `best_lag`, `best_value` |
| `mutual_information_binned` | function | `(a, b, *, bins='fd' | int) -> (mi_nats, n, bins_used)` — 2-D histogram MI with **Miller–Madow** bias correction; default Freedman–Diaconis bin selection clamped to `[8, 64]`. Clipped at 0. |
| `mutual_information_ksg` | function | `(a, b, *, k=5) -> (mi_nats, n)` — **KSG-1** k-NN MI with Chebyshev metric and digamma corrections; iid jitter for ties (fixed seed). |
| `normalised_mi` | function | `(mi_nats, n, bins) -> float` — divide by `log(min(bins, n))` so values land in `[0, 1]`. |
| `mutual_information_lag_curve` | function | `(a, b, *, max_lag=30, method='binned' | 'ksg', bins='fd', k=5) -> MILagResult` — `I(a.shift(ℓ); b)` for `ℓ ∈ [-max_lag, +max_lag]`; positive ℓ ⇒ a leads b. |

All MI values are in **nats** (natural-log basis).

## `spectral.py`

| name | kind | signature / description |
|------|------|-------------------------|
| `Periodogram` | dataclass | `periods_days`, `power`, `method`, `n`, `dominant_period_days`; `.top_k(k)` |
| `lomb_scargle_periodogram` | function | `(s, *, min_period_days=4.0, max_period_days=None, n_freqs=1500, standardize=True) -> Periodogram` — log-spaced grid in `[min_period_days, min(max_period_days, n)/2]`; drops NaN days; constant input → empty result |
| `dominant_period` | function | `(p: Periodogram) -> float` — convenience accessor for the peak period |
| `band_power` | function | `(p, *, min_period_days, max_period_days) -> float` — fraction of total LS power inside the `[lo, hi]` band. Argument order is swap-invariant. Empty periodogram → `0.0`; empty band / zero total → `NaN` |

## `per_repo.py`

- `per_repo_associations(commits_by_repo, metrics_frame, *, method='spearman', min_active_days=10, fdr_q=0.1) -> DataFrame` — long-form `repo, metric, n, total_commits, rho, p, q_significant`. BH-FDR is applied independently per metric across repos.

## `multi_user.py`

| name | kind | signature / description |
|------|------|-------------------------|
| `multi_user_associations` | function | `(users_commits, metrics_frame, *, method='spearman', fdr_q=0.1, min_active_days=30) -> DataFrame` — long-form `user, metric, n, total_commits, active_days, rho, p, q_significant`; BH-FDR per metric across users |
| `multi_user_rank_matrix` | function | `(users_commits, *, method='spearman', smoothing_window=30) -> DataFrame` — pairwise user×user correlation of smoothed activity |
| `pca_users_weekly` | function | `(users_commits, *, n_components=2) -> dict \| None` — weekly resample, row z-score, SVD; PC scores per user |
| `cohort_correlation_dendrogram_data` | function | `(users_commits, *, min_row_std=0) -> dict \| None` — average linkage on `pdist` **correlation** of weekly sum rows; omits users with no cross-week variation (avoids non-finite distances); `linkage` may be `None` if \<2 users qualify |
| `cohort_dendrogram_leaves` | function | `(users_commits) -> (list[str] \| None, list[str])` — optimal leaf order and excluded logins |
| `hierarchical_user_order` | function | `(users_commits) -> list[str] \| None` — leaves only; see `cohort_dendrogram_leaves` |
