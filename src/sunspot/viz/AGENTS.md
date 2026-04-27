# AGENTS — `viz`

`matplotlib` backend is set to `Agg` on import (CI / server-safe). All plotting
functions accept an optional `style: PlotStyle | None` and `period:
(date|None, date|None) | None`. Without arguments they use the **module-global**
style (see `style.py`).

## `style.py`

| name | kind | signature / description |
|------|------|-------------------------|
| `PlotStyle` | dataclass | `font_scale`, `line_width`, `dpi`, `theme {'light','dark'}`, `palette`, `title_size`, `label_size`, `tick_size`, `legend_size`, `grid`, `show_metadata_footer` (immutable; use `replace(...)` or `set_style(**)`) |
| `get_style()` | function | current global `PlotStyle` |
| `set_style(**overrides)` | function | mutate the global style and re-apply `rcParams`; returns the new style |
| `apply_rcparams(style)` | function | push `font_scale`, `line_width`, palette and theme into `matplotlib.rcParams` |
| `period_label(start, end)` | function | `"YYYY-MM-DD → YYYY-MM-DD"` |
| `metadata_footer(fig, parts, *, style=None)` | function | bottom-right metadata strip (period, n, prewhiten, …) |
| `PALETTE_LIGHT`, `PALETTE_DARK` | tuple[str,...] | default qualitative palettes |

Defaults (tuned for tile-in-mosaic readability): `font_scale=1.45`,
`line_width=1.9`, `dpi=300`, `theme='light'`. Environment overrides at import
time: `SUNSPOT_FONT_SCALE`, `SUNSPOT_LINEWIDTH`, `SUNSPOT_DPI`, `SUNSPOT_THEME`.
The CLI passes the same defaults unless the user overrides them.

### Significance helpers (`plots.py` private)

| name | returns |
|------|---------|
| `_significance_stars(p)` | `'***'` (p<.001), `'**'` (<.01), `'*'` (<.05), `'·'` (<.10), `'ⁿˢ'` otherwise; `''` when p is None/NaN |
| `_p_label(p)` | compact `'p=0.012 *'` badge text (or `'p<1e-03 ***'` for very small p) |

These are appended to coefficient labels (`r`, `ρ`, `τ`) in scatter / regression
titles, drawn as a corner badge in scatter / regression, used to highlight
`p<.05` lags as ringed dots in `save_lag_plot`, and used to mark CCF peaks
crossing the Bartlett band.

## `plots.py`

