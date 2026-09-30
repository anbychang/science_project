"""Check P1.5-A UTC 10-minute bin summaries."""

import unittest

from satellite_orbit.data.prep_orbit_bins import (
    MICROSECONDS_PER_SECOND,
    TEN_MINUTE_BIN_US,
    summarize_single_interval_ten_minute_bin,
)


def bin_observations():
    """Input: none
    Output: 60 regular POD observations from one UTC bin"""
    bin_start_time_us = 1_200_000_000
    return [
        {"time_us": bin_start_time_us + index * 10 * MICROSECONDS_PER_SECOND, "interval_id": 4}
        for index in range(60)
    ]


class OrbitBinTest(unittest.TestCase):
    """Input: small synthetic POD observations
    Output: UTC bin integrity decisions"""

    def test_summarizes_one_regular_bin(self):
        """Input: 60 ten-second observations from one interval
        Output: count, bounds, gap, and interval summary"""
        observations = bin_observations()

        result = summarize_single_interval_ten_minute_bin(observations)

        self.assertEqual(
            result,
            {
                "time_us": 1_200_000_000,
                "pod_count": 60,
                "first_pod_time_us": 1_200_000_000,
                "last_pod_time_us": 1_790_000_000,
                "max_pod_gap_s": 10.0,
                "interval_id": 4,
            },
        )

    def test_rejects_cross_interval_observations(self):
        """Input: one UTC bin containing two interval identifiers
        Output: ValueError"""
        observations = bin_observations()
        observations[-1]["interval_id"] = 5

        with self.assertRaises(ValueError):
            summarize_single_interval_ten_minute_bin(observations)

    def test_rejects_cross_bin_observations(self):
        """Input: observations on opposite sides of a UTC bin boundary
        Output: ValueError"""
        observations = [
            {"time_us": TEN_MINUTE_BIN_US - 10 * MICROSECONDS_PER_SECOND, "interval_id": 4},
            {"time_us": TEN_MINUTE_BIN_US, "interval_id": 4},
        ]

        with self.assertRaises(ValueError):
            summarize_single_interval_ten_minute_bin(observations)

    def test_rejects_non_increasing_observations(self):
        """Input: duplicate time_us values in one bin
        Output: ValueError"""
        observations = bin_observations()
        observations[1]["time_us"] = observations[0]["time_us"]

        with self.assertRaises(ValueError):
            summarize_single_interval_ten_minute_bin(observations)


if __name__ == "__main__":
    unittest.main()
