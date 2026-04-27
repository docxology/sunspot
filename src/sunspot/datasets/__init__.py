"""Fetch and parse public solar / geomagnetic time series."""

from sunspot.datasets.noaa_swpc import load_noaa_daily_solar_indices
from sunspot.datasets.omni import load_omni2_daily
from sunspot.datasets.silso import SILSO_DAILY_TOT_V2_URL, load_silso_daily_tot_v2

__all__ = [
    "SILSO_DAILY_TOT_V2_URL",
    "load_noaa_daily_solar_indices",
    "load_omni2_daily",
    "load_silso_daily_tot_v2",
]
