"""Check the Trial4 residual GPR contracts."""

import unittest

import numpy as np

from phases.phase4.code.calc_phase4_trial4_gpr import FEATURE_NAMES, fit_gpr, score
from phases.phase4.code.calc_phase4_trial4_groupcv import split_storm_folds
from phases.phase4.code.calc_phase4_trial4_groupcv_diagnostics import nearest_distances
from phases.phase4.code.calc_phase4_trial4_trial3 import (
    SELECTION_CANDIDATES,
    candidate_features,
    select_candidate,
)
from phases.phase4.code.prep_phase4_trial4_trial3 import inner_folds
from phases.phase4.code.calc_phase4_trial4_time_tau_season import feature_matrix as time_tau_season_features
from phases.phase4.code.calc_phase4_trial5_drivers import backward_rate
from phases.phase4.code.prep_phase4_trial5_gpr import feature_matrix as trial5_feature_matrix


class Phase4Trial4GprTests(unittest.TestCase):
    """Input: synthetic Trial4 residuals. Output: Phase 4 GPR contract checks."""

    def test_gpr_uses_five_features(self) -> None:
        """Input: four feature columns. Output: rejected Phase 4 feature shape."""
        with self.assertRaises(ValueError):
            fit_gpr(np.ones((4, 4)), np.zeros(4))

    def test_score_reports_trial4_and_gpr_error(self) -> None:
        """Input: residual and exact GPR mean. Output: zero corrected error."""
        residual = np.array([0.2, -0.1])
        result = score(residual, residual, np.ones(2))
        self.assertEqual(len(FEATURE_NAMES), 5)
        self.assertAlmostEqual(result["gpr_rmse_log_density"], 0.0)

    def test_group_cv_keeps_every_test_storm_out_of_its_training_fold(self) -> None:
        """Input: two anchors per 25 storms. Output: five disjoint 20/5 storm folds."""
        storm_ids = np.repeat([f"S{index:02d}" for index in range(25)], 2)
        folds = split_storm_folds(storm_ids)
        self.assertEqual(len(folds), 5)
        for train_indices, test_indices in folds:
            self.assertEqual(
                set(storm_ids[train_indices]) & set(storm_ids[test_indices]), set()
            )
            self.assertEqual(len(set(storm_ids[test_indices])), 5)

    def test_nearest_distances_returns_nearest_training_point(self) -> None:
        """Input: two training points and one test point. Output: nearest Euclidean distance."""
        distance = nearest_distances(
            np.array([[0.0, 0.0], [3.0, 4.0]]), np.array([[1.0, 0.0]])
        )
        self.assertAlmostEqual(distance[0], 1.0)

    def test_trial3_candidates_exclude_altitude(self) -> None:
        """Input: five source features. Output: Trial3 candidate has four geomagnetic features."""
        selected = candidate_features(np.ones((2, 5)), SELECTION_CANDIDATES[0])
        self.assertEqual(selected.shape[1], 4)

    def test_trial3_selects_lowest_inner_rmse(self) -> None:
        """Input: two inner candidate scores. Output: lowest-RMSE candidate name."""
        selected = select_candidate([
            {"candidate_name": "first", "inner_rmse_log_density": 0.2},
            {"candidate_name": "second", "inner_rmse_log_density": 0.1},
        ])
        self.assertEqual(selected, "second")

    def test_trial3_inner_folds_keep_five_storms_for_validation(self) -> None:
        """Input: 20 outer-training storms. Output: four disjoint 15/5 inner splits."""
        storm_ids = np.repeat([f"S{index:02d}" for index in range(20)], 2)
        folds = inner_folds(storm_ids, outer_fold_index=1)
        valid = all(
            len(set(storm_ids[train_indices])) == 15
            and len(set(storm_ids[test_indices])) == 5
            and not set(storm_ids[train_indices]) & set(storm_ids[test_indices])
            for train_indices, test_indices in folds
        )
        self.assertTrue(valid)

    def test_trial4_time_tau_season_features_use_event_relative_time(self) -> None:
        """Input: storm event anchor. Output: zero relative event time."""
        features = time_tau_season_features([{
            "storm_id": "S20230805T0546",
            "time_us": 1691214360000000,
            "tau_hours": 6.2,
        }])
        self.assertAlmostEqual(features[0, 0], 0.0)

    def test_trial5_symh_rate_is_backward_difference(self) -> None:
        """Input: two one-second SYM-H values. Output: backward change rate."""
        rate = backward_rate(
            np.array([0, 1_000_000], dtype=np.int64), np.array([-10.0, -12.0])
        )
        self.assertAlmostEqual(rate[1], -2.0)

    def test_trial5_gpr_uses_three_new_driver_features(self) -> None:
        """Input: one Trial5 anchor. Output: three direct driver columns."""
        features = trial5_feature_matrix([{
            "symh_rate_nt_s": 0.1,
            "ap_step": 10.0,
            "f107_sfu": 150.0,
        }])
        self.assertEqual(features.shape, (1, 3))


if __name__ == "__main__":
    unittest.main()
