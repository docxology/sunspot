# AGENTS — `src/sunspot`

## Entry points

- `sunspot.cli:main` — Typer app (`sunspot correlate …`).
- `sunspot.correlate.run_correlation_report(user, *, since, until, metrics, out_dir, use_commit_cache=True, compare_user_logins=None, rolling_window=90, lag_max=60, bootstrap=0, prewhiten=True, top_repos=8, enable_acf=True, enable_spectral=True, make_mosaic=True, style_overrides=None) -> dict` — writes `statistics/`, `data/`, `visualizations/`, `analysis/` under `out_dir` and returns the report dict.
- `sunspot.cohort.run_cohort_report(logins, *, since, until, metrics, out_dir, use_commit_cache=True, make_mosaic=True, style_overrides=None, since_policy=None, min_active_days=30, large_cohort=False) -> dict` — *among-user only* (`report_kind: cohort`). Full mode: `data/commits/`, `visualizations/cohort/` (PCA, dendrogram, heatmaps, per-metric **correlation distribution** histograms + one-row-per-user CSVs), `visualizations/multi_user/`, `dynamics/`, `mosaic`. **`large_cohort`**: skip O(n²) user×user block and most structural cohort PNGs; keep full-login `multi_user_associations.csv` + histograms + `user_activity_scatter.png`. `read_logins_file` parses login list files. See `docs/large_cohort.md`.
- `sunspot.correlate.default_correlate_dir(user, since, until)` — `Path("output") / "correlate" / f"{user}__{since}__{until}"`.
- `sunspot.cohort.default_cohort_dir(n_users, since, until)` — `Path("output") / "correlate" / f"cohort_n{n}__{since}__{until}"`.

## Modules

| module | purpose |
|--------|---------|
| `cli.py` | `cmd_correlate` with `--since` (optional; defaults to the user's first commit date via `github.commits.first_commit_date`, falling back to the GitHub account `created_at`), `--until` (optional; defaults to today UTC), `--metrics`, `--out`, `--log-level`, `-v`, `--quiet`, `--no-commit-cache`, `--compare-users`, `--rolling-window`, `--lag-max`, `--bootstrap`, `--no-prewhiten`, `--top-repos`, `--no-acf`, `--no-spectral`, `--no-mosaic`, `--font-scale`, `--line-width`, `--dpi`, `--theme`. Configures logging first, then resolves the date window, then sets the global `viz.PlotStyle` from style flags. Rejects `--since > --until`. |
| `logutil.py` | `configure_sunspot_logging`, `parse_log_level` (handler on logger `sunspot`, stderr). |
| `correlate/` | Package: `pipeline.run_correlation_report`, `default_correlate_dir` in `_io.py`. See [`correlate/AGENTS.md`](correlate/AGENTS.md). Same orchestration scope as the former monolithic `correlate.py` (commits → stats → per-metric / overview / per-repo / multi-user artifacts, `tables`, mosaic, `statistics/report.json`). |
| `config.py` | Env names and defaults: `dataset_cache_dir`, `github_token_from_env`, `sqlite_parent_dir_from_env`, `commit_series_root_from_env`, `read_plot_style_env`, `sunspot_log_level_env_raw`. Documented in `docs/configuration.md`. |
| `tables.py` | `write_analysis_tables(report, analysis_dir, *, lag_results=None, ccf_results=None) -> list[Path]` — emits one tidy CSV per statistical block under `analysis/tables/` plus a `README.md` schema reference. |
| `__init__.py` | Exports `__version__` only. |

## Subpackages

- `align/` — `join_on_dates`, `zscore`, `clip_to_window`, `to_daily_dataframe`.
- `datasets/` — SILSO + OMNI2 readers; on-disk URL cache + in-memory OMNI2 daily cache.
- `github/` — Public commit retrieval; on-disk per-repo commit-series cache + SQLite SHA dedup DB.
- `stats/` — Associations + Fisher-z / Bonett–Wright / bootstrap CIs, lag search, CCF (Bartlett bands, AR(1) pre-whitening), ACF/PACF, partial correlation, `durbin_watson`, rolling Pearson, lag×window grid, cross-metric matrix, BH-FDR, Lomb–Scargle periodogram + `band_power`, mutual information (binned-MM + KSG + MI-lag), per-repo associations, multi-user associations + rank matrix + cohort PCA / dendrogram.
- `viz/` — Centralised `PlotStyle`; per-metric, overview, per-repo, dynamics, multi-user, and cohort plots; `mosaic.assemble_mosaic`, `mosaic.assemble_cohort_mosaic`, `mosaic.save_executive_summary`, `mosaic.save_cohort_executive_summary`.

## Tests

- `tests/test_correlate_offline.py` — monkeypatches `correlate.public_commit_time_series`; geophysical data is fetched from OMNI2 (network on first run, cached afterwards). Asserts new artifacts (mosaic, methods, summary, overview, per-metric, CCF/ACF/periodogram, multi-user).
- `tests/test_cli_defaults.py` — Typer `CliRunner` exercises the default-resolution paths for `--since` (mocked `first_commit_date`) and `--until` (today), and asserts the swapped-dates and unresolvable-`--since` error messages.
- `tests/test_github_model.py` — `_commit_dt` against an API fixture and `httpx.MockTransport` tests for `first_commit_date`'s search-API path, account `created_at` fallback, and `None`-on-failure behaviour.
- `tests/test_stats_extras.py`, `tests/test_stats_deeper.py`, `tests/test_spectral.py` — synthetic-data unit tests for correlation, CCF, ACF/PACF, partial correlation, AR(1) pre-whitening, multi-user statistics, and the Lomb–Scargle periodogram.
- `tests/test_viz_extras.py`, `tests/test_style_and_new_plots.py`, `tests/test_mosaic.py` — synthetic-data unit tests for the styling system, the per-metric / multi-user plots, and the mosaic assembly.
