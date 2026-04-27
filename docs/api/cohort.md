# `sunspot.cohort` — multi-user runs

Source: [`src/sunspot/cohort.py`](../../src/sunspot/cohort.py) and
[`src/sunspot/cohort_presets.py`](../../src/sunspot/cohort_presets.py). Invoked
from the Typer subcommand `cohort` (see [cli.md](cli.md)). There is no
`visualizations/{ssn,f107,…}/` per-metric tree: only shared commit data,
`dynamics/`, `cohort/`, `multi_user/`, and a cohort-specific mosaic.

| name | description |
|------|-------------|
| `default_cohort_dir(n_users: int, since, until, *, slug="cohort") -> Path` | `output/correlate/cohort_n{count}__{since}__{until}/`. |
| `expand_preset(name: str) -> tuple[str, ...]` | Named login lists: `panel`, `ai`, `famous`, `wide`, `full` (see `cohort_presets.py`). |
| `run_cohort_report(logins, *, since, until, metrics, out_dir, use_commit_cache=True, make_mosaic=True, style_overrides=None, since_policy=None) -> dict` | Fetches all users, writes `report_kind: "cohort"`, `statistics/report.json`, `analysis/`, and cohort visuals. `since_policy` is metadata only: e.g. `"union"`, `"intersection"`, or `"explicit"` when `--since` was set on the CLI. |

## Output layout (under `out_dir`)

- `statistics/report.json` — cohort block includes `cohort_users`, optional `since_policy`, `cohort_user_summary`, `cohort_zero_commit_users` (logins with no commits in the window), `cohort_clustering_excluded_users` (constant weekly-activity users omitted from correlation-distance clustering), `cohort_dendrogram_leaves`, `cohort_pca`, `multi_user_topk`, `user_user_spearman_smoothed_30d`, `commits_summary`, `executive_summary`, `mosaic` (paths), etc.
- `data/commits/` — `daily.csv` (sum across users), `daily_users_wide.csv`, `user_summary.csv`, `by_user/{login}.csv`, `cohort_logins.txt`, rollups `weekly.csv`, `monthly.csv`, `dow_means.csv`, `summary.csv`.
- `visualizations/dynamics/` — e.g. `compare_users_30d_ma.png` (commits MAs vs z(SSN)).
- `visualizations/cohort/` — `user_pca_scatter.png`, `user_dendrogram.png` (if ≥2 users have varying weekly series), `user_weekly_heatmap.png`, `user_summary.png`.
- `visualizations/multi_user/` — user×metric heatmap, overview, rank matrix, cumulative vs solar, phase by SSN quantile (see [viz.md](viz.md#multi_user)).
- `visualizations/executive_summary.png`, `mosaic.png` (from `save_cohort_executive_summary`, `assemble_cohort_mosaic` when `make_mosaic` is true).
- `analysis/summary.txt`, `multi_user_associations.csv` (and `write_analysis_tables` output where report fields exist, including `tables/cohort_user_summary.csv`; many single-user-only tables are empty or skipped for cohort).

## Among-user analysis

- **User×metric** Spearman: [`multi_user_associations` in stats](stats.md#multi_user) (requires `min_active_days` of activity per user).
- **Pairwise user×user** (smoothed): `multi_user_rank_matrix` — stored in `report.json` and as a heatmap.
- **PCA** on weekly sums (rows z-scored per user before SVD): `pca_users_weekly` — see [stats](stats.md#multi_user).
- **Hierarchical clustering** (average linkage, correlation distance on weekly sums): users with **no week-to-week variation** (e.g. all-zero commits) are **excluded** so `pdist` stays finite; see `cohort_correlation_dendrogram_data` in [stats](stats.md#multi_user) and [viz cohort](viz.md#cohort).

**Private** helpers in `cohort.py` mirror pieces of the single-user pipeline (`_write_per_user_commits`, `_series_for_metric`, etc.) but do not add per-repo or per-metric deep statistics.

## See also

- CLI flags and default date policy: [cli.md](cli.md#cohort) (`--since-policy union|intersection`).
- GitHub fetch limits: [github.md](github.md) — set `GITHUB_TOKEN` for higher rate limits on large cohorts.
