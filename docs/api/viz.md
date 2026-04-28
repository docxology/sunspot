# `sunspot.viz`

Non-interactive Matplotlib; backend `Agg` in modules. All plotting functions
accept an optional `style: PlotStyle | None` (defaults to the module-global
style) and `period: (date|None, date|None) | None` (drives the metadata footer).

## `style` ([`style.py`](../../src/sunspot/viz/style.py))

| name | role |
|------|------|
| `PlotStyle` | Frozen dataclass: `font_scale`, `line_width`, `dpi`, `theme {'light','dark'}`, `palette`, optional explicit `title_size`, `label_size`, `tick_size`, `legend_size`, `grid`, `show_metadata_footer`. |
| `get_style() -> PlotStyle` | Current global style. |
| `set_style(**overrides) -> PlotStyle` | Mutate the global style and re-apply `rcParams`. |
| `apply_rcparams(style)` | Push fonts, line width, palette and theme into `rcParams`. |
| `period_label(start, end) -> str` | `"YYYY-MM-DD → YYYY-MM-DD"` (or empty). |
| `metadata_footer(fig, parts, *, style=None)` | Bottom-right metadata line (period, n, prewhiten, …). |
| `PALETTE_LIGHT`, `PALETTE_DARK` | Default qualitative palettes. |

Environment overrides at import time:
`SUNSPOT_FONT_SCALE`, `SUNSPOT_LINEWIDTH`,
`SUNSPOT_DPI`, `SUNSPOT_THEME`.

## `plots` ([`plots.py`](../../src/sunspot/viz/plots.py))

| function | role |
|----------|------|
| `save_dual_axis(commits, solar, *, out, right_label, period=None, style=None)` | Commits (left) vs z-scored series (right). |
| `save_scatter(commits, solar, *, out, metric_label, period=None, style=None)` | Scatter with regression line and r/ρ/τ in title; hexbin density when n > 500. |
| `save_regression(commits, metric, *, out, metric_label, period=None, style=None) -> dict` | OLS `commits ~ z(metric)` with 95 % band + residual inset. Returns coefficients, R², σ², Pearson r/CI/p, **Durbin–Watson** for residual AR(1), and **D'Agostino-Pearson** omnibus normality (`stat`, `p`); same diagnostics annotated on the plot. |
| `save_rolling_corr(commits, metric, *, out, window=90, metric_label, period=None, style=None)` | Rolling Pearson and Spearman overlay. |
| `save_lag_heatmap(commits, metric, *, out, lags=, windows=, metric_label, period=None, style=None)` | `lag_window_grid` heatmap (median rolling Spearman). |
| `save_distribution(commits, metric, *, out, metric_label, period=None, style=None)` | Commits log-y histogram + metric histogram. |
| `save_monthly(commits, metric, *, out, metric_label, period=None, style=None)` | Monthly commit totals + monthly metric mean. |
| `save_ccf(commits, metric, *, out, max_lag=60, method="pearson", prewhiten=True, metric_label, period=None, style=None) -> CCFResult` | Cross-correlation with Bartlett ±95 % envelope. |
| `save_acf_pacf(series, *, out, n_lags=60, label, period=None, style=None)` | Autocorrelation + partial autocorrelation panel. |
| `save_periodogram(commits, metric, *, out, label_a="commits", label_b, period=None, style=None) -> dict[str, Periodogram]` | Lomb–Scargle periodograms (commits + metric) with marker lines at 7 d / 27 d / 1 yr / 11 yr. |
| `save_quantile_response(commits, metric, *, out, metric_label, n_bins=10, period=None, style=None)` | Mean (and median) commits per metric quantile bin with 95 % bootstrap CI bars and bin-count bars. |
| `save_joint_density(commits, metric, *, out, metric_label, period=None, style=None)` | Joint hexbin density + marginal histograms for commits vs metric; OLS line and Pearson r/CI/p in title. |
| `save_metric_correlation_matrix(frame, *, out, method="spearman", period=None, style=None)` | Heatmap from `cross_metric_corr_matrix`. |
| `save_metrics_zscored_overview(commits, metrics_frame, *, out, ma_window=30, period=None, style=None)` | Commits MA + overlaid z(metrics). |
| `save_stacked_panel(commits, metrics_frame, *, out, ma_window=30, period=None, style=None)` | Vertical small-multiples: commit MA on top, one panel per metric, shared x-axis; per-panel Pearson r vs commits annotated. |
| `save_seasonal_calendar(commits, *, out, solar=None, solar_label="SSN", period=None, style=None)` | Year × DOY heatmap of commits with optional annual-mean solar bar strip on top — lets the eye drop from solar level into seasonal commit pattern. |
| `save_lag_grid(lag_results, *, out, period=None, style=None)` | Small-multiples Spearman lag curves. |
| `save_top_repos_ma(commits_by_repo, solar, *, out, top_n=8, window=30, period=None, style=None)` | Top repos MA vs z(solar). |
| `save_repo_metric_spearman_heatmap(per_repo_df, *, out, metric_order=, top_n=30, period=None, style=None)` | Repo × metric with FDR markers. |
| `save_commits_solar_dynamics(commits, ssn, f107, *, out, title, period=None, style=None)` | 7d/30d MA + z(SSN), z(F10.7). |
| `save_compare_users_moving_averages(user_series, solar, *, out, window=30, period=None, style=None)` | Multi-user MAs + z(solar). |
| `save_lag_plot(res, *, out, metric_label, period=None, style=None)` | Single lag profile. |
| `save_mi_lag_curve(commits, metric, *, out, metric_label, max_lag=30, method='binned'|'ksg', bins='fd', k=5, period=None, style=None) -> dict` | Mutual-information vs day-lag (binned + KSG reference); peak lag annotated. Returns the curve and the peak for `report.json`. |

