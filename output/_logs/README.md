# _logs/

Run logs for the April 2026 cohort sweep (`output/_logs/_summary.txt` records
the 2026-04-23 run: 6 single-user `sunspot correlate` runs, then a cross-user
pass anchored on `docxology`).

| file | content |
|------|---------|
| `{login}.log` | full stderr log of one `uv run sunspot correlate {login}` run (sunspot logger: timestamps, level, module) — GitHub repo discovery, cache hits, OMNI2 loads, per-metric phases |
| `_cross_user.log` | log of the cross-user comparison pass (anchor: docxology) |
| `_summary.txt` | one line per step: START / OK (elapsed) / rc, ending in DONE |

To reproduce a single log: `uv run sunspot correlate docxology -v` (see
[`docs/api/logutil.md`](../../docs/api/logutil.md) for log-level flags).

Local-only under `projects/ongoing/DataTools/` — never commit. Parent:
[`../README.md`](../README.md).
