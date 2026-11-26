#!/usr/bin/env python3
"""Stage the author's archived SSN illustration without recomputing its statistics."""

import json
import shutil
from pathlib import Path


def main() -> None:
    """Copy the archived plot and record its render label and alternative text."""
    project = Path(__file__).resolve().parents[1]
    figures = project / "output" / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    filename = "archived-author-ssn-scatter.png"
    archived_plot = project / "report" / "docxology" / "ssn" / "scatter.png"
    shutil.copyfile(archived_plot, figures / filename)
    registry = {
        "figures": [
            {
                "label": "fig:archived-author-ssn",
                "filename": filename,
                "caption": "Archived repository-author SSN scatterplot.",
                "alt_text": (
                    "Scatterplot of daily activity counts against the daily sunspot number "
                    "from the repository author's archived run."
                ),
            },
        ],
    }
    (figures / "figure_registry.json").write_text(
        json.dumps(registry, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
