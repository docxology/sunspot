# GitHub configuration

This directory holds repository automation for **sunspot** on GitHub. Everything here is version-controlled; nothing in `.github/` is generated at clone time.

| Path | Role |
|------|------|
| [`workflows/ci.yml`](workflows/ci.yml) | Continuous integration: install deps, lint, test |
| [`AGENTS.md`](AGENTS.md) | Machine-oriented summary of this folder (triggers, job steps, edit points) |

The project’s Python packaging, optional dependency groups, and `pytest` markers are defined in [`pyproject.toml`](../pyproject.toml) at the repo root (`requires-python = ">=3.12"`). CI does not pin a separate Python version in YAML; the runner’s default interpreter is used, and the lockfile / `uv` resolve what gets installed.

---

## Workflow: `ci` (`workflows/ci.yml`)

**Name:** `ci` (shown in the Actions tab as the workflow name).

**When it runs**

| Event | Filter |
|--------|--------|
| `push` | Branch is `main` |
| `pull_request` | Base branch is `main` |

Pushes to other branches and PRs that do not target `main` do not run this workflow.

**Runner:** `ubuntu-latest` (`jobs.test.runs-on`).

**Job:** single job `test` with three steps after checkout:

1. **`actions/checkout@v4`** — full repo at `GITHUB_WORKSPACE` (default).
2. **`astral-sh/setup-uv@v5`** — `version: "latest"`.
3. **Sync and test** — one shell block with `working-directory: ${{ github.workspace }}` (explicit default):

   ```bash
   uv sync --all-groups
   uv run ruff check src tests
   uv run pytest -q
   ```

   - `uv sync --all-groups` installs the main environment **and** dev groups (e.g. tools used by `ruff` and `pytest` per `pyproject.toml`).
   - Ruff lints `src/` and `tests/` only; extend paths by changing that line in the workflow.
   - `pytest -q` runs the suite under `testpaths = ["tests"]`; because `pyproject.toml` sets `addopts = ["-m", "not integration"]`, the filter applies to this bare `pytest -q` too — **integration-marked tests are excluded from CI as well as locally** (the workflow YAML itself adds no `-m` flag, but addopts always apply). The `integration` marker is for tests that need network or a GitHub token (`uv run pytest -m integration`). If integration coverage should run in Actions (which has network), change the workflow line to `uv run pytest -m integration` or drop the addopts filter explicitly.

No secrets, caches, or matrix strategy are used in the current file.

---

## Match CI locally

From the repository root, the same sequence CI uses is:

```bash
uv sync --all-groups
uv run ruff check src tests
uv run pytest -q
```

This matches [`CLAUDE.md`](../CLAUDE.md) and what GitHub Actions runs. Optional: `uv run pytest -m integration` to run only tests marked `integration` (intended for cases that need network or a GitHub token).

---

## Changing behavior

| Goal | Where to edit |
|------|----------------|
| Dependencies, Python bound, test markers, ruff line length | `pyproject.toml` |
| Triggers, OS, `uv` version, ruff/test commands or args | `workflows/ci.yml` |
| What agents should know about this folder in one pass | `AGENTS.md` |

After editing the workflow, validate with Actions on a branch or a fork before merging to `main`.

---

## Related docs

- [Root `README.md`](../README.md) — project overview and how to run the `sunspot` CLI.
- [`CLAUDE.md`](../CLAUDE.md) — contributor commands, architecture sketch, and cache paths.
- [`SPEC.md`](../SPEC.md) — product scope and non-goals (e.g. causal inference out of v1).
