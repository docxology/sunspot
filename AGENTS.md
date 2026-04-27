# AGENTS — repository root

| path | content |
|------|---------|
| `src/sunspot/` | Python package: CLI (`correlate` + `cohort`), `correlate.py` + `cohort.py`, `cohort_presets.py`, `datasets/`, `github/`, `align/`, `stats/`, `tables.py`, `viz/` (incl. `viz/cohort.py`) |
| `docs/` | Modular reference: API (`docs/api/*.md`), topical method notes (`docs/methods/`), per-dataset references (`docs/measures/`); index in `docs/README.md` |
| `tests/` | Pytest: parsers on real-style fixtures; offline report test with `correlate.public_commit_time_series` monkeypatched |
| `pyproject.toml` | `uv` project; `sunspot` script → `sunspot.cli:main` |
| `.github/workflows/ci.yml` | `uv sync --all-groups`, `ruff check`, `pytest` |

**Public CLI:**

```text
uv run sunspot correlate <user>
  [--since YYYY-MM-DD]   # default: user's first GitHub commit (search/commits → /users created_at fallback)
  [--until YYYY-MM-DD]   # default: today (UTC)
  [--metrics ssn,f107,dst,ap]
  [--rolling-window 90 --lag-max 60]
  [--bootstrap 0 --no-prewhiten --top-repos 8 --no-acf --no-spectral]
  [--no-mosaic --no-commit-cache --compare-users a,b,c]
 [--font-scale 1.45 --line-width 1.9 --dpi 300 --theme light]
  [--log-level INFO -v --quiet --out /path/to/run]
```

```text
uv run sunspot cohort a,b,c
  [--preset full|panel|ai|famous|wide]   # alternative to a,b,c
  [--since YYYY-MM-DD]   # if omitted: see --since-policy
  [--since-policy union|intersection]   # default: union = min first-commit (longest window); intersection = max
  [--until YYYY-MM-DD]   # default: today (UTC)
  [--metrics ssn,f107,dst,ap]  [--out /path]  [--no-mosaic]  [--no-commit-cache]
 [--font-scale 1.45 --line-width 1.9 --dpi 300 --theme light]
```

`--since` defaults to the earliest commit GitHub knows for `<user>` via
`sunspot.github.commits.first_commit_date`; on lookup failure the CLI fails
fast with a hint to set `--since` explicitly. `--until` defaults to today
(UTC). Default run root: `output/correlate/{user}__{since}__{until}/` with
the resolved dates. Logging configured by
`sunspot.logutil.configure_sunspot_logging`, invoked from `cli.py` before
work; honours `SUNSPOT_LOG_LEVEL` when no flag is set.

**Python API:** `from sunspot.correlate import run_correlation_report` —
keyword args: `since`, `until`, `metrics`, `out_dir`,
`use_commit_cache=True`, `compare_user_logins=None`, `rolling_window=90`,
`lag_max=60`, `bootstrap=0`, `prewhiten=True`, `top_repos=8`,
`enable_acf=True`, `enable_spectral=True`, `make_mosaic=True`,
`style_overrides=None`.

**Cohort API:** `from sunspot.cohort import run_cohort_report, default_cohort_dir` — multi-user
window, among-user only (see `cohort.py` and `cohort_presets.py`).

**Caching:** SILSO/OMNI URL files under `~/.cache/sunspot/url/` (or
`XDG_CACHE_HOME`/`SUNSPOT_CACHE` for the datasets cache). **GitHub** per-repo
commit CSVs and the commit dedup DB default to **`output/github_data/`**
(`commit_series/`, `github_cache.sqlite3`); see `output/github_data/README.md`.
Set `SUNSPOT_COMMIT_SERIES` or `SUNSPOT_CACHE` to override; legacy
`~/.cache/sunspot/commit_series/` is still read for cache hits.

## Learned User Preferences

- Plot outputs should prioritize readable annotations: larger fonts, thicker lines, legends, time-window metadata, supported statistical significance markings, and high-resolution mosaics that preserve source image aspect ratios.
- Analysis runs should emit plaintext or tidy statistical outputs alongside visualizations, with daily statistics and rolling or moving-average correlations where the data support them.

## Learned Workspace Facts
