"""Change time values used by orbit data."""

from datetime import datetime, timezone

from astropy.time import Time
from astropy.utils import iers

GPS_EPOCH = datetime(1980, 1, 6)
iers.conf.auto_download = False


def gps_time_to_utc(time_gps):
    """Input: GPS datetime
    Output: UTC datetime"""
    seconds_after_gps_epoch = (time_gps - GPS_EPOCH).total_seconds()
    time_utc = Time(seconds_after_gps_epoch, format="gps").utc
    return time_utc.to_datetime(timezone=timezone.utc)


def gps_times_to_utc(times_gps):
    """Input: [GPS datetime, ...]
    Output: [UTC datetime, ...]"""
    if len(times_gps) == 0:
        return []

    first_gps = times_gps[0].replace(tzinfo=timezone.utc)
    last_gps = times_gps[-1].replace(tzinfo=timezone.utc)
    first_offset = gps_time_to_utc(times_gps[0]) - first_gps
    last_offset = gps_time_to_utc(times_gps[-1]) - last_gps

    if first_offset == last_offset:
        return [
            time_gps.replace(tzinfo=timezone.utc) + first_offset
            for time_gps in times_gps
        ]

    return [gps_time_to_utc(time_gps) for time_gps in times_gps]
