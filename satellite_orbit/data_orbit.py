"""Read orbit data."""

import csv
from datetime import datetime
from pathlib import Path


def load_orbit_csv(file_path):
    """Input: orbit CSV
    Output: [{time, position_km, velocity_km_s}, ...]"""
    orbit_points = []

    with Path(file_path).open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            orbit_points.append(
                {
                    "time": datetime.fromisoformat(
                        row["time_utc"].replace("Z", "+00:00")
                    ),
                    "position_km": (
                        float(row["x_km"]),
                        float(row["y_km"]),
                        float(row["z_km"]),
                    ),
                    "velocity_km_s": (
                        float(row["vx_km_s"]),
                        float(row["vy_km_s"]),
                        float(row["vz_km_s"]),
                    ),
                }
            )

    return orbit_points
