# AGENTS — `docs/measures/`

| path | content |
|------|---------|
| [`README.md`](README.md) | Index + cross-cutting cadence/sign-convention notes |
| [`ssn.md`](ssn.md)       | SILSO daily total sunspot number V2.0 |
| [`f107.md`](f107.md)     | 10.7 cm solar radio flux |
| [`dst.md`](dst.md)       | Disturbance storm time index |
| [`ap.md`](ap.md)         | Planetary geomagnetic Ap index |

**Source of truth:** Each page must match the loader and parser in
`src/sunspot/datasets/*.py`. When a loader's URL, units, or sentinel-value
handling change, update the corresponding measure page **and**
[`docs/api/datasets.md`](../api/datasets.md) in the same change.

**Style:** Each page follows the same layout — *Physical meaning · Source ·
Loader · Cadence & resampling · Range / sentinels / gaps · Pipeline use ·
Pitfalls · References*. Keep it terse; link out to canonical authorities for
deep background.

**Cohort context:** for comparing several GitHub logins against the same
geophysical window, see [`docs/api/cohort.md`](../api/cohort.md) and CLI
[`--since-policy`](../api/cli.md#cohort).

**Not duplicated here:** Statistical operations on these series live under
[`docs/api/stats.md`](../api/stats.md); plot writers under
[`docs/api/viz.md`](../api/viz.md).
