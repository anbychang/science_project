"""Load prepared Swarm-A states from one readable CSV."""

import csv
from datetime import datetime
from pathlib import Path

import numpy as np


def _row_to_state(row):
    """Input: {CSV column: text, ...}
    Output: {time, frame, position_m, velocity_m_s, space weather}"""
    return {
        "time": datetime.fromisoformat(row["time_utc"].replace("Z", "+00:00")),
        "frame": row["frame"],
        "position_m": np.array(
            [float(row["x_m"]), float(row["y_m"]), float(row["z_m"])]
        ),
        "velocity_m_s": np.array(
            [
                float(row["vx_m_s"]),
                float(row["vy_m_s"]),
                float(row["vz_m_s"]),
            ]
        ),
        "f107_sfu": float(row["f107_sfu"]),
        "f107a_sfu": float(row["f107a_sfu"]),
        "ap_values": [
            float(row["ap_daily"]),
            float(row["ap_now"]),
            float(row["ap_3h"]),
            float(row["ap_6h"]),
            float(row["ap_9h"]),
            float(row["ap_12_to_33h_avg"]),
            float(row["ap_36_to_57h_avg"]),
        ],
        "f107_data_type": row["f107_data_type"],
    }


def load_prepared_states(file_path, start_time=None, end_time=None):
    """Input: {prepared CSV path, start_time=None, end_time=None}
    Output: [state_1, state_2, state_3, ...]"""
    states = []

    with Path(file_path).open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            state = _row_to_state(row)

            if start_time is not None and state["time"] < start_time:
                continue
            if end_time is not None and state["time"] > end_time:
                break

            states.append(state)

    return states
