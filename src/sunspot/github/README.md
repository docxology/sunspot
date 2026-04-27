# GitHub

Lists **non-fork public** user repositories, then walks `/commits` on each default branch with `author=<login>`, `since`, and `until` filters. Commits are recorded in a SQLite file for idempotent cache growth.

`first_commit_date(user_login)` resolves the user's earliest authored commit date in a single `GET /search/commits` call (sort `author-date asc`, `per_page=1`), falling back to the GitHub account `created_at`. The CLI uses it as the default for `--since` so a bare `sunspot correlate USER` covers the user's entire commit history.

Environment: `GITHUB_TOKEN` / `GH_TOKEN` (optional), `SUNSPOT_CACHE` (optional, affects SQLite path in `default_sqlite_path`).

See `AGENTS.md` for function names.