| function | output |
|----------|--------|
| `save_dual_axis(commits, solar, *, out, right_label, period=None, style=None)` | per-metric `dual_axis.png` |
| `save_scatter(commits, solar, *, out, metric_label, period=None, style=None)` | per-metric `scatter.png` (title carries `r/ρ/τ` with significance stars; OLS line skipped on constant axis; hexbin density when n > 500; bottom-right `p=…` badge) |
| `save_lag_plot(LagResult, *, out, metric_label, period=None, style=None)` | per-metric `lag.png` (peak line annotated with significance stars; individual `p<.05` lags ringed; title reports the count of significant lags) |
| `save_mi_lag_curve(commits, metric, *, out, metric_label, max_lag=30, method='binned', bins='fd', k=5, period=None, style=None) -> dict` | per-metric `mi_lag.png` (mutual-information vs integer day-lag; returns `{lags, values_nats, n_per_lag, best_lag, best_value_nats, method, bins_or_k}`) |
| `save_regression(commits, metric, *, out, metric_label, period=None, style=None)` | per-metric `regression.png` (OLS, 95 % CI band, residual hist inset; title carries `r` + significance stars; bottom-right `p=…` badge) |
| `save_rolling_corr(commits, metric, *, out, window=90, metric_label, period=None, style=None)` | per-metric `rolling_corr.png` (Pearson + Spearman + shaded `±1.96/√window` significance band; title reports `n_sig/n_windows` with `|r|` above the band) |
| `save_lag_heatmap(commits, metric, *, out, lags, windows, metric_label, period=None, style=None)` | per-metric `lag_heatmap.png` (median rolling Spearman over lag×window grid) |
| `save_distribution(commits, metric, *, out, metric_label, period=None, style=None)` | per-metric `distribution.png` (commits log-y; metric linear) |
| `save_monthly(commits, metric, *, out, metric_label, period=None, style=None)` | per-metric `monthly.png` (commits / month bars + metric monthly mean) |
| `save_ccf(commits, metric, *, out, max_lag=60, method='pearson', prewhiten=True, metric_label, period=None, style=None) -> CCFResult` | per-metric `ccf.png` (Bartlett ±95 % envelope; AR(1)-pre-whitened by default; peak label + title report whether the peak crosses the band and how many lags do) |
| `save_acf_pacf(series, *, out, n_lags=60, label, period=None, style=None)` | per-metric `acf_pacf.png` (autocorrelation + partial autocorrelation) |
| `save_periodogram(commits, metric, *, out, label_a='commits', label_b, period=None, style=None) -> dict[str, Periodogram]` | per-metric `periodogram.png` (Lomb–Scargle, marker lines at 7 d / 27 d / 1 yr / 11 yr) |
| `save_quantile_response(commits, metric, *, out, metric_label, n_bins=10, period=None, style=None)` | per-metric `quantile_response.png` (mean ± 95 % bootstrap CI of commits by metric quantile, with bin-count bars) |
| `save_joint_density(commits, metric, *, out, metric_label, period=None, style=None)` | per-metric `joint_density.png` (hexbin density + marginal histograms; OLS line + Pearson r/CI/p in title) |
| `save_ma_correlation_curve(commits, metric, *, out, metric_label, windows=None, period=None, style=None) -> list[dict]` | per-metric `ma_corr_curve.png` (Pearson r and Spearman ρ of MA(commits) vs MA(metric) over `windows ∈ [1,3,7,14,30,60,90,180,365] d`, log-x; Fisher-z and Bonett–Wright 95 % CI bands; significance stars per window). Returns the per-window rows so the caller can persist them in `report.json`. |
| `save_dow_response(commits, metric=None, *, out, metric_label=None, period=None, style=None) -> dict` | `overview/dow_response.png` (bar chart of mean commits by Mon..Sun + weekday/weekend reference lines; with `metric`, adds a DOW × metric-tercile mean-commits heatmap). Returns `{dow_means, dow_counts, weekday_mean, weekend_mean}`. |
| `save_metric_correlation_matrix(frame, *, out, method='spearman', period=None, style=None)` | `overview/metric_correlation_matrix.png` |
| `save_metrics_zscored_overview(commits, frame, *, out, ma_window=30, period=None, style=None)` | `overview/metrics_zscored_overview.png` |
| `save_stacked_panel(commits, metrics_frame, *, out, ma_window=30, period=None, style=None)` | `overview/stacked_panel.png` (commits MA on top, one panel per metric, shared x-axis; per-panel Pearson r vs commits annotated) |
| `save_seasonal_calendar(commits, *, out, solar=None, solar_label='SSN', period=None, style=None)` | `overview/seasonal_calendar.png` (year × DOY commit heatmap; optional annual-mean solar bar strip on top) |
| `save_lag_grid(lag_results, *, out, period=None, style=None)` | `overview/lag_grid.png` |
| `save_top_repos_ma(commits_by_repo, solar, *, out, top_n=8, window=30, period=None, style=None)` | `per_repo/top_repos_30d_ma.png` |
| `save_repo_metric_spearman_heatmap(per_repo_df, *, out, metric_order, top_n=30, period=None, style=None)` | `per_repo/repo_metric_spearman_heatmap.png` (FDR-significant marked) |
| `save_commits_solar_dynamics(commits, ssn, f107, *, out, title, period=None, style=None)` | `dynamics/commits_and_solar.png` |
| `save_compare_users_moving_averages(user_series, solar, *, out, window=30, period=None, style=None)` | `dynamics/compare_users_30d_ma.png` |

## `multi_user.py`

