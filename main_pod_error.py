"""Run one Swarm-A orbit prediction and print its position error."""

import argparse
from datetime import datetime, timedelta

from astropy.utils import iers

from satellite_orbit.calc_coordinates import itrf_to_gcrf
from satellite_orbit.calc_integrator import propagate
from satellite_orbit.calc_position_error import position_error_m
from satellite_orbit.calc_time import gps_time_to_utc
from satellite_orbit.load_swarm_pod import load_swarm_pod_period


RK4_STEP_SECONDS = 10


def find_state(orbit_states, target_time):
    """Input: {orbit_states, target_time}
    Output: one orbit state"""
    for state in orbit_states:
        if state["time"] == target_time:
            return state

    raise ValueError(f"No POD point at UTC time {target_time}.")


def calculate_error(day_gps, start_time_gps, prediction_minutes):
    """Input: {day_gps, start_time_gps, prediction_minutes}
    Output: {initial_state, predicted_state, official_state, error_m}"""
    start_gps = datetime.fromisoformat(f"{day_gps}T{start_time_gps}")
    target_gps = start_gps + timedelta(minutes=prediction_minutes)

    if target_gps.date() != start_gps.date():
        raise ValueError("Start and target must be on the same GPS day.")

    start_utc = gps_time_to_utc(start_gps)
    target_utc = gps_time_to_utc(target_gps)

    orbit_states = load_swarm_pod_period(
        day_gps,
        "00:00:00",
        "23:59:59.999999",
    )
    start_state = find_state(orbit_states, start_utc)
    target_state = find_state(orbit_states, target_utc)

    initial_state = itrf_to_gcrf(start_state)
    official_state = itrf_to_gcrf(target_state)
    duration_seconds = prediction_minutes * 60
    n_steps = duration_seconds // RK4_STEP_SECONDS

    predicted_states = propagate(
        initial_state,
        RK4_STEP_SECONDS,
        n_steps,
    )
    predicted_state = predicted_states[-1]
    error_m = position_error_m(predicted_state, official_state)

    return {
        "initial_state": initial_state,
        "predicted_state": predicted_state,
        "official_state": official_state,
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
    initial_state = result["initial_state"]
    predicted_state = result["predicted_state"]
    official_state = result["official_state"]

    print("Model: two-body gravity + J2 + RK4")
    print(f"Start UTC:  {initial_state['time']}")
    print(f"Target UTC: {predicted_state['time']}")
    print(f"Predicted GCRF m: {predicted_state['position_m']}")
    print(f"Official GCRF m:  {official_state['position_m']}")
    print(f"Position error: {result['error_m']:.3f} m")


if __name__ == "__main__":
    main()
