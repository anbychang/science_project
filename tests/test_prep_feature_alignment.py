"""Check P1.6 raw feature alignment rules."""

import unittest
from datetime import datetime, timezone

from satellite_orbit.data.prep_feature_alignment import (
    MICROSECONDS_PER_DAY,
    MICROSECONDS_PER_MINUTE,
    align_space_weather,
    align_sym_h,
)


def time_us(hour, minute, second=0):
    """Input: UTC clock fields on 2024-05-10
    Output: Unix time in microseconds"""
    time_utc = datetime(2024, 5, 10, hour, minute, second, tzinfo=timezone.utc)
    return round(time_utc.timestamp() * 1_000_000)


def weather_row(ap_now):
    """Input: current Ap value
    Output: one prepared space-weather row"""
    return {
        "ap_now": ap_now,
        "f107_sfu": 120.0,
        "f107a_sfu": 110.0,
        "f107a_last81_sfu": 105.0,
        "f107_data_type": "OBSERVED",
    }


class FeatureAlignmentTest(unittest.TestCase):
    """Input: small raw feature records
    Output: P1.6 source-time alignment decisions"""

    def test_sym_h_keeps_an_exact_minute(self):
        """Input: a SYM-H observation at the target minute
        Output: its value and one exact source time"""
        target_time_us = time_us(12, 0)

        result = align_sym_h(
            target_time_us,
            [{"time_us": target_time_us, "sym_h_nt": -45.0}],
        )

        self.assertEqual(
            result,
            {
                "sym_h_nt": -45.0,
                "sym_h_left_time_us": target_time_us,
                "sym_h_right_time_us": target_time_us,
            },
        )

    def test_sym_h_interpolates_inside_one_minute_gap(self):
        """Input: target halfway between adjacent minute observations
        Output: linear SYM-H interpolation with both source times"""
        target_time_us = time_us(12, 0, 30)

        result = align_sym_h(
            target_time_us,
            [
                {"time_us": time_us(12, 0), "sym_h_nt": -40.0},
                {"time_us": time_us(12, 1), "sym_h_nt": -60.0},
            ],
        )

        self.assertEqual(result["sym_h_nt"], -50.0)

    def test_sym_h_does_not_cross_a_three_minute_gap(self):
        """Input: target inside a three-minute SYM-H source gap
        Output: missing feature"""
        result = align_sym_h(
            time_us(12, 1),
            [
                {"time_us": time_us(12, 0), "sym_h_nt": -40.0},
                {"time_us": time_us(12, 3), "sym_h_nt": -60.0},
            ],
        )

        self.assertIsNone(result)

    def test_sym_h_does_not_use_only_a_future_observation(self):
        """Input: target before the first SYM-H source observation
        Output: missing feature"""
        result = align_sym_h(
            time_us(12, 0),
            [{"time_us": time_us(12, 1), "sym_h_nt": -40.0}],
        )

        self.assertIsNone(result)

    def test_ap_before_boundary_uses_current_block(self):
        """Input: 02:59:59 UTC and two Ap blocks
        Output: 00:00 block value and source time"""
        first_block_time_us = time_us(0, 0)
        result = align_space_weather(
            time_us(2, 59, 59),
            {
                first_block_time_us: weather_row(4.0),
                time_us(3, 0): weather_row(20.0),
                first_block_time_us - MICROSECONDS_PER_DAY: weather_row(4.0),
            },
        )

        self.assertEqual(
            (result["ap_now"], result["ap_source_time_us"]),
            (4.0, first_block_time_us),
        )

    def test_ap_at_boundary_uses_new_block(self):
        """Input: 03:00:00 UTC and two Ap blocks
        Output: 03:00 block value and source time"""
        second_block_time_us = time_us(3, 0)
        result = align_space_weather(
            second_block_time_us,
            {
                time_us(0, 0): weather_row(4.0),
                second_block_time_us: weather_row(20.0),
                time_us(0, 0) - MICROSECONDS_PER_DAY: weather_row(4.0),
            },
        )

        self.assertEqual(
            (result["ap_now"], result["ap_source_time_us"]),
            (20.0, second_block_time_us),
        )

    def test_f107_and_f107a_keep_separate_source_days(self):
        """Input: a noon weather row and its previous daily source
        Output: F10.7 and causal F10.7A source times"""
        target_time_us = time_us(12, 0)
        result = align_space_weather(
            target_time_us,
            {
                time_us(12, 0): weather_row(4.0),
                time_us(0, 0) - MICROSECONDS_PER_DAY: weather_row(4.0),
            },
        )

        self.assertEqual(
            (result["f107_source_time_us"], result["f107a_source_time_us"]),
            (time_us(0, 0) - MICROSECONDS_PER_DAY,) * 2,
        )

    def test_f107a_uses_trailing_average(self):
        """Input: centered and trailing F10.7A values
        Output: the causal trailing value"""
        target_time_us = time_us(12, 0)
        result = align_space_weather(
            target_time_us,
            {
                target_time_us: weather_row(4.0),
                time_us(0, 0) - MICROSECONDS_PER_DAY: weather_row(4.0),
            },
        )

        self.assertEqual(result["f107a_sfu"], 105.0)

    def test_missing_weather_block_keeps_features_missing(self):
        """Input: target without its official Ap block
        Output: missing weather feature"""
        result = align_space_weather(time_us(12, 0), {})

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
