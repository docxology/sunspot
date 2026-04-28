# `sunspot` package

Typer CLI in `cli.py` with two entry points (`correlate`, `cohort`),
orchestration in `correlate/` / `cohort.py`, with subpackages for data
ingest, GitHub, alignment, statistics, tables, and plotting.

## Layout

| path | role |
|------|------|
| `cli.py` | `sunspot` console script (`sunspot correlate …`, `sunspot cohort …`) |
| `correlate/` | Single-user pipeline (`pipeline.run_correlation_report`): join commits with geophysical series; write report, `data/commits/`, per-metric tree, summaries, plots, mosaic (see `correlate/AGENTS.md`) |
| `config.py` | Env helpers + defaults consumed by CLI, `datasets.cache`, `github`, `viz.style` |
| `cohort.py` + `cohort_presets.py` | Multi-user–only pipeline (`report_kind="cohort"`): no per-metric deep dive, adds cohort PCA / dendrogram / weekly heatmap |
| `tables.py` | Plaintext CSV sidecars under `analysis/tables/` (one per statistical block) + schema `README.md` |
| `logutil.py` | Logger setup (`sunspot` logger, `--log-level` / `SUNSPOT_LOG_LEVEL`) |
| `datasets/` | SILSO, NOAA SWPC, OMNI2 fetch/parse with on-disk URL cache + in-memory OMNI2 daily cache |
| `github/` | GitHub REST client, commit iteration, SQLite dedup DB, per-repo commit-series cache |
| `align/` | `join_on_dates`, `zscore`, `clip_to_window`, `to_daily_dataframe` |
| `stats/` | Associations + CIs + bootstrap, CCF / ACF / PACF, partial correlation, Durbin-Watson, lag×window grid, Lomb-Scargle periodogram + `band_power`, mutual information (binned-MM + KSG), per-repo + multi-user + cohort PCA / dendrogram |
| `viz/` | `PlotStyle`, per-metric / overview / per-repo / dynamics / multi-user / cohort plots, mosaic + executive summary |

## Public API

- `sunspot.correlate.run_correlation_report` — single-user orchestrator.
- `sunspot.correlate.default_correlate_dir` — canonical output path.
- `sunspot.cohort.run_cohort_report` — multi-user orchestrator.
- `sunspot.cohort.default_cohort_dir` — cohort output path.
- `sunspot.cohort_presets.expand_preset` — named login bundles.
- Dataset loaders in `sunspot.datasets` (`load_silso_daily_tot_v2`,
  `load_omni2_daily`, `load_noaa_daily_solar_indices`).
- `sunspot.github.commits.public_commit_time_series`,
  `sunspot.github.commits.first_commit_date`.
- `sunspot.tables.write_analysis_tables` — one tidy CSV per statistical block.
- `sunspot.viz.set_style` / `sunspot.viz.PlotStyle` — global plot configuration.
- `sunspot.viz.assemble_mosaic`, `sunspot.viz.save_executive_summary`.
