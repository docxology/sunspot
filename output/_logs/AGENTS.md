# AGENTS.md — `sunspot/output/_logs`

## What this is

Per-user and cross-user run logs plus `_summary.txt` from the 2026-04-23
n=6 cohort sweep (logins: 4dsolutions, AiwonA1, antirez, docxology,
gvanrossum, karpathy; cross-user anchored on docxology).

## Layout (verified by direct listing, 2026-08-29)

```
4dsolutions.log, AiwonA1.log, _cross_user.log, _summary.txt, antirez.log, docxology.log, gvanrossum.log, karpathy.log
```

## Gotchas

- Logs are point-in-time evidence for the 2026-04-23 run only; they do not
  refresh on reruns — a new run writes wherever its `--out`/cwd points.
- `_summary.txt` lines are the fast health check: every step should read
  `OK` / `rc=0` and end with `DONE`.
