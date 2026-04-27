# Stats

Correlation, time-series, and spectral primitives consumed by
`correlate.run_correlation_report`.

## Single series

- `association_metrics` — Pearson / Spearman / Kendall (NaN-safe).
- `pearson_with_ci` — Pearson r with Fisher-z 95 % confidence interval.
- `spearman_with_ci` — Spearman ρ with Bonett–Wright Fisher-z CI.
- `bootstrap_corr_ci` — percentile bootstrap CI for Pearson / Spearman / Kendall.
- `partial_correlation` — Pearson partial ρ controlling for a set of covariates.

## Time-domain dependence

- `lag_correlation_search` — Spearman/Pearson over ±lag window; returns full
  profile and per-lag p-values.
- `cross_correlation_function` — CCF up to ±`max_lag` with Bartlett ±95 %
  envelope and optional joint AR(1) pre-whitening.
- `ar1_prewhiten` — joint AR(1) residualisation that removes red-noise
  inflation before correlating two series.
- `acf_values`, `pacf_values` — autocorrelation / partial autocorrelation up to
  `n_lags`.
- `lag_window_grid` — `lag × rolling-window` median correlation surface
  (drives `viz.save_lag_heatmap`).

## Cross-series and group structure

- `cross_metric_corr_matrix` — pairwise matrix across the columns of a frame.
- `rolling_pearson` — rolling Pearson on an aligned join.
- `per_repo_associations` — repo × metric Spearman with FDR per metric.
- `multi_user_associations` — user × metric Spearman with FDR per metric across
  users (drives the user × metric heatmap).
- `multi_user_rank_matrix` — pairwise correlation between users' smoothed
  commit activity (drives the user × user heatmap).

## Frequency domain

- `lomb_scargle_periodogram` — handles uneven sampling; returns the spectrum
  and the dominant period in days.
- `dominant_period` — convenience accessor for the peak.

## Multiple-testing control

- `fdr_on_pvalues` — Benjamini–Hochberg across an arbitrary vector.

All correlations are **exploratory**. Solar / geomagnetic indices are highly
autocorrelated; raw p-values understate the true noise, so always read CI / FDR
columns and CCF Bartlett bands alongside point estimates. Use `bootstrap` and
`prewhiten=True` (CCF) when in doubt.

See `AGENTS.md` for full signatures.
