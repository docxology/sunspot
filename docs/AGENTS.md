# AGENTS — `docs/`

| path | content |
|------|---------|
| [`README.md`](README.md)                 | Human index: links to API and topic guides; high-level Mermaid map |
| [`configuration.md`](configuration.md) | Env vars and `src/sunspot/config.py` |
| [`large_cohort.md`](large_cohort.md) | Many-login cohort, `--logins-file`, distribution histograms |
| [`measures/`](measures/README.md)        | Per-dataset references (`ssn`, `f107`, `dst`, `ap`) — physics, source, cadence, pitfalls |
| [`methods/`](methods/README.md)          | Topical method notes (regression, correlation, time-lag, mutual information) |
| [`api/cli.md`](api/cli.md)               | Typer entry: `main`, `cmd_correlate` |
| [`api/correlate.md`](api/correlate.md)   | `run_correlation_report`, `default_correlate_dir`, run layout |
| [`api/cohort.md`](api/cohort.md)         | `run_cohort_report`, `default_cohort_dir`, `expand_preset`, multi-user output |
| [`api/logutil.md`](api/logutil.md)       | `configure_sunspot_logging`, `parse_log_level` |
| [`api/align.md`](api/align.md)           | `to_daily_dataframe`, `join_on_dates`, `zscore` |
| [`api/datasets.md`](api/datasets.md)     | Cache, SILSO, OMNI2, NOAA SWPC public loaders |
| [`api/github.md`](api/github.md)         | `client`, `commits`, per-repo commit series cache |
| [`api/stats.md`](api/stats.md)           | `Association`, `LagResult`, `MILagResult`, association/lag/rolling/FDR/MI APIs |
| [`api/viz.md`](api/viz.md)               | `save_*` plot writers, `assemble_mosaic`, `save_executive_summary` |

**Source of truth:** Runtime behavior lives in `src/sunspot/**/*.py`.
Agent-oriented tables in `src/**/AGENTS.md` should match public APIs.
When you add or change a public function, update the matching
`docs/api/*.md`, the relevant `AGENTS.md`, *and* — when the change
touches a dataset or a method — the matching page in
[`measures/`](measures/AGENTS.md) or [`methods/`](methods/AGENTS.md).

**Not duplicated here:** Project goals and ethics — [SPEC.md](../SPEC.md).
CLI quickstart and caching env vars — [README.md](../README.md).