| function | output |
|----------|--------|
| `save_multi_user_overview(users_commits, solar, *, out, window=30, period=None, style=None)` | `multi_user/overview_30d_ma.png` |
| `save_multi_user_heatmap(long_df, *, out, metric_order=None, period=None, style=None)` | `multi_user/user_metric_spearman_heatmap.png` (FDR-significant cells ringed) |
| `save_multi_user_rank_matrix(users_commits, *, out, smoothing_window=30, method='spearman', period=None, style=None)` | `multi_user/user_user_rank_matrix.png` |
| `save_multi_user_cumulative(users_commits, solar, *, out, period=None, style=None)` | `multi_user/cumulative_vs_solar.png` |
| `save_multi_user_phase(users_commits, ssn, *, out, period=None, style=None)` | `multi_user/phase_by_ssn_quantile.png` |

## `cohort.py`

| function | output |
|----------|--------|
| `save_cohort_pca_scatter(pca, *, out, period=None, style=None)` | `cohort/user_pca_scatter.png` |
| `save_cohort_dendrogram(users_commits, *, out, period=None, style=None)` | `cohort/user_dendrogram.png` |
| `save_cohort_timeseries_heatmap(users_commits, *, out, max_cols=260, period=None, style=None)` | `cohort/user_weekly_heatmap.png` |
| `save_cohort_user_summary(user_summary, *, out, period=None, style=None)` | `cohort/user_summary.png` |

## `mosaic.py`

- `save_executive_summary(out_root, *, out=None) -> Path` — one-page PNG "executive summary" card summarizing `statistics/report.json` (headline counts, top associations, dominant period, AR(1) partials). Exported as `visualizations/executive_summary.png` by the correlate pipeline.
- `save_cohort_executive_summary(out_root, *, out=None) -> Path` — cohort counterpart (headline users + cross-user structure).
- `assemble_cohort_mosaic(out_root) -> Path` — compact cohort mosaic (no per-metric tree), saved at the active `PlotStyle.dpi`.
- `assemble_mosaic(out_root, *, metrics=None, mosaic_name='mosaic.png', write_svg=True) -> Path` — packs PNGs already under `visualizations/` into a hierarchical figure. Writes `visualizations/mosaic.png` (saved at the active `PlotStyle.dpi`) plus an SVG twin and `visualizations/mosaic_index.json`. Missing tiles render as labelled blank panels and are excluded from the index. Tiles use `aspect='equal'` (no stretching) — cells with mismatched proportions get neutral whitespace padding rather than distorted content. Per-cell footprint is `cell_w=4.2"` × source-image-aspect.
- Banner content (title / period / Σ commits / top |ρ|) is read from `statistics/report.json`; if the file is unreadable a generic title is used. The banner also carries the significance-stars legend (`*** p<.001  ** p<.01  * p<.05  · p<.10  ⁿˢ otherwise`) so the per-tile annotations are self-explanatory.
- Layout (top → bottom):
  1. **Banner** (filled rectangle, white text on Anthropic-blue).
  2. **Solar context** — full-width `dynamics/commits_and_solar.png`.
  3. **Cross-metric overview** — two split rows: (`metric_correlation_matrix`, `stacked_panel`, `seasonal_calendar`, `dow_response`) above (`metrics_zscored_overview`, `lag_grid`, `commits_acf_pacf`, `commits_periodogram`).
  4. **Per-metric juxtaposition** — one row per metric. Tile order (left → right) is `PER_METRIC_TILES = ('dual_axis','scatter','joint_density','regression','rolling_corr','ma_corr_curve','quantile_response','distribution','lag','lag_heatmap','ccf','monthly','acf_pacf','periodogram')`. The metric name is written vertically on the left edge of the row.
  5. **Per-repo** — `repo_metric_spearman_heatmap`, `top_repos_30d_ma`.
  6. **Multi-user** (when present) — `overview_30d_ma`, `user_metric_spearman_heatmap`, `user_user_rank_matrix`, `cumulative_vs_solar`, `phase_by_ssn_quantile`.
