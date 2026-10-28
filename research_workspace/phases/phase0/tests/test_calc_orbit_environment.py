import unittest

from research_workspace.phases.phase0.code.calculation.density.calc_orbit_environment import (
    ASCENDING,
    DESCENDING,
    DensityObservation,
    EnvironmentTolerance,
    build_reference_environment_index,
    classify_orbit_observations,
    density_baseline,
    density_baseline_from_index,
    local_solar_time_difference,
)


TOLERANCE = EnvironmentTolerance(
    altitude_m=5_000.0,
    latitude_deg=1.0,
    local_solar_time_h=0.25,
)


def observation(time_us, latitude_deg, **changes):
    """Input: observation time, latitude, optional density fields
    Output: one DensityObservation for a test"""
    defaults = {
        "density_kg_m3": 1.0,
        "altitude_m": 500_000.0,
        "local_solar_time_h": 6.0,
        "orbit_id": None,
        "direction": None,
    }
    defaults.update(changes)
    return DensityObservation(time_us=time_us, latitude_deg=latitude_deg, **defaults)


class OrbitEnvironmentTest(unittest.TestCase):
    def test_assigns_new_orbit_after_ascending_equator_crossing(self):
        classified = classify_orbit_observations(
            [
                observation(10, -10.0),
                observation(20, -1.0),
                observation(30, 1.0),
                observation(40, 10.0),
            ]
        )

        self.assertEqual(classified[2].orbit_id, 1)

    def test_marks_falling_latitude_as_descending(self):
        classified = classify_orbit_observations(
            [observation(10, 10.0), observation(20, 5.0)]
        )

        self.assertEqual(classified[0].direction, DESCENDING)

    def test_does_not_infer_an_orbit_across_a_source_gap(self):
        classified = classify_orbit_observations(
            [
                observation(10, -1.0),
                observation(70_000_011, 1.0),
            ]
        )

        self.assertIsNone(classified[1].orbit_id)
        self.assertIsNone(classified[1].direction)

    def test_resumes_orbit_ids_at_the_next_observed_equator_crossing(self):
        classified = classify_orbit_observations(
            [
                observation(10, -1.0),
                observation(20, 1.0),
                observation(70_000_021, -1.0),
                observation(70_000_031, 1.0),
            ]
        )

        self.assertEqual(classified[3].orbit_id, 2)

    def test_uses_one_median_from_each_matching_reference_orbit(self):
        target = observation(100, 20.0, direction=ASCENDING)
        references = [
            observation(10, 20.0, density_kg_m3=1.0, orbit_id=1, direction=ASCENDING),
            observation(20, 20.0, density_kg_m3=5.0, orbit_id=1, direction=ASCENDING),
            observation(30, 20.0, density_kg_m3=9.0, orbit_id=2, direction=ASCENDING),
            observation(40, 20.0, density_kg_m3=11.0, orbit_id=2, direction=ASCENDING),
        ]

        baseline = density_baseline(target, references, TOLERANCE)

        self.assertEqual(baseline.density_median_kg_m3, 6.5)

    def test_rejects_reference_with_wrong_orbit_direction(self):
        target = observation(100, 20.0, direction=ASCENDING)
        references = [
            observation(10, 20.0, orbit_id=1, direction=DESCENDING)
        ]

        self.assertIsNone(density_baseline(target, references, TOLERANCE))

    def test_rejects_reference_later_than_target(self):
        target = observation(100, 20.0, direction=ASCENDING)
        references = [
            observation(110, 20.0, orbit_id=1, direction=ASCENDING)
        ]

        self.assertIsNone(density_baseline(target, references, TOLERANCE))

    def test_binary_search_index_matches_list_scan_baseline(self):
        target = observation(100, 20.0, direction=ASCENDING)
        references = [
            observation(10, 20.0, density_kg_m3=1.0, orbit_id=1, direction=ASCENDING),
            observation(20, 20.0, density_kg_m3=5.0, orbit_id=1, direction=ASCENDING),
            observation(30, 20.0, density_kg_m3=9.0, orbit_id=2, direction=ASCENDING),
            observation(40, 20.0, density_kg_m3=11.0, orbit_id=2, direction=ASCENDING),
        ]
        reference_index = build_reference_environment_index(references)

        self.assertEqual(
            density_baseline_from_index(target, reference_index, TOLERANCE),
            density_baseline(target, references, TOLERANCE),
        )

    def test_binary_search_index_matches_local_time_across_midnight(self):
        target = observation(100, 20.0, local_solar_time_h=0.1, direction=ASCENDING)
        references = [
            observation(
                10,
                20.0,
                local_solar_time_h=23.9,
                orbit_id=1,
                direction=ASCENDING,
            )
        ]
        reference_index = build_reference_environment_index(references)

        self.assertIsNotNone(
            density_baseline_from_index(target, reference_index, TOLERANCE)
        )

    def test_wraps_local_solar_time_at_midnight(self):
        difference = local_solar_time_difference(23.9, 0.1)

        self.assertAlmostEqual(difference, 0.2)


if __name__ == "__main__":
    unittest.main()
