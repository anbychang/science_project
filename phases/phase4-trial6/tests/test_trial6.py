"""Small checks for Trial6 solar geometry and source-disjoint blocks."""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from calc_trial6_daylight import day_flags
from calc_trial6_interpolation_rule import decide, same_sign_decision
from calc_trial6_ridge import block_masks, time_features
from calc_trial6_stress import HOUR_US, MINUTE_US, most_variable_start


class Trial6Checks(unittest.TestCase):
    """Input: synthetic sample and anchor records. Output: geometry/holdout checks."""

    def test_local_noon_and_midnight(self) -> None:
        """Input: equinox Greenwich noon/midnight. Output: day then night."""
        times = [datetime(2024, 3, 20, hour, tzinfo=timezone.utc)
                 for hour in (12, 0)]
        samples = [{"time_us": round(time.timestamp() * 1_000_000),
                    "latitude_deg": 0.0, "longitude_deg": 0.0} for time in times]
        self.assertEqual(day_flags(samples).tolist(), [True, False])

    def test_block_excludes_shared_source_support(self) -> None:
        """Input: adjacent overlapping orbit supports. Output: disjoint train set."""
        rows = [{"elapsed_hours": float(hour), "support_start_us": hour * 10 - 6,
                 "support_end_us": hour * 10 + 6} for hour in range(24)]
        masks = block_masks(rows, 6.0)
        self.assertIsNotNone(masks)
        self.assertFalse(np.any(masks["train"] & masks["test"]))
        self.assertFalse(masks["train"][5])
        self.assertFalse(masks["train"][12])
        self.assertTrue(masks["train"][4])
        self.assertTrue(masks["train"][13])

    def test_time_bends_at_fixed_twelve_hours(self) -> None:
        """Input: [0,12,24,36] h. Output: fixed 12-hour hinge columns."""
        features = time_features(np.array([0.0, 12.0, 24.0, 36.0]))
        np.testing.assert_allclose(features[:, 0], [0.0, 1.0, 2.0, 3.0])
        np.testing.assert_allclose(features[:, 1], [0.0, 0.0, 1.0, 2.0])

    def test_activity_window_stays_outside_t0(self) -> None:
        """Input: strong late SYM-H swings. Output: late six-hour window."""
        minutes = np.arange(36 * 60, dtype=np.int64) * MINUTE_US
        symh = np.zeros(len(minutes))
        symh[24 * 60:30 * 60] = np.tile(np.repeat([-100.0, 0.0], 30), 6)
        rows = [{"time_us": 0}, {"time_us": 36 * HOUR_US}]
        start_us, variation = most_variable_start(
            rows, {"t0_us": 12 * HOUR_US, "minute_us": minutes, "symh_nt": symh}
        )
        self.assertEqual(start_us, 24 * HOUR_US)
        self.assertGreater(variation, 0)

    def test_interpolation_decisions_do_not_read_hidden_residual(self) -> None:
        """Input: same visible shoulders, changed hidden values. Output: same decisions."""
        rows = [{"storm_id": "synthetic", "time_us": hour * HOUR_US,
                 "elapsed_hours": float(hour),
                 "support_start_us": hour * HOUR_US - MINUTE_US,
                 "support_end_us": hour * HOUR_US + MINUTE_US,
                 "residual_log_density": 0.1} for hour in range(60)]
        changed = [row.copy() for row in rows]
        for row in changed[24:30]:
            row["residual_log_density"] = -9.0
        self.assertEqual(decide(rows, 24 * HOUR_US), decide(changed, 24 * HOUR_US))
        self.assertEqual(same_sign_decision(rows, 24 * HOUR_US),
                         same_sign_decision(changed, 24 * HOUR_US))


if __name__ == "__main__":
    unittest.main()
