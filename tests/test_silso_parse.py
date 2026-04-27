import io
from pathlib import Path

import pandas as pd

from sunspot.datasets.silso import _parse_silso_csv

FIX = Path(__file__).resolve().parent / "fixtures" / "silso_snippet.csv"


def test_parse_silso_snippet() -> None:
    text = FIX.read_text(encoding="utf-8")
    df = _parse_silso_csv(io.StringIO(text))
    assert "ssn" in df.columns
    assert len(df) >= 1
    assert df["ssn"].iloc[0] == 0.0
    assert isinstance(df.index, pd.DatetimeIndex)
