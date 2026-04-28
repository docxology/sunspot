# AGENTS — `.github/`

Human-oriented walkthrough: [`README.md`](README.md).

| path | content |
|------|---------|
| [`workflows/ci.yml`](workflows/ci.yml) | GitHub Actions: Ubuntu, `astral-sh/setup-uv`, working directory default workspace root |

**Triggers:** `push` to `main`, `pull_request` targeting `main` (any branch of the PR).

**Job `test`:** `uv sync --all-groups` then `uv run ruff check src tests` then `uv run pytest -q` (pytest uses `addopts` from `pyproject.toml` — by default ``-m "not integration"`` for offline CI). To change markers or opt-in to network tests, adjust [`pyproject.toml`](../pyproject.toml) and the workflow line as needed.
