# AGENTS — `src/sunspot`

## Entry points

- `sunspot.cli:main` — Typer app (`sunspot correlate …`).
- `sunspot.correlate.run_correlation_report(user, *, since, until, metrics, out_dir, use_commit_cache=True, compare_user_logins=None, rolling_window=90, lag_max=60, bootstrap=0, prewhiten=True, top_repos=8, enable_acf=True, enable_spectral=True, make_mosaic=True, style_overrides=None) -> dict` — writes `statistics/`, `data/`, `visualizations/`, `analysis/` under `out_dir` and returns the report dict.
- `sunspot.cohort.run_cohort_report(logins: list[str], *, since, until, metrics, out_dir, use_commit_cache=True, make_mosaic=True, style_overrides=None) -> dict` — *among-user only* (`report_kind: cohort`): `data/commits/` (`daily.csv` = sum across users, `daily_users_wide.csv`, `user_summary.csv`, `by_user/`), `visualizations/cohort/` (PCA, dendrogram, weekly heatmap, user summary), `visualizations/multi_user/`, `visualizations/dynamics/compare_users_30d_ma.png`, compact `mosaic.png`; **no** `visualizations/{ssn,f107,…}/` per-metric tree, no per-repo.
- `sunspot.correlate.default_correlate_dir(user, since, until)` — `Path("output") / "correlate" / f"{user}__{since}__{until}"`.
- `sunspot.cohort.default_cohort_dir(n_users, since, until)` — `Path("output") / "correlate" / f"cohort_n{n}__{since}__{until}"`.

## Modules

| module | purpose |
|--------|---------|
| `cli.py` | `cmd_correlate` with `--since` (optional; defaults to the user's first commit date via `github.commits.first_commit_date`, falling back to the GitHub account `created_at`), `--until` (optional; defaults to today UTC), `--metrics`, `--out`, `--log-level`, `-v`, `--quiet`, `--no-commit-cache`, `--compare-users`, `--rolling-window`, `--lag-max`, `--bootstrap`, `--no-prewhiten`, `--top-repos`, `--no-acf`, `--no-spectral`, `--no-mosaic`, `--font-scale`, `--line-width`, `--dpi`, `--theme`. Configures logging first, then resolves the date window, then sets the global `viz.PlotStyle` from style flags. Rejects `--since > --until`. |
| `logutil.py` | `configure_sunspot_logging`, `parse_log_level` (handler on logger `sunspot`, stderr). |
| `correlate.py` | Orchestrator. Loads commits via `github.commits.public_commit_time_series`, geo series via `datasets`; computes per-metric stats (`stats.correlation` + `stats.spectral` + `stats.information`), per-repo associations (`stats.per_repo`), and (if `compare_user_logins`) cross-user statistics (`stats.multi_user`); writes commit data under `data/commits/` (`daily.csv`, `weekly.csv`, `monthly.csv`, `dow_means.csv`, `summary.csv`, `manifest.json`, `by_repo/`, optional `by_user/`); writes per-metric tiles — `dual_axis`, `scatter`, `joint_density`, `regression`, `rolling_corr`, `quantile_response`, `distribution`, `lag`, `lag_heatmap`, `ccf`, `mi_lag`, `monthly`, `acf_pacf`, `periodogram` — overview tiles (`metric_correlation_matrix`, `metrics_zscored_overview`, `stacked_panel`, `seasonal_calendar`, `lag_grid`, `commits_acf_pacf`, `commits_periodogram`), per-repo, dynamics, and multi-user PNGs, plus the `viz.mosaic.assemble_mosaic` graphical abstract; emits `analysis/summary.txt`, `analysis/methods.md`, `analysis/per_repo_summary.csv`, `analysis/multi_user_associations.csv`, `analysis/tables/*.csv` (one per analysis), `statistics/report.json` with full lag/CCF profiles and spectral band-power summaries. |
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
