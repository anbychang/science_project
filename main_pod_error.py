"""Run one Swarm-A orbit prediction and print its position error."""

import argparse
from datetime import datetime, timedelta
from pathlib import Path

from astropy.utils import iers

from satellite_orbit.calc_integrator import propagate
from satellite_orbit.calc_position_error import position_error_m
from satellite_orbit.load_prepared_states import load_prepared_states


RK4_STEP_SECONDS = 10


def find_state(orbit_states, target_time):
    """Input: {orbit_states, target_time}
    Output: one orbit state"""
    for state in orbit_states:
        if state["time"] == target_time:
            return state

    raise ValueError(f"No POD point at UTC time {target_time}.")


def calculate_error(day_utc, start_time_utc, prediction_minutes):
    """Input: {day_utc, start_time_utc, prediction_minutes}
    Output: {initial_state, predicted_state, official_state, error_m}"""
    start_utc = datetime.fromisoformat(f"{day_utc}T{start_time_utc}+00:00")
    target_utc = start_utc + timedelta(minutes=prediction_minutes)

    start_month = start_utc.strftime("%Y-%m")
    target_month = target_utc.strftime("%Y-%m")
    if target_month != start_month:
        raise ValueError("Start and target must be in the same UTC month.")

    prepared_file = Path(f"data/prepared_swarm_a_{start_month}.csv")
    orbit_states = load_prepared_states(
        prepared_file,
        start_time=start_utc,
        end_time=target_utc,
    )

    initial_state = find_state(orbit_states, start_utc)
    official_state = find_state(orbit_states, target_utc)
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
    """Input: command-line text
    Output: {day, start, minutes}"""
    parser = argparse.ArgumentParser(description="Compare an orbit prediction with Swarm-A POD.")
    parser.add_argument("--day", default="2025-01-01", help="UTC day: YYYY-MM-DD")
    parser.add_argument("--start", default="00:00:02", help="UTC start time: HH:MM:SS")
    parser.add_argument("--minutes", type=int, default=10, help="Prediction time in minutes")
    return parser.parse_args()


def main():
    """Input: command-line text
    Output: printed {predicted_position, official_position, error_m}"""
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
