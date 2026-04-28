# Configuration

Runtime behaviour is controlled by the Typer CLI (see [api/cli.md](api/cli.md)) and
environment variables. Canonical names and defaults live in
[`src/sunspot/config.py`](../src/sunspot/config.py); the table below is the human
reference.

## Environment variables

| Variable | Default | Read by | Purpose |
|----------|---------|---------|---------|
| `XDG_CACHE_HOME` | (unset) | `config.dataset_cache_dir` → `datasets.cache.default_cache_dir` | Base for `…/sunspot/url/` dataset file cache |
| `SUNSPOT_CACHE` | (unset) | `config.sqlite_parent_dir_from_env` → `github.client.default_sqlite_path` | Directory containing `github_cache.sqlite3` (SHA dedup DB) |
| `SUNSPOT_COMMIT_SERIES` | (unset) | `config.commit_series_root_from_env` → `github.commit_cache.commit_series_dir` | Root for per-repo daily commit CSV trees |
| `GITHUB_TOKEN` / `GH_TOKEN` | (unset) | `config.github_token_from_env` → `github.client` | Authenticated GitHub REST (higher rate limit) |
| `SUNSPOT_LOG_LEVEL` | (empty) | `config.sunspot_log_level_env_raw` → `cli._resolve_log_level` | When `--log-level` stays at default `INFO`, can set e.g. `DEBUG` |
| `SUNSPOT_FONT_SCALE` | `1.45` | `config.read_plot_style_env` → `viz.style` (import-time global) | Plot font scale |
| `SUNSPOT_LINEWIDTH` | `1.9` | same | Default line width |
| `SUNSPOT_DPI` | `300` | same | PNG resolution |
| `SUNSPOT_THEME` | `light` | same | `light` or `dark` |

CLI flags for `correlate` / `cohort` override the plot style globals when the
command runs (`viz.set_style`), after logging is configured.

## See also

- [README.md](../README.md) — quickstart and token setup
- [api/datasets.md](api/datasets.md) — dataset loaders and URL cache
- [api/github.md](api/github.md) — commit API and caches
