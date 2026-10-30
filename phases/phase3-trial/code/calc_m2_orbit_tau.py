"""Compute a continuous SME response with a time constant set once per orbit."""

import math

import numpy as np
from scipy.signal import lfilter


SME_QUIET_NT = 65.0
SME_RESPONSE_SCALE_NT = 435.0
MINUTE_PER_HOUR = 60.0


def tau_from_previous_sme(previous_sme_nt: np.ndarray,
                          tau_quiet_hours: float,
                          tau_active_hours: float) -> np.ndarray:
    """Input: [previous-orbit SME nT], quiet/active tau h. Output: [tau h]."""
    if min(tau_quiet_hours, tau_active_hours) < 0 or not np.isfinite(previous_sme_nt).all():
        raise ValueError("Time constants must be nonnegative and SME finite")
    excess = np.maximum(previous_sme_nt - SME_QUIET_NT, 0)
    activity = excess / (excess + SME_RESPONSE_SCALE_NT)
    return tau_quiet_hours + (tau_active_hours - tau_quiet_hours) * activity


def event_orbit_response(sme_excess_nt: np.ndarray, orbit_edges: np.ndarray,
                         tau_by_orbit_hours: np.ndarray,
                         initial_response_nt: float) -> np.ndarray:
    """Input: event SME, orbit edges/tau, prior H nT. Output: event H nT."""
    if (len(orbit_edges) != len(tau_by_orbit_hours) + 1
            or orbit_edges[0] != 0 or orbit_edges[-1] != len(sme_excess_nt)
            or np.any(np.diff(orbit_edges) < 0)
            or not np.isfinite(sme_excess_nt).all()
            or not np.isfinite(tau_by_orbit_hours).all()
            or np.any(tau_by_orbit_hours < 0)
            or not math.isfinite(initial_response_nt)):
        raise ValueError("SME and segment schedule must be finite and ordered")
    response = np.empty_like(sme_excess_nt, dtype=float)
    previous = initial_response_nt
    for segment in range(len(orbit_edges) - 1):
        start, stop = int(orbit_edges[segment]), int(orbit_edges[segment + 1])
        if start == stop:
            continue
        segment_tau = float(tau_by_orbit_hours[segment])
        if segment_tau == 0:
            response[start:stop] = sme_excess_nt[start:stop]
        else:
            alpha = math.exp(-1 / (MINUTE_PER_HOUR * segment_tau))
            response[start:stop], _ = lfilter(
                [1 - alpha], [1, -alpha], sme_excess_nt[start:stop],
                zi=[alpha * previous],
            )
        previous = float(response[stop - 1])
    return response
