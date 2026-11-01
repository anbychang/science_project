"""Fit independent event R values and one positive gain at a shared tau."""

import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from phases.phase3.code.calc_h_tau import filtered_sme, phase_weighted_mean
from load_phase4_v2_inputs import SME_REFERENCE_NT


def response_at_tau(sme: np.ndarray, phase_events: list[dict],
                    density_by_storm: dict[str, dict], tau_hours: float) -> list[np.ndarray]:
    """Input: [SME nT], [phase event], {density}, tau h. Output: [phase H arrays nT]."""
    filtered = filtered_sme(sme, tau_hours) - SME_REFERENCE_NT
    responses = []
    for event in phase_events:
        support = event["support"]
        valid_times = event["time_us"][support["valid"]]
        if not np.array_equal(valid_times, density_by_storm[event["storm_id"]]["time_us"]):
            raise ValueError(f"Time keys differ for {event['storm_id']}")
        phase_mean = phase_weighted_mean(
            filtered[event["minute_index"]], event["pair_count"], support
        )
        responses.append(phase_mean[support["valid"]])
    return responses


def fit_shared_tau(density_by_storm: dict[str, dict], responses: list[np.ndarray]
                   ) -> tuple[np.ndarray, float, float]:
    """Input: {storm density}, [phase H nT]. Output: [R_k], G 1/nT, equal-event RMSE."""
    events = list(density_by_storm.values())
    if len(events) != len(responses):
        raise ValueError("Density and response event counts differ.")
    gain = 0.0007
    upper_log_r = np.log(np.nextafter(2.0, 0.0))
    for _ in range(100):
        log_r = np.asarray([
            min(float(np.mean(event["log_anomaly"] - gain * response)), upper_log_r)
            for event, response in zip(events, responses, strict=True)
        ])
        numerator = sum(float(np.mean(response * (event["log_anomaly"] - offset)))
                        for event, response, offset in zip(events, responses, log_r, strict=True))
        denominator = sum(float(np.mean(response * response)) for response in responses)
        updated_gain = numerator / denominator
        if updated_gain <= 0:
            raise ValueError("Shared gain must be positive.")
        if np.isclose(updated_gain, gain, rtol=1e-12, atol=0):
            gain = updated_gain
            break
        gain = updated_gain
    else:
        raise RuntimeError("Shared tau fit did not converge.")
    losses = [float(np.mean((event["log_anomaly"] - offset - gain * response) ** 2))
              for event, response, offset in zip(events, responses, log_r, strict=True)]
    return np.exp(log_r), gain, float(np.sqrt(np.mean(losses)))
