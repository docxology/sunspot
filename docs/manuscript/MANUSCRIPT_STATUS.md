# Manuscript Status

- **Repo type:** Tool + exploratory analysis package (GitHub commit history
  vs. solar/geophysical time series). Root `README.md` states statistics and
  plots are "exploratory only — not causal".
- **Why no publication-target manuscript applies today:** evidence checked —
  the repo ships a package (`src/`, `tests/`, `pyproject.toml`) with a module-
  scoped `docs/` hub; `output/correlate/` and `report/` hold run outputs
  (report.json, rolling CSVs, PNGs) that are per-run artifacts, not a
  claims-gated findings writeup. There is no research README asserting
  findings, no figures-of-record registry, and the root README explicitly
  disclaims causal interpretation.
- **What would trigger creating a `manuscript/`:** a preregistered,
  claims-gated study with fixed cohorts, statistical methods of record, and
  interpreted findings that the repo's own docs could source (see
  `SPEC.md` for current scope and limitations).
