# AGENTS — `src/sunspot/correlate`

Single-user **correlate** pipeline: `run_correlation_report` in `pipeline.py` orchestrates
GitHub commits, geophysical series, stats, plots, tables, and mosaic. Shared helpers used
by `cohort.py` live here as private exports from `__init__.py`.

| file | role |
|------|------|
| `__init__.py` | Re-exports `run_correlation_report`, `default_correlate_dir`, `public_commit_time_series` (for test monkeypatch), and `_write_*` / `_series_for_metric` / `_commits_daily_summary` / `_format_summary` |
| `_constants.py` | `SPECTRAL_BANDS_DAYS`, `OUTPUT_ROOT`, `DIR_*` path segments |
| `_io.py` | `default_correlate_dir`, per-repo / roll-up / per-user commit writers, `_write_methods` |
| `_series.py` | `_years_between`, `_series_for_metric` (SILSO + OMNI2) |
| `_report_helpers.py` | `_format_summary`, `_commits_daily_summary`, lag/CCF/spectral profile rows |
| `pipeline.py` | `run_correlation_report` — full artifact tree |

**Tests:** `tests/test_correlate_offline.py` (monkeypatched commits). `public_commit_time_series` is resolved at runtime via `import sunspot.correlate as _cor_mod` inside `run_correlation_report` so patches on the package attribute apply.

**Config reference:** [docs/configuration.md](../../../docs/configuration.md), [sunspot.config](../config.py).
