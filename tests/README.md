# Tests

Offline-by-default pytest suite. Parsers are covered by **real** file snippets
in `tests/fixtures/` (SILSO V2.0 semicolon, OMNI2 hourly line, GitHub commit
JSON) so format drift surfaces as a failing parse, never as silent numeric
corruption.

- **End-to-end offline** (`test_correlate_offline.py`, `test_cohort_offline.py`)
  monkeypatches `public_commit_time_series` with synthetic series and (for
  metrics) either returns a synthesized `pd.Series` or uses the on-disk OMNI2
  cache populated by earlier runs. Fresh-checkout CI downloads OMNI2 on the
  first run; subsequent runs hit the cache.
- **Statistics primitives** (`test_stats.py`, `test_stats_extras.py`,
  `test_stats_deeper.py`, `test_stats_primitives.py`) exercise every public
  function in `sunspot.stats` on controlled synthetic samples.
- **HTTP boundaries** (`test_github_model.py`, `test_github_client_cache.py`,
  `test_datasets_cache.py`) use `httpx.MockTransport` — no real network.
- **CLI** (`test_cli_defaults.py`) runs the Typer app through `CliRunner`
  with `first_commit_date` monkeypatched.
- **Integration** (GitHub / NASA / SILSO live): not run in default CI; mark new
  tests that need the network with `@pytest.mark.integration` (see
  `pyproject.toml` markers).

Run: `uv run pytest` (matches CI: `ruff` + pytest with `-m "not integration"` from
`pyproject.toml`). Integration tests (real network): `uv run pytest -m integration`.
Full selection: `uv run pytest -m "integration or not integration"`.

Single test: `uv run pytest tests/test_stats.py::test_lag`.

See `AGENTS.md` for a file-by-file inventory.
