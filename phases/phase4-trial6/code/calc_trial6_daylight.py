"""Classify local atmospheric day side from sample UTC and geographic position."""

import numpy as np
from astropy import units as u
from astropy.coordinates import AltAz, EarthLocation, get_sun
from astropy.time import Time
from astropy.utils import iers


iers.conf.auto_download = False


def day_flags(samples: list[dict]) -> np.ndarray:
    """Input: [{time_us, latitude_deg, longitude_deg}]. Output: [day-side bool]."""
    if not samples:
        return np.empty(0, dtype=bool)
    times = Time(
        np.array([sample["time_us"] for sample in samples], dtype=np.int64) / 1_000_000,
        format="unix", scale="utc",
    )
    locations = EarthLocation(
        lat=np.array([sample["latitude_deg"] for sample in samples]) * u.deg,
        lon=np.array([sample["longitude_deg"] for sample in samples]) * u.deg,
        height=0 * u.m,
    )
    solar_altitude = get_sun(times).transform_to(
        AltAz(obstime=times, location=locations, pressure=0 * u.hPa)
    ).alt.deg
    return np.asarray(solar_altitude > 0, dtype=bool)
