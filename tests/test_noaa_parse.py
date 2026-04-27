import io

from sunspot.datasets.noaa_swpc import _parse_daily_solar_indices

SAMPLE = """# test
# Date  10.7  SSN
:Product: x
2026 03 24 128 113 750
2026 03 25 140 103 735
"""


def test_noaa_parse() -> None:
    df = _parse_daily_solar_indices(io.StringIO(SAMPLE))
    assert len(df) == 2
    assert float(df["f107"].iloc[0]) == 128.0
