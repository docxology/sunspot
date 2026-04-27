from pathlib import Path

from sunspot.datasets.omni import _parse_omni2_hourly_line, _parse_omni2_hourly_lines

FIX = Path(__file__).parent / "fixtures" / "omni2_oneline.txt"


def test_omni2_line() -> None:
    line = FIX.read_text().strip()
    p = _parse_omni2_hourly_line(line)
    assert p is not None
    _t, f107, _dst, _r, ap = p
    assert abs(f107 - 72.7) < 0.1
    assert ap == 0.0 or ap == 0


def test_omni2_daily_rollup() -> None:
    line = FIX.read_text().strip()
    df = _parse_omni2_hourly_lines([line], year=2010)
    d = df.resample("1D").mean()
    assert not d.empty
    assert "f107" in d.columns
    assert d["f107"].iloc[0] == df["f107"].iloc[0]
