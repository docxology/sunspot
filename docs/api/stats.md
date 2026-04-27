# `sunspot.stats`

## `correlation` ([`correlation.py`](../../src/sunspot/stats/correlation.py))

| name | description |
|------|-------------|
| `Association` | Dataclass: `kind`, `value`, `p` (optional). |
| `association_metrics(a, b) -> list[Association]` | Pearson, Spearman, Kendall; fewer than 2 valid points or all-constant input yields NaN associations. |
| `LagResult` | `lags`, `values`, `p_values` optional, `best_lag`, `best_value`. |
| `CCFResult` | `lags`, `values`, `n`, `bartlett_ci`, `method`. |
| `lag_correlation_search(a, b, *, max_lag=30, method="pearson")` | Shifts `a` by k days; Spearman or Pearson at each lag; best by max \|statistic\|. |
| `pearson_with_ci(a, b, *, alpha=0.05) -> (r, lo, hi, p, n)` | Fisher-z CI; small `n` or `abs(r) >= 1` may yield NaN bounds. |
| `spearman_with_ci(a, b, *, alpha=0.05) -> (rho, lo, hi, p, n)` | Bonett–Wright Fisher-z CI. |
| `bootstrap_corr_ci(a, b, *, method="pearson", n_boot=1000, seed=0, alpha=0.05) -> (point, lo, hi)` | Percentile bootstrap CI (Pearson, Spearman or Kendall). |
| `ar1_prewhiten(a, b) -> (ax, bx)` | Joint AR(1) residualisation; drops the burned-in lag. |
| `cross_correlation_function(a, b, *, max_lag=60, method="pearson", prewhiten=True) -> CCFResult` | Cross-correlation up to ±`max_lag` with Bartlett ±95 % envelope. |
| `partial_correlation(a, b, controls, *, method="pearson") -> (rho, p, n)` | Pearson or Spearman partial correlation via OLS residuals, where `controls` is a list of aligned `Series`. |
| `acf_values(x, *, n_lags=60) -> np.ndarray` | Autocorrelation up to `n_lags`. |
| `pacf_values(x, *, n_lags=60) -> np.ndarray` | Partial autocorrelation (Yule–Walker) up to `n_lags`. |
| `lag_window_grid(commits, metric, *, lags=None, windows=None, method="spearman")` | Returns `(grid, lags, windows)`; median rolling corr in each (lag, window) cell. |
| `cross_metric_corr_matrix(frame, *, method="spearman") -> pd.DataFrame` | Square symmetric matrix. |
| `fdr_on_pvalues(p, *, q=0.1) -> np.ndarray[bool]` | Benjamini–Hochberg two-sided. |
| `rolling_pearson(a, b, window=30) -> pd.Series` | Uses `join_on_dates` internally. |
| `moving_average_correlation_curve(a, b, *, windows=None, method="pearson", alpha=0.05) -> list[dict]` | For each smoothing window `w`: `{window, method, r, lo, hi, p, n, n_eff}`; CI via Fisher z (Pearson) or Bonett–Wright (Spearman); `n_eff = n // w` is a Bartlett-style independence proxy. Default `windows=[1, 7, 14, 30, 60, 90, 180, 365]`. |
| `durbin_watson(residuals) -> float` | DW statistic for first-order residual AR(1). `≈2` = no AR(1), `<2` = positive, `>2` = negative. Returns `NaN` for constant or `n<2` input. |

## `spectral` ([`spectral.py`](../../src/sunspot/stats/spectral.py))

| name | description |
|------|-------------|
| `Periodogram` | Dataclass: `periods_days`, `power`, `method`, `n`, `dominant_period_days`; `.top_k(k)` returns the top peaks. |
| `lomb_scargle_periodogram(s, *, min_period_days=4.0, max_period_days=None, n_freqs=1500, standardize=True) -> Periodogram` | Lomb–Scargle on uneven daily-cadence input; log-spaced period grid in `[min_period_days, min(max_period_days, n)/2]`. Constant input → empty result. |
| `dominant_period(p: Periodogram) -> float` | Convenience accessor for the peak period. |
| `band_power(p, *, min_period_days, max_period_days) -> float` | Fraction of total LS power inside the `[lo, hi]` period band. Argument order is swap-invariant. Empty periodogram → `0.0`; empty band / zero total → `NaN`. |

