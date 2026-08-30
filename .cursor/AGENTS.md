# AGENTS.md — `sunspot/.cursor`

> Local-only path under `projects/ongoing/DataTools/` — matched by the
> root `.gitignore` rule `projects/*`; never commit. Repo-wide policy:
> see `/Volumes/external_drive/Git/template/projects/ongoing/AGENTS.md`.

## What this is

Cursor editor config. `hooks/state/` holds the local continual-learning
memory files (`continual-learning.json`, `continual-learning-index.json`);
there are no active hook scripts in this checkout.

## Layout (verified by direct listing, 2026-08-29)

```
hooks/
```

## Gotchas

- `hooks/state/continual-learning*.json` are gitignored local memory per the
  template's continual-learning convention; never commit them.
- Never `git add` anything under `projects/ongoing/`.
