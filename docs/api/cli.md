# `sunspot.cli`

Source: [`src/sunspot/cli.py`](../../src/sunspot/cli.py). Typer app: `sunspot` → `main()` → `app()`.

| name | description |
|------|-------------|
| `main() -> None` | Invokes the Typer app. |
| `cmd_correlate(...)` | Subcommand `correlate` (see [correlate command](#correlate)). |
| `cmd_cohort(...)` | Subcommand `cohort` (see [cohort command](#cohort)). Calls `run_cohort_report` in [`cohort.py`](../../src/sunspot/cohort.py); full layout in [cohort.md](cohort.md). |

## `correlate`

`cmd_correlate` arguments (Typer):

| option / arg | type | notes |
|--------------|------|--------|
| `user` | argument | GitHub login (public data only) |
| `--since` | `YYYY-MM-DD`, optional | UTC day. Default: user's earliest GitHub commit date via `github.commits.first_commit_date` (search-commits API → `/users/{user}` `created_at` fallback). Errors fast with a hint if both lookups fail. |
| `--until` | `YYYY-MM-DD`, optional | UTC day. Default: today (UTC). |
| `--metrics` | default `ssn,f107,dst,ap` | Comma list: `ssn`, `f107`, `dst`, `ap`, `r_ssn` |
| `--out` | path | Default: `output/correlate/{user}__{since}__{until}/` (see [correlate.md](correlate.md)) |
| `--log-level` | `DEBUG\|INFO\|WARNING\|ERROR` | Default `INFO` |
| `-v` / `--verbose` | flag | `DEBUG` (wins over `--log-level` and env) |
| `--quiet` | flag | `WARNING` |
| `--no-commit-cache` | flag | Skip per-repo series cache under the cache dir |
| `--compare-users` | comma logins | Extra users for 30d MA vs SSN in `visualizations/dynamics/` |
| `--rolling-window` | int | Default `90` (passed to pipeline) |
| `--lag-max` | int | Default `60` |
| `--bootstrap` | int | Percentile bootstrap iterations for correlation CIs (default `0` = off) |
| `--no-prewhiten` | flag | Disable AR(1) pre-whitening for the CCF |
| `--top-repos` | int | Repos shown in the top-repos MA plot (default `8`) |
| `--no-acf` | flag | Skip per-metric and overview ACF/PACF plots |
| `--no-spectral` | flag | Skip per-metric and overview Lomb–Scargle periodograms |
| `--no-mosaic` | flag | Skip `mosaic.png` / `mosaic_index.json` |
| `--font-scale` | float | Plot font scale (default `1.45`); also `SUNSPOT_FONT_SCALE` |
| `--line-width` | float | Plot line width (default `1.9`); also `SUNSPOT_LINEWIDTH` |
| `--dpi` | int | Output DPI (default `300`); also `SUNSPOT_DPI` |
| `--theme` | `light\|dark` | Plot theme (default `light`); also `SUNSPOT_THEME` |

On startup, `configure_sunspot_logging` (see [logutil.md](logutil.md)) runs, then `--since`/`--until` are resolved (defaulting to the single user's first commit date and today UTC, with `--since > --until` rejected), the global `viz.PlotStyle` is set from the style flags, and `run_correlation_report` runs (see [correlate.md](correlate.md)).

## `cohort`

*Either* comma-separated `logins` *or* `--preset` (see [`cohort_presets.py`](../../src/sunspot/cohort_presets.py): `panel`, `ai`, `famous`, `wide`, `full` — not both at once). Presets are expanding lists of public GitHub logins for comparison-style runs.

| option / arg | type | notes |
|--------------|------|--------|
| `logins` | argument, optional | Comma list; required if no `--preset`. |
| `--preset` | string | `panel`, `ai`, `famous`, `wide`, or `full`. |
| `--since` | `YYYY-MM-DD`, optional | UTC start. Omitted: see `--since-policy` and [github.md](github.md) `first_commit_date` per login. |
| `--since-policy` | string | Used only when `--since` is omitted. Default **`union`**: `min` of known first-commit dates (longest calendar window; aligns with long solar/geomag series). **`intersection`** (aliases accepted in code: `i`, `max`, `tight`): `max` of first commits — shortest span where every account already existed. |
| `--until` | `YYYY-MM-DD`, optional | Default: today (UTC). |
| `--out` | path | Default: `output/correlate/cohort_n{N}__{since}__{until}/`. |
| `--metrics` | comma list | Default `ssn,f107,dst,ap` — columns for the user×geophysics [multi_user](stats.md#multi_user) long table. |
| `--no-commit-cache` | flag | Refetch per-repo series (ignore cache). |
| `--no-mosaic` | flag | Skip `mosaic.png` / `mosaic_index.json`. |
| `--log-level` | `DEBUG\|INFO\|WARNING\|ERROR` | Default `INFO`; same precedence as `correlate`. |
| `-v` / `--verbose` | flag | `DEBUG`. |
| `--quiet` | flag | `WARNING`. |
| `--font-scale`, `--line-width`, `--dpi`, `--theme` | | Same role as `correlate`; feed `style_overrides` into `run_cohort_report`. |

Cohort does **not** write `visualizations/{ssn,f107,…}/` per-metric trees — only `dynamics/`, `cohort/`, `multi_user/`, and cohort [mosaic / executive](viz.md#mosaic). See [cohort.md](cohort.md) for the report dict and [`multi_user.py`](../../src/sunspot/stats/multi_user.py) for clustering excludes when weekly activity is constant.

**Private** helpers: `_root`, `_dt`, `_resolve_log_level` — not part of a stable API.
