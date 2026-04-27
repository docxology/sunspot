# `sunspot.tables`

Plaintext sidecars for every statistical block in
`statistics/report.json`. Source: [`tables.py`](../../src/sunspot/tables.py).

| name | description |
|------|-------------|
| `write_analysis_tables(report, analysis_dir, *, lag_results=None, ccf_results=None) -> list[Path]` | Writes one tidy CSV per analysis under `analysis_dir/tables/` plus a `README.md` schema reference. Defensive: missing fields produce empty / partial files rather than failing the run. Returns the list of paths that were written. |

## Files written under `analysis/tables/`

| file | rows | columns |
|------|------|---------|
| `associations.csv`             | one per (metric, kind ∈ {pearson, spearman, kendall}) | `metric, kind, n, value, ci95_lo, ci95_hi, p, stars` |
| `lag_profile.csv`              | one per (metric, lag) for the full Spearman lag scan | `metric, lag_days, rho, p, fdr_significant` |
| `ccf_profile.csv`              | one per (metric, lag) for the cross-correlation scan | `metric, lag_days, ccf, bartlett_ci95, crosses_bartlett_ci95, method, n_eff` |
| `ma_correlations.csv`          | one per (metric, MA window) | `metric, window_days, n, n_eff, pearson_r, pearson_lo, pearson_hi, pearson_p, spearman_rho, spearman_lo, spearman_hi, spearman_p` |
| `mi_lag.csv`                   | one per (metric, lag) | `metric, lag_days, mi_nats, n, method, bins_or_k` |
| `mutual_information.csv`       | one per metric | `metric, n, binned_nats, binned_normalised, binned_bins, ksg_nats` |
| `regression_ols.csv`           | one per metric | `metric, n, b0, b1, r2, sigma2, pearson_r, pearson_lo, pearson_hi, pearson_p, durbin_watson, normality_stat, normality_p` |
| `partial_correlation_ar1.csv`  | one per metric | `metric, controls, n, pearson_r, pearson_p, spearman_rho, spearman_p` |
| `cross_metric_spearman.csv`    | square Spearman matrix | index `metric` + one column per metric |
| `periodogram_top.csv`          | top-5 LS peaks per series (commits + each metric) | `series, rank, period_days, power` |
| `spectral_band_power.csv`      | named LS period-band power fractions | `series, band, min_period_days, max_period_days, power_fraction` |
| `commits_daily_summary.csv`    | one row | scalar fields from the daily commit summary block |
| `per_repo_topk.csv`            | top-K \|ρ\| per metric across repos (FDR flagged) | `repo, metric, n, total_commits, rho, p, q_significant` |
| `multi_user_topk.csv`          | when `--compare-users` is set, or a **cohort** run (always built if the block exists) | `user, metric, n, rho, p, kind` |
| `cohort_user_summary.csv`      | one row per cohort login | `login, total_commits, total_days, active_days, active_days_fraction, mean_per_day, mean_per_active_day, max_day, max_day_date` |
| `README.md`                    | schema reference, regenerated each run | — |

`stars` follows: `***` (p < 0.001), `**` (p < 0.01), `*` (p < 0.05),
`.` (p < 0.10), empty otherwise.

## Invariants

- Every row carries the sample size `n` it was computed from, where applicable.
- Every correlation row carries 95 % CI bounds when the underlying writer
  supplies them (`pearson_with_ci` / `spearman_with_ci`); otherwise CI cells
  are empty.
- File set is closed: the writer never invents tables that are not in the
  list above. New analyses must be added explicitly.
- Missing report blocks produce **no file** rather than an empty file —
  callers can use `Path.exists()` to feature-detect what a run produced.
- **Cohort** runs call the same `write_analysis_tables` helper; most
  per-metric-only files are absent or empty because the cohort `report` dict
  lacks single-anchor blocks. Cohort-specific CSVs (e.g. `multi_user_*.csv`
  from `analysis/`) are [documented in cohort output](cohort.md).
