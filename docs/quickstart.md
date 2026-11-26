# Install, verify, and render Sunspot

## Local setup and checks

The package supports Python 3.12 and newer. The repository selects Python
3.15 in `.python-version`. With uv installed, run from the repository root:

```sh
uv sync --locked --all-groups
uv run --no-sync sunspot --help
uv run --no-sync sunspot correlate --help
uv run --no-sync ruff check src tests scripts
uv run --no-sync pytest -q -m 'not integration'
```

The offline tests use saved solar-source parser snippets and synthetic
daily series for report tests. Integration tests use external services and
are excluded in the default profile. Existing
[author report artifacts](../report/docxology/README.md) can be inspected
directly as JSON, CSV, and PNG files.

| Surface | Location |
| --- | --- |
| Package configuration and caches | [Configuration reference](configuration.md) |
| Statistical transformations and interpretation | [Methods guides](methods/README.md) |
| Report JSON, analysis tables, and plots | [Output layout](../output/README.md) |
| Archived documentation example | [Author report](../report/docxology/README.md) |

## Pinned manuscript build

Install Python 3.14, uv, Pandoc 3.14, matching pandoc-crossref v0.3.26b,
and XeLaTeX with the [Template TeX packages](https://github.com/docxology/template/blob/87704feae0a4490ef7dad9c931d268e8c30273c2/README.md#L565-L574).
Set `SUNSPOT_CHECKOUT` to the absolute path of the source checkout.

```sh
git clone https://github.com/docxology/template.git sunspot-template-runner
cd sunspot-template-runner
git checkout --detach 87704feae0a4490ef7dad9c931d268e8c30273c2
uv sync --locked --python 3.14
project=projects/working/sunspot
mkdir -p projects/working
git -C "$SUNSPOT_CHECKOUT" worktree add --no-checkout --detach "$PWD/$project" HEAD
git -C "$project" sparse-checkout set --no-cone '/*' '!/output/'
git -C "$project" read-tree -mu HEAD
uv run --no-sync python "$project/scripts/01_prepare_manuscript.py"
uv run --no-sync python scripts/pipeline/stage_03_render.py --project working/sunspot
uv run --no-sync python scripts/pipeline/stage_04_validate.py --project working/sunspot
```

The sparse checkout omits the tracked `output/` archive so the verification
stage sees only new build artifacts. The figure preparer copies the saved
author example plot byte-for-byte. The archived report JSON supplies the
quoted coefficients.

Inspect `$project/output/pdf/sunspot_combined.pdf`,
`$project/output/web/index.html`, and
`$project/output/reports/validation_report.md`. The rendered provenance
receipt sits alongside the validation report.
