"""Check four-input GPR uses current D-model and completed L2 only."""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path("phases/phase5-trial8/code").resolve()))
from calc_trial8_four_feature_gpr import feature_vector, predict_event  # noqa: E402


def orbit_rows() -> list[dict]:
    """Input: none. Output: [seven consecutive orbit rows with positive density]."""
    residuals = [0.01, 0.02, 0.03, 0.05, 0.04, 0.06, 0.07]
    return [{"time_us": index * 5_600_000_000,
             "u_rel_rad": index * 2 * math.pi,
             "rho_trial4_phase_kg_m3": (1 + 0.05 * index) * 1e-12,
             "rho_l2_phase_kg_m3": (1 + 0.05 * index) * 1e-12 * math.exp(residual),
             "residual_log_density": residual}
            for index, residual in enumerate(residuals)]


def test_four_features_match_requested_inputs() -> None:
    """Input: two neighboring orbit rows. Output: four named source values in order."""
    previous, current = orbit_rows()[:2]
    features = feature_vector(current, previous)
    assert features == [math.log(current["rho_trial4_phase_kg_m3"]),
                        math.log(previous["rho_trial4_phase_kg_m3"]),
                        math.log(previous["rho_l2_phase_kg_m3"]),
                        previous["residual_log_density"]]


def test_target_l2_is_not_used_for_target_prediction() -> None:
    """Input: target L2 changed after prediction. Output: identical estimate."""
    original = orbit_rows()
    changed = orbit_rows()
    changed[-1]["rho_l2_phase_kg_m3"] *= 5
    changed[-1]["residual_log_density"] += math.log(5)
    first = predict_event(original)[0]
    second = predict_event(changed)[0]
    assert first["gp_log_residual_mean"] == second["gp_log_residual_mean"]
    assert first["training_pair_count"] == 5
    assert first["previous_time_us"] == original[-2]["time_us"]
    assert first["previous_trial4_density_kg_m3"] == original[-2]["rho_trial4_phase_kg_m3"]
    assert first["previous_l2_density_kg_m3"] == original[-2]["rho_l2_phase_kg_m3"]
