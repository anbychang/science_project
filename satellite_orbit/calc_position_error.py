"""Compare a predicted position with an official position."""

import numpy as np


def position_error_m(predicted_position_m, official_position_m):
    """Input: {predicted_position_m, official_position_m}
    Output: error_m"""
    predicted = np.asarray(predicted_position_m)
    official = np.asarray(official_position_m)
    difference_m = predicted - official
    return np.linalg.norm(difference_m)
