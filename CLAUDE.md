# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

`sunspot` correlates a GitHub user's **public** commit history (per repo and aggregate, daily UTC bins) with vetted space-weather time series (SILSO sunspot number, OMNI2 F10.7 / Dst / ap / R). Output is **exploratory** association statistics and plots — the SPEC explicitly excludes causal inference (Granger, VAR) as out of scope for v1. Keep that framing when writing analysis / summary text.

## Commands

All Python work goes through `uv` (project uses `uv_build`, Python `>=3.12`):

```bash
uv sync --all-groups            # install deps + dev group (pytest, ruff)
uv run ruff check src tests     # lint (rules: E, F, I, W; line-length 100)
uv run pytest                   # default: excludes @pytest.mark.integration (see pyproject addopts)
uv run pytest tests/test_stats.py::test_name   # single test
uv run pytest -m integration    # only network / live-URL tests (e.g. SILSO fetch)
uv run pytest -m "integration or not integration"  # full selection including integration
```

CI (`.github/workflows/ci.yml`) runs exactly: `uv sync --all-groups` → `uv run ruff check src tests` → `uv run pytest -q`. Match that locally before pushing.

### Running the CLI

```bash
export GITHUB_TOKEN=$(gh auth token)    # unauthenticated GitHub = ~60 req/hr; tokened = thousands
uv run sunspot correlate <user>         # --since defaults to user's first commit, --until to today UTC
uv run sunspot cohort a,b,c             # multi-user among-user analysis
uv run sunspot cohort --preset ai       # presets live in src/sunspot/cohort_presets.py
```

Env overrides: see [`docs/configuration.md`](docs/configuration.md) and `src/sunspot/config.py` — e.g. `SUNSPOT_LOG_LEVEL`, `SUNSPOT_FONT_SCALE`, `SUNSPOT_LINEWIDTH`, `SUNSPOT_DPI`, `SUNSPOT_THEME`, `SUNSPOT_CACHE` (dir containing `github_cache.sqlite3`), `SUNSPOT_COMMIT_SERIES` (per-repo CSV tree), `XDG_CACHE_HOME` (under it: `…/sunspot/url/` for dataset files).

## Architecture

Data flow (orchestrated by `src/sunspot/correlate/pipeline.py::run_correlation_report`):

1. **Ingest commits** — `github.commits.public_commit_time_series(user, since, until)` walks `/users/{u}/repos` then `/repos/{u}/{r}/commits?author={u}&since=...&until=...`, with a sqlite dedup DB and per-repo CSV cache (defaults under `output/github_data/`; legacy `~/.cache/sunspot/commit_series/` is still read). `github.commits.first_commit_date` supplies the `--since` default via `GET /search/commits?q=author:USER&sort=author-date&order=asc`, falling back to account `created_at`.
2. **Ingest geophysical series** — `datasets/silso.py` (SILSO daily V2.0) and `datasets/omni.py` (OMNI2 hourly → daily mean for F10.7, Dst, ap, R). Downloads cache to `~/.cache/sunspot/url/` (override with `XDG_CACHE_HOME` or `SUNSPOT_CACHE`).
3. **Align** — `align.join_on_dates` produces a common daily index; `align.zscore` standardizes for overlays.
4. **Statistics** — `stats/correlation.py` (Pearson + Fisher-z CI, Spearman + Bonett–Wright CI, Kendall, bootstrap, rolling, lag search with BH-FDR), `stats/spectral.py` (CCF with Bartlett bands + optional AR(1) pre-whitening, ACF/PACF, Lomb–Scargle), `stats/information.py` (mutual information), `stats/per_repo.py`, `stats/multi_user.py`.
5. **Write artifacts** under `out_dir` (default `output/correlate/{user}__{since}__{until}/`):
   - `statistics/report.json` — machine-readable; the authoritative output
   - `data/` — `commits_daily.csv`, per-repo and per-metric CSVs, manifests
   - `visualizations/` — per-metric tiles, overview, per-repo, dynamics, multi-user, and `mosaic.png` graphical abstract (built by `viz/mosaic.py`)
   - `analysis/` — `summary.txt`, `methods.md`, `per_repo_summary.csv`, `multi_user_associations.csv`, `tables/*.csv` (one tidy CSV per analysis block, schema in `analysis/tables/README.md`) — emitted by `tables.py::write_analysis_tables`

`cohort.py` (`sunspot cohort`) is a distinct, narrower pipeline: **among-user only** (`report_kind: "cohort"`), no per-metric plot tree, no per-repo. It writes `data/commits/` (`daily.csv` = sum across users, `daily_users_wide.csv`, `by_user/`) and `visualizations/cohort/` (PCA, dendrogram, weekly heatmap) plus a compact mosaic. Don't retrofit correlate's per-metric artifacts onto cohort output.

### Module map

| Module | Role |
|--------|------|
| `cli.py` | Typer app. Configures logging **first**, resolves date window, then sets the global `viz.PlotStyle` from `--font-scale`/`--line-width`/`--dpi`/`--theme`. Rejects `--since > --until`. |
| `correlate/` | Package; `pipeline.py` is the main orchestrator. See `src/sunspot/correlate/AGENTS.md`. |
| `cohort.py` + `cohort_presets.py` | Multi-user pipeline. Presets: `full`, `panel`, `ai`, `famous`, `wide`. |
| `tables.py` | `write_analysis_tables` — tidy CSV-per-analysis exports + schema README. |
| `logutil.py` | `configure_sunspot_logging` (logger name `sunspot`, handler on stderr). Call before any work. |
| `align/`, `datasets/`, `github/`, `stats/`, `viz/` | Subpackages; each has its own `AGENTS.md` and `README.md` worth reading when you touch that area. |

Every package directory has an `AGENTS.md` (root, `src/sunspot/`, and each subpackage + `tests/`, `docs/`, `.github/`) that is the authoritative per-area reference. Read the relevant `AGENTS.md` before non-trivial changes.

## Conventions

- **Parsers are tested against real file snippets** (see `tests/fixtures/` + `test_silso_parse.py`, `test_omni_parse.py`, `test_noaa_parse.py`) — not hand-rolled numeric mocks. Preserve this when adding dataset readers: capture a real fixture.
- **Offline tests** (`test_correlate_offline.py`, `test_cohort_offline.py`) monkeypatch `correlate.public_commit_time_series`; OMNI data is fetched once then served from cache. Keep new tests offline by default; gate network tests with `@pytest.mark.integration`.
- **Logging** goes to `stderr` via the `sunspot` logger. Don't `print()` in library code.
- **Style system** is centralized in `viz/style.py` as a global `PlotStyle`. `cli.py` sets it before any plot call — don't pass style knobs into individual plot functions.
- **Datasets and attribution:** SILSO is CC BY-NC (non-commercial); OMNI2/SPDF and NOAA SWPC are public but want proper citation. Don't bake SILSO values into committed fixtures without checking the license angle.
- **Framing:** results are **exploratory correlations**, never causal. `SPEC.md` is explicit about this; keep that tone in any `summary.txt`/`methods.md` edits.

## Outputs and caches (gitignored)

`output/*` is ignored except the committed `README.md` stubs. Treat it as scratch space. The CLI default run root is `output/correlate/{user}__{since}__{until}/`. GitHub per-repo commit CSVs + dedup sqlite default to `output/github_data/`.
