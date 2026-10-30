"""Score common delay and response-time candidates on fixed M1 pairs."""

import math

import numpy as np

from phases.phase3.code.calc_h_tau import filtered_sme, phase_weighted_mean


SME_REFERENCE_NT = 65.0
DELTA_MINUTES = tuple(range(0, 361, 15))
M1_TAU_HOURS = 4.65
FINE_TAU_HOURS = tuple(index / 20 for index in range(201))
JOINT_TAU_HOURS = tuple(index / 4 for index in range(49)) + tuple(range(13, 25))
SPLIT_SEED = 20261029


def balanced_splits(event_count: int) -> list[tuple[int, np.ndarray, np.ndarray]]:
    """Input: event count. Output: 100 balanced (fold, train IDs, test IDs)."""
    if event_count != 25:
        raise ValueError("Balanced split design requires 25 events")
    generator = np.random.default_rng(SPLIT_SEED)
    splits = []
    for round_index in range(20):
        order = generator.permutation(event_count)
        for group in range(5):
            test = np.sort(order[5 * group:5 * (group + 1)])
            train = np.setdiff1d(np.arange(event_count), test)
            splits.append((5 * round_index + group, train, test))
    return splits


def response_statistics(sme_nt: np.ndarray, events: list[dict],
                        candidates: list[tuple[float, int]]) -> tuple[np.ndarray, np.ndarray]:
    """Input: [SME], [event arrays], [(tau h, delay min)]. Output: cross and H2 arrays."""
    cross = np.empty((len(candidates), len(events)), dtype=float)
    response_squared = np.empty_like(cross)
    filtered = None
    previous_tau = None
    excess = sme_nt - SME_REFERENCE_NT
    for candidate_index, (tau_hours, delay_minutes) in enumerate(candidates):
        if tau_hours != previous_tau:
            filtered = filtered_sme(excess, tau_hours)
            previous_tau = tau_hours
        for event_index, event in enumerate(events):
            raw = filtered[event["minute_index"] - delay_minutes]
            phase = phase_weighted_mean(raw, event["pairs"], event["support"])
            valid_phase = phase[event["support"]["valid"]]
            cross[candidate_index, event_index] = float(valid_phase @ event["anomaly"])
            response_squared[candidate_index, event_index] = float(valid_phase @ valid_phase)
    return cross, response_squared


def fit_gain(cross: np.ndarray, response_squared: np.ndarray,
             anomaly_squared: float) -> tuple[np.ndarray, np.ndarray]:
    """Input: candidate cross/H2 and z2. Output: [positive gain], [training SSE]."""
    gain = np.divide(cross, response_squared, out=np.full_like(cross, np.nan),
                     where=response_squared > 0)
    error = anomaly_squared - gain * cross
    error[(gain <= 0) | ~np.isfinite(gain)] = np.inf
    return gain, error


def fixed_gain_error(statistics: tuple[np.ndarray, np.ndarray],
                     anomaly_squared: float, gain: float) -> np.ndarray:
    """Input: (cross,H2), z2, fixed gain. Output: [candidate SSE]."""
    cross, response_squared = statistics
    return np.maximum(anomaly_squared - 2 * gain * cross
                      + gain * gain * response_squared, 0.0)


def heldout_rmse(event: dict, statistics: tuple[float, float], gain: float) -> float:
    """Input: event z2/count, (cross,H2), gain. Output: log-density RMSE."""
    cross, response_squared = statistics
    error = fixed_gain_error((np.array(cross), np.array(response_squared)),
                             event["anomaly_squared"], gain)
    return math.sqrt(float(error) / event["count"])


def event_mean_rmse(scores: list[dict], model_name: str,
                    event_count: int) -> np.ndarray:
    """Input: [fold/event scores], model, event count. Output: [mean RMSE/event]."""
    grouped = [[] for _ in range(event_count)]
    for row in scores:
        if model_name in row:
            grouped[row["event_index"]].append(row[model_name])
    if any(len(values) != 20 for values in grouped):
        raise ValueError("Every event must have 20 held-out scores")
    return np.array([float(np.mean(values)) for values in grouped])
