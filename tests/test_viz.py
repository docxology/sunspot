from pathlib import Path

import pandas as pd

from sunspot.stats.correlation import LagResult, lag_correlation_search
from sunspot.viz.plots import save_lag_plot, save_scatter


def test_save_plots(tmp_path: Path) -> None:
    idx = pd.date_range("2020-01-01", periods=20, freq="D")
    c = pd.Series(range(20), index=idx, name="c")
    s = pd.Series((range(20)), index=idx, name="g")
    save_scatter(c, s, out=tmp_path / "s.png")
    lag = lag_correlation_search(c, s, max_lag=3)
    assert isinstance(lag, LagResult)
    save_lag_plot(lag, out=tmp_path / "l.png")
    assert (tmp_path / "s.png").is_file()
    assert (tmp_path / "l.png").is_file()
