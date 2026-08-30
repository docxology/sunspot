# AGENTS.md — `sunspot/.github/workflows`

> Local-only path under `projects/ongoing/DataTools/` — matched by the
> root `.gitignore` rule `projects/*`; never commit. Repo-wide policy:
> see `/Volumes/external_drive/Git/template/projects/ongoing/AGENTS.md`.

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

- CI is effectively advisory while the project lives under
  `projects/ongoing/` (local-only, never pushed); the workflow assumes the
  project is a standalone repo root with `src/`, `tests/`, `pyproject.toml`.
- Never `git add` anything under `projects/ongoing/`.
