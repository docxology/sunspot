# `output/`

**GitHub cache (reusable data):** see [`github_data/README.md`](github_data/README.md) —
on-disk per-repo commit series and the SHA dedup DB default here so you can
archive one tree (`output/github_data/`) without scraping `~/.cache/`.

Run artifacts. Every numeric block in `statistics/report.json` has a
matching plaintext CSV under `analysis/tables/`, and every GitHub-derived
series for the run lives under `data/commits/`. For among-user-only runs (no
per-metric `ssn/`, `f107/`, … tiles, no per-repo), use `uv run sunspot cohort`
(see `sunspot cohort --help`); outputs add `visualizations/cohort/` (PCA,
dendrogram, weekly heatmap). By default, `uv run sunspot correlate …` writes to:

```
output/correlate/{github_login}__{since}__{until}/
├── statistics/
│   └── report.json
├── data/
│   ├── commits/                            # ALL GitHub-derived series live here
│   │   ├── daily.csv                       # commits per day (full UTC index)
│   │   ├── weekly.csv                      # week-starting Monday sums
│   │   ├── monthly.csv                     # month-starting sums
│   │   ├── dow_means.csv                   # Mon..Sun mean / median / total / n
│   │   ├── summary.csv                     # one-row daily-grain stats
│   │   ├── user_summary.csv                # cohort only: one activity row per login
│   │   ├── manifest.json                   # repos covered + window
│   │   ├── by_repo/{owner__repo}.csv       # one CSV per repo
│   │   └── by_user/                        # only with --compare-users
│   │       ├── manifest.json
│   │       └── {login}.csv                 # one CSV per compared user
│   └── {metric}/
│       ├── aligned_daily.csv
│       └── rolling.csv
├── visualizations/
│   ├── dynamics/
│   │   ├── commits_and_solar.png            # 7d/30d MA + z(SSN), z(F10.7)
│   │   └── compare_users_30d_ma.png         # only if --compare-users …
│   ├── overview/
│   │   ├── metric_correlation_matrix.png    # cross-metric Spearman heatmap
│   │   ├── lag_grid.png                     # per-metric lag curves (small multiples)
│   │   ├── metrics_zscored_overview.png     # z-overlays + commits MA
│   │   ├── stacked_panel.png                # commits MA + each metric stacked, shared x
│   │   ├── seasonal_calendar.png            # year × DOY commit heatmap with annual SSN strip
│   │   ├── dow_response.png                 # mean commits by day-of-week (+ DOW × metric tercile heatmap)
│   │   ├── commits_acf_pacf.png             # ACF + PACF of daily commits
│   │   └── commits_periodogram.png          # Lomb–Scargle periodogram of commits
│   ├── per_repo/
│   │   ├── repo_metric_spearman_heatmap.png # FDR-flagged dots
│   │   └── top_repos_30d_ma.png             # top-N repos with z(SSN) overlay
│   ├── multi_user/                          # only if --compare-users …
│   │   ├── overview_30d_ma.png              # per-user MA + z(SSN)
│   │   ├── user_metric_spearman_heatmap.png # user × metric Spearman, FDR-ringed
│   │   ├── user_user_rank_matrix.png        # pairwise user×user Spearman
│   │   ├── cumulative_vs_solar.png          # cumulative commits + z(SSN)
│   │   └── phase_by_ssn_quantile.png        # mean commits per z(SSN) quantile
│   ├── cohort/                              # cohort runs only
│   │   ├── user_pca_scatter.png
│   │   ├── user_dendrogram.png
│   │   ├── user_weekly_heatmap.png
│   │   └── user_summary.png
│   ├── {metric}/
│   │   ├── dual_axis.png
│   │   ├── scatter.png                      # r, ρ, τ, n in title; hexbin if n > 500
│   │   ├── joint_density.png                # hexbin + marginal histograms (joint distribution)
│   │   ├── regression.png                   # OLS + 95 % CI band, residual inset
│   │   ├── rolling_corr.png                 # rolling Pearson + Spearman
│   │   ├── ma_corr_curve.png                # MA-window vs r/ρ (1, 3, 7, 14, 30, 60, 90, 180, 365 d) with 95 % CI
│   │   ├── quantile_response.png            # mean ± 95 % bootstrap CI of commits per metric quantile
│   │   ├── lag.png                          # lag-correlation profile
│   │   ├── lag_heatmap.png                  # lag × window grid (Spearman)
│   │   ├── mi_lag.png                       # mutual-information vs lag (binned + KSG reference)
│   │   ├── distribution.png                 # commits log-y + metric hist
│   │   ├── monthly.png                      # monthly bars + metric overlay
│   │   ├── ccf.png                          # CCF with Bartlett ±95 % envelope
│   │   ├── acf_pacf.png                     # autocorrelation + partial autocorrelation
│   │   └── periodogram.png                  # Lomb–Scargle of commits + metric
│   ├── mosaic.png                           # graphical abstract (also .svg)
│   └── mosaic_index.json                    # source files referenced by the mosaic
│
│   # Mosaic layout (top → bottom):
│   #   1. Banner — title, period, Σ commits, top |ρ|.
│   #   2. Solar context — full-width commits_and_solar.png.
│   #   3. Cross-metric overview — correlation matrix, stacked panel,
│   #      seasonal calendar, DOW response, z-overview, lag grid, ACF/PACF,
│   #      periodogram.
│   #   4. Per-metric juxtaposition — one row per metric, 15 tile types
│   #      (timeline → distribution → response → MA-correlation → lag &
│   #       MI → causality → spectra).
│   #   5. Per-repo breakdown — Spearman heatmap, top-N repos.
│   #   6. Multi-user comparison — only when --compare-users is set.
└── analysis/
    ├── summary.txt                          # human-readable per-run report
    ├── methods.md                           # data sources + statistics methodology
    ├── per_repo_summary.csv                 # repo × metric Spearman + FDR flag
    ├── multi_user_associations.csv          # only if --compare-users …
    └── tables/                              # plaintext CSVs, one per analysis
        ├── README.md                        # schema reference
        ├── associations.csv                 # per-metric Pearson/Spearman/Kendall + CIs
        ├── lag_profile.csv                  # per-metric lag-by-lag rho + p + per-lag FDR flag
        ├── ccf_profile.csv                  # per-metric lag-by-lag CCF + Bartlett crossing flag
        ├── ma_correlations.csv              # per-metric × MA-window r/ρ + CIs
        ├── mi_lag.csv                       # per-metric × lag MI in nats
        ├── mutual_information.csv           # per-metric MI summary (binned/MM + KSG)
        ├── regression_ols.csv               # per-metric OLS R²/DW/normality
        ├── partial_correlation_ar1.csv      # per-metric AR(1)-controlled partials
        ├── cross_metric_spearman.csv        # square Spearman matrix
        ├── periodogram_top.csv              # top-5 LS peaks per series
        ├── spectral_band_power.csv          # named LS period-band power fractions
        ├── commits_daily_summary.csv        # one-row commit activity stats
        ├── per_repo_topk.csv                # top-K |ρ| repo×metric pairs (FDR)
        ├── multi_user_topk.csv              # only if --compare-users …
        └── cohort_user_summary.csv          # cohort only: one row per login
```

