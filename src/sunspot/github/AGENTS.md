# AGENTS — `github`

## Functions

| name | description |
|------|-------------|
| `client.github_token()` | Returns `GITHUB_TOKEN` / `GH_TOKEN` or `None` |
| `client.has_github_token()` | True if a token is set (higher API rate cap than unauthenticated) |
| `client.github_headers()` | `Accept` + `User-Agent` + optional `Authorization` |
| `client.default_sqlite_path()` | Default `output/github_data/github_cache.sqlite3` (or `SUNSPOT_CACHE`); may one-time copy from `~/.cache/sunspot/` |
| `commit_cache.github_data_dir()` | `output/github_data` (cwd-relative) |
| `commit_cache.commit_series_dir()` | `github_data_dir()/commit_series` or `SUNSPOT_COMMIT_SERIES` |
| `client.http_client()` | `httpx.Client` to `https://api.github.com` |
| `commits.list_public_repos(user_login, client=)` | Paginated public non-fork repos |
| `commits.iter_commits(user, full_name, default_branch, since=, until=, client=)` | Yields authored `(sha, datetime)` from `/commits?author=user&since=...&until=...` |
| `commits.public_commit_time_series(user_login, since=, until=)` | `dict` keyed by `full_name` and `"__all__"` → daily `Series` |
| `commit_cache.try_load_first_commit_date` / `save_first_commit_date` | JSON in `default_cache_dir()/first_commit_date/{login}.json` (sanitized name). |
| `commits.first_commit_date(user_login, client=, use_cache=True) -> date \| None` | If `use_cache` and `client` is `None`, returns cached date when present. Else: `GET /search/commits?…` then `/users/…` `created_at`. Writes successful results to the cache. Used by the CLI when `--since` is omitted. |

**Logging (INFO):** public repo count; sampled repo progress summaries; large-repo commit page progress; rate-limit waits with reset time. **WARNING:** HTTP 409 empty repo and low/unauthenticated rate-limit guidance (once per process). **DEBUG:** per-repo cache/API details and occasional commit pages.

## Tests

- `tests/test_github_model.py` uses `tests/fixtures/github_commit.json` to validate `_commit_dt`, plus `httpx.MockTransport` cases for `first_commit_date` (search-commits success, account-`created_at` fallback, both-fail returns `None`) and `iter_commits` request scoping (`author`, `since`, `until`).