## `multi_user` ([`multi_user.py`](../../src/sunspot/viz/multi_user.py))

| function | role |
|----------|------|
| `save_multi_user_overview(users_commits, solar, *, out, window=30, period=None, style=None)` | Per-user MA panel + z(solar). |
| `save_multi_user_heatmap(long_df, *, out, metric_order=None, period=None, style=None)` | User × metric Spearman heatmap with FDR-significant cells ringed. |
| `save_multi_user_rank_matrix(users_commits, *, out, smoothing_window=30, method="spearman", period=None, style=None)` | Pairwise user × user correlation matrix. |
| `save_multi_user_cumulative(users_commits, solar, *, out, period=None, style=None)` | Cumulative commits per user vs z(solar). |
| `save_multi_user_phase(users_commits, ssn, *, out, period=None, style=None)` | Mean commits per z(SSN) quantile bin. |

## `cohort` ([`cohort.py`](../../src/sunspot/viz/cohort.py))

Cohort runs only; backend `Agg` like other viz modules. Uses [`cohort_correlation_dendrogram_data`](stats.md#multi_user) so users with no weekly variation are not fed to `pdist` (no file if a tree cannot be built).

| function | role |
|----------|------|
| `save_cohort_pca_scatter(pca, *, out, period=None, style=None)` | Users in PC1–PC2 space from `pca_users_weekly` output. |
| `save_cohort_dendrogram(users_commits, *, out, period=None, style=None)` | Average-linkage dendrogram; metadata may note how many logins were excluded. |
| `save_cohort_timeseries_heatmap(users_commits, *, out, max_cols=260, period=None, style=None)` | Weekly sums, per-user z-score, downsampled columns if long. |
| `save_cohort_user_summary(user_summary, *, out, period=None, style=None)` | Per-user total commits and active-day bars. |
| `save_correlation_distribution_histogram(mu_long, *, metric, out, out_csv, period=None, style=None) -> dict` | Histogram of per-user Spearman ρ for one metric; writes PNG + per-metric CSV; returns summary for `report.json`. |

## `mosaic` ([`mosaic.py`](../../src/sunspot/viz/mosaic.py))

| name | description |
|------|-------------|
| `PER_METRIC_TILES` | Tuple of per-metric PNG basenames drawn left → right per metric row: `dual_axis`, `scatter`, `joint_density`, `regression`, `rolling_corr`, `ma_corr_curve`, `quantile_response`, `distribution`, `lag`, `lag_heatmap`, `mi_lag`, `ccf`, `monthly`, `acf_pacf`, `periodogram`. |
| `save_executive_summary(out_root, *, out) -> Path` | Render a standalone executive-summary card from `statistics/report.json` (Pearson, Spearman, best lag, MA peak, partial r, MI / lag, R²·DW). |
| `assemble_mosaic(out_root, *, metrics=None, mosaic_name="mosaic.png", write_svg=True) -> Path` | Builds `visualizations/mosaic.png` (and optional `.svg`) from existing PNGs and writes `mosaic_index.json` with source paths. Layout: banner (title / period / Σ commits / top \|ρ\| read from `statistics/report.json`) → solar context → cross-metric overview (two split rows) → per-metric juxtaposition rows → per-repo strip → multi-user strip (when present). Tiles use `aspect='equal'` to preserve source image aspect. |
| `save_cohort_executive_summary(out_root, *, out) -> Path` | Requires `report_kind == "cohort"`; compact PNG from `statistics/report.json` (user table, top multi-user \|ρ\|, PCA variance). |
| `assemble_cohort_mosaic(out_root, *, mosaic_name="mosaic.png", write_svg=True) -> Path` | Cohort layout only: banner → cohort executive row → dynamics compare → cohort analytics row (PCA, dendrogram, heatmap) → `multi_user/` strip — no per-metric or per-repo sections. |
