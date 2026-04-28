# `sunspot.correlate`

Source: package [`src/sunspot/correlate/`](../../src/sunspot/correlate/) — main entry
[`pipeline.py`](../../src/sunspot/correlate/pipeline.py) (`run_correlation_report`), plus
[`_io.py`](../../src/sunspot/correlate/_io.py), [`_series.py`](../../src/sunspot/correlate/_series.py),
[`_report_helpers.py`](../../src/sunspot/correlate/_report_helpers.py).

| name | description |
|------|-------------|
| `default_correlate_dir(user: str, since: date, until: date) -> Path` | `output/correlate/{user}__{since}__{until}/` (slashes in `user` sanitized). |
| `run_correlation_report(user, *, since, until, metrics, out_dir, use_commit_cache=True, compare_user_logins=None, rolling_window=90, lag_max=60, make_mosaic=True, bootstrap=0, prewhiten=True, top_repos=8, enable_acf=True, enable_spectral=True, style_overrides=None) -> dict` | Full pipeline: commits + metrics, stats (associations, CIs, full lag/CCF profiles, ACF/PACF, periodogram + band power, multi-user), plots (per-metric, overview, per-repo, dynamics, multi-user), JSON/CSVs. Returns the report dict also written to `statistics/report.json`. |

## Output layout (under `out_dir`)

- `statistics/report.json` — associations, Pearson + Spearman CI, optional bootstrap CI, lag block (best lag, profile p-min, FDR-significant count) plus full `lag_profile`, CCF summary plus full `ccf_profile`, MA correlations, partial correlation (AR(1)-controlled), mutual information (binned-MM + KSG + normalised), MI lag profile, OLS regression diagnostics (R², Durbin–Watson, residual normality), Lomb–Scargle dominant period + top-5 plus named band-power fractions, cross-metric matrix, per-repo top-K, multi-user top-K.
- `data/commits/` — every GitHub-derived series for the run: `daily.csv`, `weekly.csv`, `monthly.csv`, `dow_means.csv`, `summary.csv`, `manifest.json`, `by_repo/{owner__repo}.csv`; with `--compare-users`, also `by_user/{login}.csv` + `by_user/manifest.json`.
- `data/{metric}/` — `aligned_daily.csv` (joined commits + metric) and `rolling.csv` (rolling Pearson) per metric.
- `visualizations/{metric}/` — per-metric PNGs (see [viz.md](viz.md)); plus `dynamics/`, `overview/`, `per_repo/`, optional `multi_user/`; top-level `mosaic.png`, `mosaic_index.json`, `executive_summary.png`.
- `analysis/summary.txt`, parameterized `methods.md`, `per_repo_summary.csv`, optional `multi_user_associations.csv`, and `tables/*.csv` — one plaintext CSV per statistical analysis (associations, lag profile, CCF profile, MA correlations, MI lag, MI summary, regression OLS, partial correlation, cross-metric Spearman, periodogram peaks and band power, top-K rankings, commit summary). Schema reference: [`sunspot.tables`](../../src/sunspot/tables.py).

Full tree description: [output/README.md](../../output/README.md).

**Cohort (multiple anchor logins, no per-metric deep dive):** see [cohort.md](cohort.md) and the `sunspot cohort` subcommand in [cli.md](cli.md#cohort).

**Private** functions (`_write_per_repo_commits`, `_write_commit_rollups`, `_write_per_user_commits`, `_series_for_metric`, `_format_summary`, etc.) are implementation details; tests exercise behavior via `run_correlation_report` and parsers.
