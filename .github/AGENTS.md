# AGENTS — `.github/`

| path | content |
|------|---------|
| [`workflows/ci.yml`](workflows/ci.yml) | GitHub Actions: Ubuntu, `astral-sh/setup-uv`, working directory default workspace root |

**Triggers:** `push` to `main`, `pull_request` targeting `main` (any branch of the PR).

**Job `test`:** `uv sync --all-groups` then `uv run ruff check src tests` then `uv run pytest -q`. Change Python/deps in [`pyproject.toml`](../pyproject.toml); change lint/test scope by editing the `ruff`/`pytest` lines in the workflow.
