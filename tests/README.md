# Tests

The default pytest selection excludes tests marked `integration`. Parser tests
use **real** file snippets from `tests/fixtures/` (SILSO V2.0 semicolon, OMNI2
hourly line, GitHub commit JSON) so format drift produces a failing parse.

- **End-to-end offline** (`test_correlate_offline.py`, `test_cohort_offline.py`)
  exercise both report pipelines with synthetic commit and solar metric
  series. The tests replace the loaders at both data boundaries, so these
  runs work with an empty OMNI2 cache.
- **Statistics primitives** (`test_stats.py`, `test_stats_extras.py`,
  `test_stats_deeper.py`, `test_stats_primitives.py`) exercise every public
  function in `sunspot.stats` on controlled synthetic samples.
- **HTTP boundaries** (`test_github_model.py`, `test_github_client_cache.py`,
  `test_datasets_cache.py`) use `httpx.MockTransport` — no real network.
- **CLI** (`test_cli_defaults.py`) runs Typer through `CliRunner` and supplies
  local responses for commit data. The two correlation tests for date defaults
  still call the SILSO and OMNI2 loaders on a cold cache. They pass when those
  requests are blocked because the CLI handles unavailable metric data.
- **Integration** (`test_integration_network.py`) exercises the live SILSO
  fetch. Mark new integration tests that require network access with
  `@pytest.mark.integration`.

The tracked CI workflow configures `uv run ruff check src tests` and
`uv run pytest -q`. Pytest applies `-m "not integration"` from `pyproject.toml`.
To select live integration tests, run `uv run pytest -m integration`.
Select both groups with `uv run pytest -m "integration or not integration"`.

Single test: `uv run pytest tests/test_stats.py::test_lag`.

See `AGENTS.md` for a file-by-file inventory.
