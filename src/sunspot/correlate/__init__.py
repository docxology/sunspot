"""Join commit activity with geophysical series and emit artifacts."""

from __future__ import annotations

from sunspot.github.commits import public_commit_time_series

from ._io import (
    _write_commit_rollups,
    _write_methods,
    _write_per_user_commits,
    default_correlate_dir,
)
from ._report_helpers import _commits_daily_summary, _format_summary
from ._series import _series_for_metric
from .pipeline import run_correlation_report

__all__ = [
    "default_correlate_dir",
    "public_commit_time_series",
    "run_correlation_report",
    "_commits_daily_summary",
    "_format_summary",
    "_series_for_metric",
    "_write_commit_rollups",
    "_write_methods",
    "_write_per_user_commits",
]
