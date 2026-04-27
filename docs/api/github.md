# `sunspot.github`

## `client` ([`client.py`](../../src/sunspot/github/client.py))

| name | description |
|------|-------------|
| `github_token() -> str \| None` | `GITHUB_TOKEN` or `GH_TOKEN`. |
| `has_github_token() -> bool` | Whether a non-empty token exists. |
| `github_headers() -> dict` | `Accept`, `User-Agent`, optional `Authorization: Bearer`. |
| `default_sqlite_path() -> Path` | If **`SUNSPOT_CACHE`** is set: `{SUNSPOT_CACHE}/github_cache.sqlite3`; else **`output/github_data/github_cache.sqlite3`** (resolved from `cwd`, see `github_data_dir()` in `commit_cache.py`). A one-time copy from `~/.cache/sunspot/github_cache.sqlite3` may run if the new file is missing. |
| `http_client() -> httpx.Client` | Base URL `https://api.github.com`, shared headers, 30s timeout. |

**Rate limits:** unauthenticated calls are **very** low (on the order of tens
of requests per hour for search-related endpoints). For multi-repo or
[cohort](cohort.md) runs, set **`GITHUB_TOKEN`** (or **`GH_TOKEN`**) to a
read-only personal access token — the same `Authorization: Bearer` path
[`github_headers()`](../../src/sunspot/github/client.py) uses. The CLI and
`commits` log warnings when the API returns a rate-limit body and may sleep
until the reset window.

## `commits` ([`commits.py`](../../src/sunspot/github/commits.py))

| name | description |
|------|-------------|
| `first_commit_date(user_login, *, client=None, use_cache=True) -> date \| None` | If `use_cache` and `client` is `None`, returns `try_load_first_commit_date` when a JSON file exists under `default_cache_dir()/first_commit_date/`. Otherwise: `GET /search/commits?…` then `GET /users/{user_login}` `created_at`. Successful lookups are saved to that cache. Used when `--since` is omitted (correlate and cohort). |
| `list_public_repos(user_login, client=None) -> list[dict]` | Non-fork owner repos, paginated; each dict has `full_name`, `default_branch`, `pushed_at`. |
| `iter_commits(user_login, full_name, default_branch, *, since=None, until=None, client=None)` | Yields authored `(sha, datetime)` from `/commits?author=user_login&since=...&until=...`; stops when responses are exhausted. Records SHAs in SQLite dedup DB. |
| `to_daily_commit_counts(times: list[datetime]) -> pd.Series` | Daily sum of commit counts, name `commits`. |
| `public_commit_time_series(user_login, *, since=None, until=None, use_commit_cache=True) -> dict[str, pd.Series]` | Keys: `owner/repo` and `__all__` (sum). Uses per-repo CSV cache when enabled (see `commit_cache`). |

## `commit_cache` ([`commit_cache.py`](../../src/sunspot/github/commit_cache.py))

| name | description |
|------|-------------|
| `github_data_dir() -> Path` | `output/github_data` (from cwd); base for default GitHub on-disk state. |
| `commit_series_dir() -> Path` | Default `github_data_dir()/commit_series` or `SUNSPOT_COMMIT_SERIES` if set. |
| `commit_series_cache_path(user, full_name, since, until, *, root=None) -> Path` | Under `commit_series_dir()` / `{user}/` (or `root` if passed). |
| `commit_series_meta_path(path) -> Path` | Sidecar `.meta.json`. |
| `try_load_commit_series(...) -> pd.Series \| None` | Returns daily series or `None` if missing/invalid. |
| `save_commit_series_cache(series, user, full_name, since, until, *, root=None) -> Path` | Writes CSV + meta. |
| `first_commit_date_cache_path(user_login) -> Path` | `default_cache_dir()/first_commit_date/{sanitized}.json`. |
| `try_load_first_commit_date(user_login) -> date \| None` | Read cached first-commit date. |
| `save_first_commit_date(user_login, d) -> Path` | Write cache after a successful API resolution. |

**Private** helpers: `_get` (rate-limit retry), DB init, throttle — not stable API.