`statistics/report.json` carries:

- `commits_summary` — daily-grain commit stats: `total_days`, `days_with_commits`,
  `active_days_fraction`, `first_commit_date`, `last_commit_date`,
  `mean_per_day`, `mean_per_active_day`, `median_per_day`, `std_per_day`,
  `p95_per_day`, `max_day` + `max_day_date`,
  `longest_active_streak_days`, `longest_quiet_streak_days`,
  `dow_means_mon_to_sun` (7-vector), `weekday_total/share/mean`,
  `weekend_total/share/mean`, and a nested `dow_response` block with
  the values shown in `overview/dow_response.png`.
- `metrics[m].associations` — Pearson/Spearman/Kendall (value, p).
- `metrics[m].pearson_ci95` — Fisher-z 95 % CI.
- `metrics[m].spearman_ci95` — Bonett–Wright Fisher-z CI for Spearman ρ.
- `metrics[m].bootstrap_ci95` — percentile bootstrap CI when `--bootstrap N` > 0.
- `metrics[m].lag` — `best_lag`, `best`, `profile_p_min`, `profile_p_min_lag`.
- `metrics[m].lag_fdr_significant_count` — BH-FDR significant lag count.
- `metrics[m].lag_profile` — one row per scanned lag: `lag_days`, `rho`,
  `p`, and `fdr_significant`.
- `metrics[m].ccf` — CCF method, `prewhiten` flag, `n_eff`, Bartlett ±95 % band, `peak_lag`, `peak_value`.
- `metrics[m].ccf_profile` — one row per CCF lag, including whether the
  coefficient crosses the Bartlett band.
- `metrics[m].ma_correlations` — list of `{window, n, n_eff, pearson_r/lo/hi/p, spearman_rho/lo/hi/p}` rows
  for the smoothing windows `[1, 3, 7, 14, 30, 60, 90, 180, 365]` days. `n_eff = n // window` is a
  Bartlett-style independence proxy useful for interpreting `p` after smoothing.
- `metrics[m].partial_correlation_ar1` — Pearson and Spearman partial correlations of `commits` vs
  `metric` controlling for one-day lags of both series (a coarse but cheap autocorrelation control).
- `metrics[m].mutual_information` — `binned_nats` (Miller–Madow corrected),
  `binned_normalised` ∈ [0, 1], `binned_bins`, `ksg_nats` (KSG-1, k=5), `n`.
  See [`docs/methods/mutual_information.md`](../docs/methods/mutual_information.md).
- `metrics[m].mi_lag` — `lags`, `values_nats`, `n_per_lag`, `best_lag`,
  `best_value_nats`, `method`, `bins_or_k` — MI vs integer day-lag, the
  nonlinear analogue of the lag-correlation curve.
- `metrics[m].regression_ols` — OLS coefficients (`b0`, `b1`), `r2`,
  `sigma2`, Pearson r/CI/p, **Durbin–Watson** for residual AR(1), and
  D'Agostino-Pearson **omnibus normality** (`normality_stat`, `normality_p`).
- `metrics[m].dominant_period_days` and `metrics[m].periodogram_top5` — Lomb–Scargle peaks.
- `commits_dominant_period_days` and `commits_periodogram_top5` — periodogram peaks for the daily commit series.
- `metrics[m].spectral_band_power` and `commits_spectral_band_power` —
  Lomb–Scargle power fractions in weekly, solar-rotation, annual, and
  solar-cycle period bands.
- `cross_metric_correlation` — pairwise Spearman across requested metrics + commits.
- `per_repo_topk` — top 10 repos by |ρ| with FDR flag.
- `multi_user_topk` — top 10 (user, metric) pairs by |ρ| (only when `--compare-users`).
- `cohort_user_summary` — one row per login for cohort runs.

Override the run root with `--out`. Pass `--no-mosaic` to skip the graphical
abstract; `--rolling-window N` and `--lag-max N` adjust the rolling-correlation
window (days) and the lag search range. Statistics depth: `--bootstrap N`,
`--no-prewhiten`, `--top-repos N`, `--no-acf`, `--no-spectral`. Plot styling:
`--font-scale`, `--line-width`, `--dpi`, `--theme`.
