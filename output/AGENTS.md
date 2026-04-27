# AGENTS — `output/`

| path | content |
|------|---------|
| [`README.md`](README.md) | Full directory tree for `sunspot correlate` runs (statistics, data, visualizations, analysis) |

**Purpose:** Default run root for the CLI is `output/correlate/{user}__{since}__{until}/` (overridable with `--out`). The `output/` tree is typically **gitignored**; only this README and this file are meant to be versioned to document layout.

**Layout invariants:**

- `data/commits/` is the *only* place GitHub-derived series are written: `daily.csv`, `weekly.csv`, `monthly.csv`, `dow_means.csv`, `summary.csv`, `manifest.json`, `by_repo/{owner__repo}.csv`, plus `by_user/{login}.csv` when `--compare-users` is set.
- `data/{metric}/` carries the aligned daily series and rolling correlations for each requested metric.
- `analysis/tables/` mirrors every block in `statistics/report.json` as one CSV per analysis (associations, lag profile, CCF profile, MA correlations, MI lag, MI summary, regression diagnostics, partial correlations, cross-metric matrix, periodogram peaks, per-repo top-K, multi-user top-K). Schema: [`analysis/tables/README.md`](../src/sunspot/tables.py) (generated at run time).
- `analysis/summary.txt` is the human-readable rollup; `methods.md` documents data sources and the statistical pipeline.
- `visualizations/` is laid out so the mosaic can be rebuilt purely from disk: per-metric `{ssn,f107,dst,ap,…}/`, plus `dynamics/`, `overview/`, `per_repo/`, optional `multi_user/`, and the top-level `mosaic.png` + `mosaic_index.json` (and `executive_summary.png`).

**Pipeline:** [correlate.py](../src/sunspot/correlate.py) `run_correlation_report` writes all artifacts. Human index: [docs/api/correlate.md](../docs/api/correlate.md). Plaintext sidecar writer: [`sunspot.tables.write_analysis_tables`](../src/sunspot/tables.py).
