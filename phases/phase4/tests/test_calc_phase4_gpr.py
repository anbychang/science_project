"""Check fold isolation and physical fallback in the Phase 4 estimator."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np

from phases.phase4.code.calc_phase4_gpr import fit_gpr, fit_physics, make_features
from phases.phase4.code.load_phase4_inputs import nearest_phase_anchors
from phases.phase4.code import prep_gpr_loso


class Phase4EstimatorTests(unittest.TestCase):
    """Input: synthetic anchors. Output: checks for Phase 4 model contracts."""

    def test_physical_fit_uses_only_supplied_training_rows(self) -> None:
        """Input: two candidate responses and train anomalies. Output: selected tau."""
        h = np.array([[1.0, 2.0], [2.0, 1.0], [3.0, 2.0]])
        z = 0.2 * h[:, 0]
        fit = fit_physics(z, h)
        self.assertEqual(fit["tau_index"], 0)
        self.assertAlmostEqual(fit["gain_per_nt"], 0.2)

    def test_u_grid_selects_nearest_valid_anchor(self) -> None:
        """Input: radians near two u-grid positions. Output: unique valid indices."""
        phase = np.array([-0.2, -0.03, 0.02, 6.25, 6.30, 6.60])
        valid = np.array([True, True, False, True, True, True])
        self.assertEqual(nearest_phase_anchors(phase, valid).tolist(), [1, 4])

    def test_two_cycle_diagnostic_has_its_own_grid(self) -> None:
        """Input: near 2pi and 4pi phases. Output: only the 4pi diagnostic point."""
        phase = np.array([6.28, 12.53, 12.58])
        valid = np.array([True, True, True])
        self.assertEqual(nearest_phase_anchors(phase, valid, 2).tolist(), [2])

    def test_zero_mean_gp_returns_to_physical_baseline(self) -> None:
        """Input: sparse residual examples and distant feature. Output: near-zero GP mean."""
        h = np.linspace(-1, 1, 8)
        fixed = np.column_stack((h ** 2, h ** 3, np.sin(h)))
        features = make_features(h, fixed)
        residual = 0.1 * np.sin(2 * h)
        fitted = fit_gpr(features, residual)
        scaler = fitted["scaler"]
        model = fitted["model"]
        far = np.array([[100.0, 100.0, 100.0, 100.0]])
        mean, std = model.predict(scaler.transform(far), return_std=True)
        self.assertAlmostEqual(mean[0], 0.0, places=6)
        self.assertGreater(std[0], 0.0)

    def test_fold_checkpoint_is_reusable_without_overwrite(self) -> None:
        """Input: completed fold record. Output: identical resume record; no overwrite."""
        result = {"metrics": {"storm_id": "S-test"},
                  "hyperparameters": {"optimizer": "scikit_learn_default_fmin_l_bfgs_b",
                                      "n_restarts_optimizer": 5},
                  "predictions": [[1, 2.0]], "scaler": {"mean": [0.0]}}
        with TemporaryDirectory(dir=Path("phases/phase4/data/analysis")) as directory:
            with patch.object(prep_gpr_loso, "FOLD_DIR", Path(directory)):
                prep_gpr_loso.save_fold(result)
                self.assertEqual(prep_gpr_loso.load_fold("S-test"), result)
                with self.assertRaises(FileExistsError):
                    prep_gpr_loso.save_fold(result)


if __name__ == "__main__":
    unittest.main()
