# `output/github_data/`

**Portable GitHub client state** for this working copy: one directory you can
tar/rsync to reuse fetches and avoid extra API work on another machine.

| path | role |
|------|------|
| `commit_series/{login}/` | Per-repo daily commit-count CSVs + `.meta.json` (window-specific filenames). |
| `github_cache.sqlite3` | SHA dedup while paging `/repos/{owner}/{repo}/commits` (unless overridden). |

**Overrides**

- `SUNSPOT_COMMIT_SERIES` — absolute path: alternate root for `commit_series/` layout (replaces the default under this folder, not merged).
- `SUNSPOT_CACHE` — directory: place `github_cache.sqlite3` there instead of this folder.

**Legacy**

- Reads still fall back to `~/.cache/sunspot/commit_series/` for cache **hits**;
  new **writes** go to `commit_series/` here (or `SUNSPOT_COMMIT_SERIES`).
- If `github_cache.sqlite3` is missing but `~/.cache/sunspot/github_cache.sqlite3`
  exists, it is **copied once** on first use.

**Note:** Resolve paths from the **repository root** (`Path.cwd()` when you run
`uv run sunspot` from the project). Science dataset URL caches stay under
`~/.cache/sunspot/url/` (or `XDG_CACHE_HOME`); only GitHub user/repo state uses
this tree by default.
