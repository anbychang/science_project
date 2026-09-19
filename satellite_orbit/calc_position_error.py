"""Compare a predicted position with an official position."""

import numpy as np


def position_error_m(predicted_state, official_state):
    """Input: {predicted_state, official_state}
    Output: error_m"""
    if predicted_state["frame"] != official_state["frame"]:
        raise ValueError("Both states must use the same frame.")

    predicted = np.asarray(predicted_state["position_m"])
    official = np.asarray(official_state["position_m"])
    difference_m = predicted - official
    return np.linalg.norm(difference_m)
