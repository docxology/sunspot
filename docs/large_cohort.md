# Large cohorts (many GitHub logins)

Use the `cohort` subcommand with **`--logins-file`** (one login per line, `#` comments) when the list is too long for a single comma argument. Merge order: **file first**, then comma-separated positional logins; duplicates are removed in first-seen order.

## Scaling behavior

- **`--large-cohort`** — Skips PCA, dendrogram, weekly heatmap, multi-user heatmaps, user×user pairwise correlation (O(n²)) in `report.json`, and several large multi-user PNGs. Still writes commit CSVs, **`analysis/multi_user_associations.csv`**, and for each requested metric a **histogram** of Spearman ρ across users: `visualizations/cohort/correlation_distribution_{metric}.png` plus `analysis/correlation_distribution_{metric}.csv`. Summary stats are in `report.json` under **`correlation_distribution`**.

- **`--large-cohort-threshold N`** (default **200**) — Same “large” behavior runs when the number of distinct logins is **≥ N**, even without `--large-cohort`.

- **`--min-active-days`** (default **30**) — Passed to `multi_user_associations`: every login has one row per requested metric. Users below the threshold get NaN `rho`/`p` and `insufficient_active` = True; the per-metric correlation CSVs and histogram footers report `cohort_n`, row counts, and how many were below threshold.
- **Large-cohort extra PNG** — `visualizations/cohort/user_activity_scatter.png`: all logins as points (total commits vs active days), since the per-user bar `user_summary.png` is omitted at scale.

## API cost

Hundreds or thousands of users implies many GitHub API calls to list repos and walk commits. Use **`GITHUB_TOKEN`**, `output/github_data/` caching, and an explicit **`--since`** date. If `--since` is omitted, the CLI resolves each user’s first commit date (one request per user) before the main fetch—avoid that for very large *n* by setting `--since` yourself.

A **histogram** characterizes the logins *you* chose; it is not a sample of all GitHub users unless your list was designed that way. Results remain **exploratory** (see [SPEC.md](../SPEC.md)).

## Example (not run in CI)

```bash
export GITHUB_TOKEN=$(gh auth token)
uv run sunspot cohort --logins-file my_logins.txt --since 2015-01-01 --until 2024-12-31 \
  --metrics ssn --large-cohort --out output/correlate/myrun
```

Runtime can be **hours to days** for very large *n* on a cold cache.
