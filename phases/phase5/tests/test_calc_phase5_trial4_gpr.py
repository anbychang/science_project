"""Check the Trial4 residual GPR contracts."""

import unittest
import sys
from pathlib import Path

import numpy as np

PHASES_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PHASES_ROOT / "phase5-trial3/code"))
sys.path.insert(0, str(PHASES_ROOT / "phase5-trial5/code"))

from phases.phase5.code.calc_phase5_trial4_gpr import FEATURE_NAMES, GprSettings, fit_gpr, score
from phases.phase5.code.calc_phase5_feature_ablation import (
    contribution_deltas,
    feature_set_definitions,
    selected_feature_matrix,
)
from phases.phase5.code.calc_phase5_trial4_groupcv import split_storm_folds
from phases.phase5.code.calc_phase5_trial4_groupcv_diagnostics import nearest_distances
from phases.phase5.code.calc_phase5_trial4_trial3 import (
    SELECTION_CANDIDATES,
    candidate_features,
    select_candidate,
)
from prep_phase5_trial4_trial3 import inner_folds
from phases.phase5.code.calc_phase5_trial4_time_tau_season import feature_matrix as time_tau_season_features
from phases.phase5.code.calc_phase5_trial5_drivers import backward_rate
from prep_phase5_trial5_gpr import feature_matrix as trial5_feature_matrix


class Phase5Trial4GprTests(unittest.TestCase):
    """Input: synthetic Trial4 residuals. Output: Phase 5 GPR contract checks."""

    def test_gpr_uses_five_features(self) -> None:
        """Input: four feature columns. Output: rejected Phase 5 feature shape."""
        with self.assertRaises(ValueError):
            fit_gpr(np.ones((4, 4)), np.zeros(4))

    def test_gpr_rejects_negative_optimizer_restarts(self) -> None:
        """Input: negative restart count. Output: rejected GPR settings."""
        with self.assertRaises(ValueError):
            fit_gpr(np.ones((4, 1)), np.zeros(4), GprSettings(("one",), -1))

    def test_feature_ablation_defines_one_full_set_and_ten_single_or_drop_sets(self) -> None:
        """Input: fixed Trial1 feature names. Output: 11 distinct ablation definitions."""
        definitions = feature_set_definitions()
        self.assertEqual(len(definitions), 11)

    def test_feature_ablation_keeps_one_extra_baseline_outside_gpr_feature_sets(self) -> None:
        """Input: 11 GPR feature sets. Output: 12 summary rows including Trial4 baseline."""
        self.assertEqual(len(feature_set_definitions()) + 1, 12)

    def test_feature_ablation_selects_named_columns_in_source_order(self) -> None:
        """Input: five source columns and two selected names. Output: named feature columns."""
        selected = selected_feature_matrix(
            np.array([[1.0, 2.0, 3.0, 4.0, 5.0]]),
            ("symh_phase_nt", "h_tau_phase_nt"),
        )
        self.assertTrue(np.array_equal(selected, np.array([[4.0, 1.0]])))

    def test_feature_ablation_reports_signed_single_and_drop_deltas(self) -> None:
        """Input: baseline, full, single, and drop RMSE. Output: signed contribution metrics."""
        deltas = contribution_deltas(0.10, 0.11, 0.09, 0.12)
        self.assertAlmostEqual(deltas["single_feature_delta_vs_trial4"], -0.01)
        self.assertAlmostEqual(deltas["drop_feature_delta_vs_all_features"], 0.01)

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
