"""Check M1-only shape features and orbit-gap handling."""

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from calc_m1_shape_features import build_triplets, shape_features


class M1ShapeFeatureTests(unittest.TestCase):
    """Input: synthetic orbit anchors. Output: centered-shape contract checks."""

    def test_centered_curvature_uses_next_m1_without_next_l2(self) -> None:
        """Input: three model densities. Output: center level, past slope, centered curvature."""
        previous = {"rho_m1_kg_m3": math.exp(1)}
        current = {"rho_m1_kg_m3": math.exp(3)}
        following = {"rho_m1_kg_m3": math.exp(4)}
        level, slope, curvature = shape_features(previous, current, following)
        self.assertAlmostEqual(level, 3)
        self.assertAlmostEqual(slope, 2)
        self.assertAlmostEqual(curvature, -1)

    def test_gap_does_not_create_a_triplet(self) -> None:
        """Input: grids 0, 2, 3. Output: no feature row across the missing orbit."""
        rows = [
            {"storm_id": "S1", "grid_index": grid, "time_us": grid,
             "rho_m1_kg_m3": 1.0, "rho_l2_kg_m3": 1.0}
            for grid in (0, 2, 3)
        ]
        self.assertEqual(build_triplets(rows), [])


if __name__ == "__main__":
    unittest.main()
