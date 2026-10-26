# AGENTS.md — `sunspot/.github/workflows`

## What this is

GitHub Actions workflows. Exactly one: [`ci.yml`](ci.yml) — job `test`
(ubuntu-latest, `setup-uv@v5`): `uv sync --all-groups` → `ruff check src tests`
→ `pytest -q` (offline; `integration`-marked tests excluded via
`pyproject.toml` addopts). Triggers: push/PR on `main`.

## Layout (verified by direct listing, 2026-08-29)

```
ci.yml
```

## Gotchas

- CI runs on push to `main` and on PRs targeting `main`; the repo root is a
  standalone project with `src/`, `tests/`, `pyproject.toml`.
