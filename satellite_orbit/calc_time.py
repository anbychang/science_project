"""Change time values used by orbit data."""

from datetime import datetime, timezone

from astropy.time import Time


GPS_EPOCH = datetime(1980, 1, 6)


def gps_time_to_utc(time_gps):
    """Input: GPS datetime
    Output: UTC datetime"""
    seconds_after_gps_epoch = (time_gps - GPS_EPOCH).total_seconds()
    time_utc = Time(seconds_after_gps_epoch, format="gps").utc
    return time_utc.to_datetime(timezone=timezone.utc)
