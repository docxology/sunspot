"""
Optional network integration tests. Default ``uv run pytest`` (and CI) skip
them via ``addopts = -m not integration`` in ``pyproject.toml``.

- Only integration: ``uv run pytest -m integration -q``
- Full suite including integration: ``uv run pytest -m "integration or not integration" -q``
"""

from __future__ import annotations

import pytest

from sunspot.datasets.cache import ensure_cached_url
from sunspot.datasets.silso import SILSO_DAILY_TOT_V2_URL


@pytest.mark.integration
def test_ensure_cached_url_silso_v2() -> None:
    """Fetches the pinned SILSO CSV header (or uses cache) — real HTTP."""
    p = ensure_cached_url(SILSO_DAILY_TOT_V2_URL, suffix=".csv")
    assert p.is_file()
    assert p.stat().st_size > 500
    text = p.read_text(encoding="utf-8", errors="replace")[:400]
    # SILSO V2.0: semicolon-separated numeric rows (year; month; day; …)
    assert ";" in text and any(c.isdigit() for c in text)
