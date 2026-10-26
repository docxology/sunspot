# AGENTS.md — `sunspot/.cursor`

## What this is

Cursor editor config. `hooks/state/` holds the local continual-learning
memory files (`continual-learning.json`, `continual-learning-index.json`);
there are no active hook scripts in this checkout.

## Layout (verified by direct listing, 2026-08-29)

```
hooks/
```

## Gotchas

- `hooks/state/continual-learning*.json` are gitignored machine-local hook
  state (see `.gitignore`).
