# fixtures/

Real file snippets consumed by the pytest suite — format drift in external
data sources surfaces as a failing parse, never silent numeric corruption.

| file | used by | format |
|------|---------|--------|
| `silso_snippet.csv` | SILSO parser tests | WDC-SILSO daily total V2.0 semicolon format |
| `omni2_oneline.txt` | OMNI2 parser tests | OMNI2 hourly line format |
| `github_commit.json` | GitHub model tests | `/repos/{owner}/{repo}/commits` JSON payload |
| `cohort_logins.txt` | cohort tests | one login per line (`read_logins_file` input) |

Parent: [`../README.md`](../README.md). Local-only — never commit.
