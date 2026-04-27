# AGENTS — `tests`

All tests run offline (no network) unless marked `@pytest.mark.integration`.
Parsers exercise **real** dataset snippets in `fixtures/`, not hand-rolled mock
numbers, so format regressions surface as failed parses instead of silent drift.

## Inventory

| file | focus |
|------|-------|
| `test_silso_parse.py`       | `_parse_silso_csv` on `fixtures/silso_snippet.csv` (SILSO V2.0 semicolon format) |
| `test_noaa_parse.py`        | `_parse_daily_solar_indices` on SWPC DSD-style rows |
| `test_omni_parse.py`        | `_parse_omni2_hourly_line` + `_parse_omni2_hourly_lines` → daily resample (`fixtures/omni2_oneline.txt`) |
| `test_github_model.py`      | `_commit_dt` on `fixtures/github_commit.json`; `first_commit_date` across search-commits / `/users` fallback / both-fail; `iter_commits` request scoping via `httpx.MockTransport` |
| `test_github_client_cache.py` | `github_token` / `github_headers` / `default_sqlite_path` env handling; `commit_series_cache_path` + `save_/try_load_commit_series` round-trip (sanitized segments, meta JSON, cache-miss path) |
| `test_datasets_cache.py`    | `default_cache_dir` / `cache_path_for_url` / `ensure_cached_url` + `read_text_cached` with an `httpx.MockTransport`; HTTP 404 surfaces; `default_correlate_dir` + `default_cohort_dir` slug shape |
| `test_cli_defaults.py`      | Typer `CliRunner`: `--since` defaults via monkeypatched `first_commit_date`, `--until` defaults to today, swapped-dates rejection, unresolvable-`--since` error text, cohort logging flags |
| `test_logging.py`           | `parse_log_level`; `configure_sunspot_logging` idempotent level change |
| `test_align.py`             | `to_daily_dataframe` (naming + empty), `join_on_dates` (outer union, unnamed fallback, sort), `zscore` (constant + centering), `clip_to_window` (inclusive bounds, None-unbounded, dtype preservation) |
| `test_stats.py`             | `association_metrics`, `lag_correlation_search`, `rolling_pearson`, `fdr_on_pvalues` baseline |
| `test_stats_extras.py`      | `pearson_with_ci` vs scipy; constant-input NaN; `lag_window_grid`; `cross_metric_corr_matrix` symmetry; `moving_average_correlation_curve` recovering signal + FDR flag on a synthetic cohort |
| `test_stats_deeper.py`      | `spearman_with_ci`; `bootstrap_corr_ci` brackets point; `ar1_prewhiten` reduces AR(1); `cross_correlation_function` finds engineered lag; `partial_correlation` removes common driver; `multi_user_associations` / `multi_user_rank_matrix`; `cohort_dendrogram_leaves` excludes flat users |
| `test_stats_primitives.py`  | Direct `acf_values` / `pacf_values` including AR(1) spike shape; `ar1_prewhiten` short-series + constant edge cases; `partial_correlation` with empty controls; `durbin_watson` white-noise / positive-AR1 / negative-AR1 / constant / Series; `band_power` concentration, argument-order invariance, empty periodogram |
| `test_spectral.py`          | Lomb–Scargle recovers a 27 d sinusoid; constant input → empty result |
| `test_information.py`       | Binned + KSG MI on linked / independent series; constant / too-few / normalised edge cases; MI lag curve |
| `test_tables.py`            | `write_analysis_tables` emits expected files with correct schemas, including lag/CCF profile flags, spectral band power, and cohort user summary; empty report still writes README |
| `test_viz.py`               | PNG write smoke for `save_scatter` / `save_lag_plot` |
| `test_viz_extras.py`        | PNG write smoke for regression / rolling_corr / lag_heatmap / distribution / monthly / overview matrix / z-overview / lag_grid / per-repo |
| `test_style_and_new_plots.py` | `PlotStyle` / `set_style` / `period_label`; CCF / ACF-PACF / periodogram / multi-user bundle / quantile_response / joint_density / seasonal_calendar / stacked_panel / ma_corr_curve / dow_response / regression diagnostics / mi_lag |
| `test_mosaic.py`            | `assemble_mosaic` indexes all sections; `save_executive_summary` renders a card from a synthetic report |
| `test_correlate_offline.py` | End-to-end `run_correlation_report` with commits monkeypatched to a zero series; asserts full artifact tree, per-metric tables, multi-user tree when `compare_user_logins` is set |
| `test_cohort_offline.py`    | `expand_preset` returns non-empty; `run_cohort_report` end-to-end with commits + metrics mocked (cohort PCA, dendrogram, user-metric heatmap, mosaic) |

## Fixtures

`fixtures/silso_snippet.csv`, `fixtures/omni2_oneline.txt`, `fixtures/github_commit.json`.
