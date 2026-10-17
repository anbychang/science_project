"""Check causal P1.6 feature-alignment rules."""

import unittest
from datetime import datetime, timezone

from satellite_orbit.calculation.analysis.calc_feature_alignment import (
    align_space_weather,
    align_sym_h,
    feature_quality_flags,
)
from satellite_orbit.data.database.prep_raw_identifiers import time_to_us


def utc_time_us(day, hour=0, minute=0, second=0):
    """Input: UTC calendar fields
    Output: Unix time in microseconds"""
    return time_to_us(datetime(2024, 5, day, hour, minute, second, tzinfo=timezone.utc))


def weather_row(ap_now, f107_sfu, f107a_last81_sfu):
    """Input: weather feature values
    Output: one minimal raw space-weather row"""
    return {
        "ap_now": ap_now,
        "f107_sfu": f107_sfu,
        "f107a_last81_sfu": f107a_last81_sfu,
        "f107_data_type": "OBSERVED",
    }


class FeatureAlignmentTest(unittest.TestCase):
    """Input: raw P1.6 source records
    Output: causal feature values and missing flags"""

    def test_keeps_exact_sym_h_minute(self):
        """Input: exact SYM-H observation
        Output: exact value and duplicate source time"""
        target_time_us = utc_time_us(10, 14, 20)

        features = align_sym_h(
            target_time_us,
            {"time_us": target_time_us, "sym_h_nt": -47.0},
            None,
        )

        self.assertEqual(
            features,
            {
                "sym_h_nt": -47.0,
                "sym_h_left_time_us": target_time_us,
                "sym_h_right_time_us": target_time_us,
            },
        )

    def test_interpolates_sym_h_only_across_two_minute_gap(self):
        """Input: target halfway through a two-minute SYM-H gap
        Output: linear interpolation with both source times"""
        target_time_us = utc_time_us(10, 14, 20)

        features = align_sym_h(
            target_time_us,
            {"time_us": target_time_us - 60_000_000, "sym_h_nt": -50.0},
            {"time_us": target_time_us + 60_000_000, "sym_h_nt": -40.0},
        )

        self.assertEqual(features["sym_h_nt"], -45.0)

    def test_rejects_sym_h_gap_larger_than_two_minutes(self):
        """Input: target inside a three-minute SYM-H gap
        Output: missing SYM-H fields"""
        target_time_us = utc_time_us(10, 14, 20)

        features = align_sym_h(
            target_time_us,
            {"time_us": target_time_us - 60_000_000, "sym_h_nt": -50.0},
            {"time_us": target_time_us + 120_000_000, "sym_h_nt": -40.0},
        )

        self.assertIsNone(features["sym_h_nt"])

    def test_rejects_future_only_sym_h_observation(self):
        """Input: one SYM-H observation after target
        Output: no future-only fill"""
        target_time_us = utc_time_us(10, 14, 20)

        features = align_sym_h(
            target_time_us,
            None,
            {"time_us": target_time_us + 60_000_000, "sym_h_nt": -40.0},
        )

        self.assertIsNone(features["sym_h_nt"])

    def test_uses_previous_ap_block_before_three_hour_boundary(self):
        """Input: target at 02:59:59 UTC
        Output: 00:00 UTC Ap block"""
        target_time_us = utc_time_us(10, 2, 59, 59)
        weather = {
            utc_time_us(10): weather_row(7.0, 130.0, 111.0),
            utc_time_us(9): weather_row(6.0, 129.0, 110.0),
        }

        features = align_space_weather(target_time_us, weather)

        self.assertEqual(features["ap_source_time_us"], utc_time_us(10))

    def test_uses_new_ap_block_at_three_hour_boundary(self):
        """Input: target at 03:00:00 UTC
        Output: 03:00 UTC Ap block"""
        target_time_us = utc_time_us(10, 3)
        weather = {
            utc_time_us(10, 3): weather_row(8.0, 130.0, 111.0),
            utc_time_us(9): weather_row(6.0, 129.0, 110.0),
        }

        features = align_space_weather(target_time_us, weather)

        self.assertEqual(features["ap_source_time_us"], utc_time_us(10, 3))

    def test_uses_prior_day_f107_and_trailing_f107a(self):
        """Input: target-block and preceding-day weather rows
        Output: prior-day source times and trailing F10.7A"""
        target_time_us = utc_time_us(10, 14, 20)
        weather = {
            utc_time_us(10, 12): weather_row(13.0, 130.0, 999.0),
            utc_time_us(9): weather_row(6.0, 129.0, 110.0),
        }

        features = align_space_weather(target_time_us, weather)

        self.assertEqual(
            (features["f107_sfu"], features["f107a_sfu"]),
            (129.0, 110.0),
        )
        self.assertEqual(
            (features["f107_source_time_us"], features["f107a_source_time_us"]),
            (utc_time_us(9), utc_time_us(9)),
        )

    def test_flags_missing_weather_without_future_fill(self):
        """Input: only a next-day weather record
        Output: missing weather fields and controlled flag"""
        target_time_us = utc_time_us(10, 14, 20)
        weather = {utc_time_us(11, 12): weather_row(13.0, 131.0, 112.0)}

        weather_features = align_space_weather(target_time_us, weather)
        quality_flags = feature_quality_flags(
            {"sym_h_nt": -30.0},
            weather_features,
        )

        self.assertIsNone(weather_features["f107_sfu"])
        self.assertEqual(quality_flags, "missing_space_weather")

    def test_combines_missing_feature_flags(self):
        """Input: missing SYM-H and weather fields
        Output: stable joined quality flags"""
        quality_flags = feature_quality_flags(
            {"sym_h_nt": None},
            {"ap_now": None},
        )

        self.assertEqual(quality_flags, "missing_sym_h|missing_space_weather")


if __name__ == "__main__":
    unittest.main()
