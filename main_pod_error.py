"""Run one Swarm-A orbit prediction and print its position error."""

import argparse
from datetime import datetime, timedelta

import numpy as np
from astropy.utils import iers

from satellite_orbit.calc_coordinates import itrf_to_gcrf
from satellite_orbit.calc_integrator import propagate
from satellite_orbit.calc_position_error import position_error_m
from satellite_orbit.calc_time import gps_time_to_utc
from satellite_orbit.load_swarm_pod import load_swarm_pod_period


RK4_STEP_SECONDS = 10


def find_point(orbit_points, target_time):
    """Input: {orbit_points, target_time}
    Output: one orbit point"""
    for point in orbit_points:
        if point["time"] == target_time:
            return point

    raise ValueError(f"No POD point at UTC time {target_time}.")


def point_to_gcrf(point):
    """Input: one ITRF POD point
    Output: {time, x_gcrf_km, ..., vz_gcrf_km_s}"""
    position_itrf_km = np.array(
        [point["x_itrf_km"], point["y_itrf_km"], point["z_itrf_km"]]
    )
    velocity_itrf_km_s = np.array(
        [point["vx_itrf_km_s"], point["vy_itrf_km_s"], point["vz_itrf_km_s"]]
    )
    time_utc = point["time"]
    state_gcrf = itrf_to_gcrf(time_utc, position_itrf_km, velocity_itrf_km_s)
    position_gcrf_km = state_gcrf["position_gcrf_km"]
    velocity_gcrf_km_s = state_gcrf["velocity_gcrf_km_s"]

    return {
        "time": time_utc,
        "x_gcrf_km": position_gcrf_km[0],
        "y_gcrf_km": position_gcrf_km[1],
        "z_gcrf_km": position_gcrf_km[2],
        "vx_gcrf_km_s": velocity_gcrf_km_s[0],
        "vy_gcrf_km_s": velocity_gcrf_km_s[1],
        "vz_gcrf_km_s": velocity_gcrf_km_s[2],
    }


def calculate_error(day_gps, start_time_gps, prediction_minutes):
    """Input: {day_gps, start_time_gps, prediction_minutes}
    Output: {start_time_utc, target_time_utc, error_m}"""
    start_gps = datetime.fromisoformat(f"{day_gps}T{start_time_gps}")
    target_gps = start_gps + timedelta(minutes=prediction_minutes)

    if target_gps.date() != start_gps.date():
        raise ValueError("Start and target must be on the same GPS day.")

    start_utc = gps_time_to_utc(start_gps)
    target_utc = gps_time_to_utc(target_gps)

    orbit_points = load_swarm_pod_period(
        day_gps,
        "00:00:00",
        "23:59:59.999999",
    )
    start_point = find_point(orbit_points, start_utc)
    target_point = find_point(orbit_points, target_utc)

    initial = point_to_gcrf(start_point)
    official = point_to_gcrf(target_point)

    initial_state = np.array(
        [
            initial["x_gcrf_km"],
            initial["y_gcrf_km"],
            initial["z_gcrf_km"],
            initial["vx_gcrf_km_s"],
            initial["vy_gcrf_km_s"],
            initial["vz_gcrf_km_s"],
        ]
    )
    duration_seconds = prediction_minutes * 60
    n_steps = duration_seconds // RK4_STEP_SECONDS

    predicted_points = propagate(
        initial_state,
        RK4_STEP_SECONDS,
        n_steps,
        initial["time"],
    )
    predicted_point = predicted_points[-1]
    predicted_position_gcrf_km = np.array(
        [
            predicted_point["x_gcrf_km"],
            predicted_point["y_gcrf_km"],
            predicted_point["z_gcrf_km"],
        ]
    )
    official_position_gcrf_km = np.array(
        [
            official["x_gcrf_km"],
            official["y_gcrf_km"],
            official["z_gcrf_km"],
        ]
    )
    error_m = position_error_m(
        predicted_position_gcrf_km,
        official_position_gcrf_km,
    )

    return {
        "start_time_utc": predicted_points[0]["time"],
        "target_time_utc": predicted_point["time"],
        "predicted_position_gcrf_km": predicted_position_gcrf_km,
        "official_position_gcrf_km": official_position_gcrf_km,
        "error_m": error_m,
    }


def read_arguments():
    parser = argparse.ArgumentParser(description="Compare an orbit prediction with Swarm-A POD.")
    parser.add_argument("--day", default="2025-01-01", help="GPS day: YYYY-MM-DD")
    parser.add_argument("--start", default="00:00:00", help="GPS start time: HH:MM:SS")
    parser.add_argument("--minutes", type=int, default=10, help="Prediction time in minutes")
    return parser.parse_args()


def main():
    iers.conf.auto_download = False
    arguments = read_arguments()
    result = calculate_error(arguments.day, arguments.start, arguments.minutes)

    print("Model: two-body gravity + J2 + RK4")
    print(f"Start UTC:  {result['start_time_utc']}")
    print(f"Target UTC: {result['target_time_utc']}")
    print(f"Predicted GCRF km: {result['predicted_position_gcrf_km']}")
    print(f"Official GCRF km:  {result['official_position_gcrf_km']}")
    print(f"Position error: {result['error_m']:.3f} m")


if __name__ == "__main__":
    main()
