"""Score trial density multipliers against paired log-density observations."""

import math


def score_r_grid(log_density_ratios: list[float]) -> list[tuple[float, float]]:
    """Input: [ln(L2/M0), ...]. Output: [(trial_R, RMSE_log_density), ...]."""
    if not log_density_ratios:
        raise ValueError("At least one paired density is required")
    if not all(math.isfinite(value) for value in log_density_ratios):
        raise ValueError("Log-density ratios must be finite")

    count = len(log_density_ratios)
    return [
        (
            hundredths / 100,
            math.sqrt(sum(
                (value - math.log(hundredths / 100)) ** 2
                for value in log_density_ratios
            ) / count),
        )
        for hundredths in range(40, 161)
    ]


def choose_trial(scores: list[tuple[float, float]]) -> tuple[float, float]:
    """Input: [(trial_R, RMSE), ...]. Output: lowest-RMSE grid pair."""
    if not scores:
        raise ValueError("At least one trial score is required")
    return min(scores, key=lambda score: score[1])