## `per_repo` ([`per_repo.py`](../../src/sunspot/stats/per_repo.py))

| name | description |
|------|-------------|
| `per_repo_associations(commits_by_repo, metrics_frame, *, method="spearman", min_active_days=10, fdr_q=0.1) -> pd.DataFrame` | Long form: `repo`, `metric`, `n`, `total_commits`, `rho`, `p`, `q_significant` (FDR per metric across repos). |

## `information` ([`information.py`](../../src/sunspot/stats/information.py))

| name | description |
|------|-------------|
| `MILagResult` | Dataclass: `lags`, `values` (nats), `method`, `bins_or_k`, `n_per_lag`, `best_lag`, `best_value`. |
| `mutual_information_binned(a, b, *, bins='fd') -> (mi_nats, n, bins)` | Plug-in MI on a 2-D histogram with **Miller–Madow** bias correction; Freedman–Diaconis bin selection by default (`'fd'`). Returns `nan` for `n<4` or constant input. |
| `mutual_information_ksg(a, b, *, k=5) -> (mi_nats, n)` | **Kraskov–Stögbauer–Grassberger (KSG-1)** k-NN estimator using Chebyshev metric and digamma corrections. Distribution-free; clips to 0. |
| `normalised_mi(mi_nats, n, bins) -> float` | Normalise MI by `log(min(bins, n))` so values sit in `[0, 1]`. |
| `mutual_information_lag_curve(a, b, *, max_lag=30, method='binned' | 'ksg', bins='fd', k=5) -> MILagResult` | Mirror of `lag_correlation_search` — `I(a.shift(ℓ); b)` for `ℓ ∈ [-max_lag, +max_lag]`; positive ℓ ⇒ a leads b. |

All MI values are returned in **nats** (natural-log basis); divide by `ln 2`
to convert to bits. See [`docs/measures/`](../measures/README.md) for the
specific properties of each input series and [`docs/api/viz.md`](viz.md)
for the matching `save_mi_lag_curve` plot writer.

## `multi_user` ([`multi_user.py`](../../src/sunspot/stats/multi_user.py))

Used when [`--compare-users` is set in `correlate`](cli.md#correlate) and for every [`run_cohort_report`](cohort.md) run.

| name | description |
|------|-------------|
| `multi_user_associations(users_commits, metrics_frame, *, method="spearman", fdr_q=0.1, min_active_days=30) -> pd.DataFrame` | Long form: `user`, `metric`, `n`, `total_commits`, `active_days`, `rho`, `p`, `q_significant` (FDR per metric across users). |
| `multi_user_rank_matrix(users_commits, *, method="spearman", smoothing_window=30) -> pd.DataFrame` | Pairwise correlation matrix between users' smoothed commit activity. |
| `pca_users_weekly(users_commits, *, n_components=2) -> dict \| None` | Weekly resample, z-score per user row, SVD; returns `user_order`, `pc_scores`, `explained_variance_ratio`, `n_weeks` or `None` if too few users/weeks. |
| `cohort_correlation_dendrogram_data(users_commits, *, min_row_std=0) -> dict \| None` | Average linkage on `pdist` **correlation** of weekly commit-sum rows; **excludes** users with no cross-week variation (e.g. all-zero window) so distances stay finite. Keys: `linkage`, `labels`, `excluded` (`linkage` may be `None` if \<2 users qualify). |
| `cohort_dendrogram_leaves(users_commits) -> tuple[list[str] \| None, list[str]]` | Dendrogram leaf order and excluded logins. |
| `hierarchical_user_order(users_commits) -> list[str] \| None` | Same leaves as `cohort_dendrogram_leaves` (convenience). |
