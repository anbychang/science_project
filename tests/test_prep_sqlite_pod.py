"""Check POD weather-block alignment."""

import unittest
from datetime import datetime, timezone

from satellite_orbit.data.prep_sqlite_pod import weather_block_time


class PodWeatherBlockTest(unittest.TestCase):
    """Input: UTC POD times near a 3-hour boundary
    Output: their official weather-block starts"""

    def test_time_before_boundary_uses_previous_block(self):
        """Input: 02:59 UTC
        Output: 00:00 UTC block start"""
        time_utc = datetime(2026, 1, 1, 2, 59, tzinfo=timezone.utc)

        self.assertEqual(
            weather_block_time(time_utc),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

    def test_time_at_boundary_uses_new_block(self):
        """Input: 03:00 UTC
        Output: 03:00 UTC block start"""
        time_utc = datetime(2026, 1, 1, 3, tzinfo=timezone.utc)

        self.assertEqual(weather_block_time(time_utc), time_utc)


if __name__ == "__main__":
    unittest.main()
