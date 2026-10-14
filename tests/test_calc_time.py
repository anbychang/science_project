"""Check GPS-to-UTC conversion at the leap-second boundary."""

import unittest
from datetime import datetime, timezone

from satellite_orbit.calculation.calc_time import gps_times_to_utc


class GpsTimeConversionTest(unittest.TestCase):
    """Input: GPS datetimes
    Output: UTC datetimes"""

    def test_keeps_the_gps_epoch(self):
        """Input: GPS epoch
        Output: identical UTC epoch"""
        result = gps_times_to_utc([datetime(1980, 1, 6)])

        self.assertEqual(result, [datetime(1980, 1, 6, tzinfo=timezone.utc)])

    def test_converts_each_side_of_the_2016_leap_second(self):
        """Input: GPS times immediately before and after a leap second
        Output: matching UTC times with different offsets"""
        result = gps_times_to_utc(
            [
                datetime(2017, 1, 1, 0, 0, 16),
                datetime(2017, 1, 1, 0, 0, 18),
            ]
        )

        self.assertEqual(
            result,
            [
                datetime(2016, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
                datetime(2017, 1, 1, tzinfo=timezone.utc),
            ],
        )


if __name__ == "__main__":
    unittest.main()
