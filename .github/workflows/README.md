# workflows/

GitHub Actions workflows.

| file | content |
|------|---------|
| `ci.yml` | `ci` workflow — one job (`test`) on `ubuntu-latest`: checkout, `astral-sh/setup-uv@v5`, then `uv sync --all-groups`, `uv run ruff check src tests`, `uv run pytest -q` |

Triggers: `push` to `main` and `pull_request` targeting `main`. Pytest runs
offline by default (`-m "not integration"` comes from `pyproject.toml`
`addopts`); network/GitHub-API tests opt in via the `integration` marker.

Parent: [`../README.md`](../README.md) / repo walkthrough: [`../AGENTS.md`](../AGENTS.md).
