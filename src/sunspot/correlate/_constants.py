"""Shared paths and spectral band definitions for the correlate pipeline."""

from __future__ import annotations

from pathlib import Path

SPECTRAL_BANDS_DAYS: dict[str, tuple[float, float]] = {
    "weekly": (6.0, 8.0),
    "solar_rotation": (24.0, 31.0),
    "annual": (330.0, 400.0),
    "solar_cycle": (3650.0, 4380.0),
}

OUTPUT_ROOT = Path("output")
DIR_STATISTICS = "statistics"
DIR_DATA = "data"
DIR_VIS = "visualizations"
DIR_ANALYSIS = "analysis"
