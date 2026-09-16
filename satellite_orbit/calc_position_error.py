"""Compare a predicted position with an official position."""

import numpy as np


KM_TO_M = 1000.0


def position_error_m(predicted_position_km, official_position_km):
    """Input: {predicted_position_km, official_position_km}
    Output: error_m"""
    predicted = np.asarray(predicted_position_km)
    official = np.asarray(official_position_km)
    difference_km = predicted - official
    return np.linalg.norm(difference_km) * KM_TO_M
