"""Make one readable CSV of prepared Swarm-A states."""

import argparse
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

from satellite_orbit.calc_coordinates import itrf_states_to_gcrf
from satellite_orbit.load_space_weather import load_space_weather
from satellite_orbit.load_swarm_pod import load_swarm_pod_period


FIELD_NAMES = [
    "time_utc",
    "frame",
    "x_m",
    "y_m",
    "z_m",
    "vx_m_s",
    "vy_m_s",
    "vz_m_s",
    "f107_sfu",
    "f107a_sfu",
    "ap_daily",
    "ap_now",
    "ap_3h",
    "ap_6h",
    "ap_9h",
    "ap_12_to_33h_avg",
    "ap_36_to_57h_avg",
    "f107_data_type",
]


def _month_bounds(year_month):
    """Input: "YYYY-MM"
    Output: {month_start_utc, next_month_start_utc}"""
    year, month = [int(value) for value in year_month.split("-")]
    month_start = datetime(year, month, 1, tzinfo=timezone.utc)

    if month == 12:
        next_month_start = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        next_month_start = datetime(year, month + 1, 1, tzinfo=timezone.utc)

    return month_start, next_month_start


def _state_to_row(state):
    """Input: prepared state
    Output: {CSV column: value, ...}"""
    x_m, y_m, z_m = state["position_m"]
    vx_m_s, vy_m_s, vz_m_s = state["velocity_m_s"]
    ap = state["ap_values"]

    return {
        "time_utc": state["time"].isoformat().replace("+00:00", "Z"),
        "frame": state["frame"],
        "x_m": x_m,
        "y_m": y_m,
        "z_m": z_m,
        "vx_m_s": vx_m_s,
        "vy_m_s": vy_m_s,
        "vz_m_s": vz_m_s,
        "f107_sfu": state["f107_sfu"],
        "f107a_sfu": state["f107a_sfu"],
        "ap_daily": ap[0],
        "ap_now": ap[1],
        "ap_3h": ap[2],
        "ap_6h": ap[3],
        "ap_9h": ap[4],
        "ap_12_to_33h_avg": ap[5],
        "ap_36_to_57h_avg": ap[6],
        "f107_data_type": state["f107_data_type"],
    }


def prepare_month_states(year_month, output_path=None):
    """Input: {year_month: "YYYY-MM", output_path}
    Output: {file_path, state_count}"""
    month_start, next_month_start = _month_bounds(year_month)

    if output_path is None:
        output_path = Path(f"data/prepared_swarm_a_{year_month}.csv")
    else:
        output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    state_count = 0
    gps_day = month_start.date()
    last_gps_day = next_month_start.date()

    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELD_NAMES)
        writer.writeheader()

        while gps_day <= last_gps_day:
            day_text = gps_day.isoformat()
            states_itrf = load_swarm_pod_period(
                day_text,
                "00:00:00",
                "23:59:59.999999",
            )
            states_gcrf = itrf_states_to_gcrf(states_itrf)

            for state in states_gcrf:
                if state["time"] < month_start:
                    continue
                if state["time"] >= next_month_start:
                    continue

                prepared_state = load_space_weather(state)
                writer.writerow(_state_to_row(prepared_state))
                state_count += 1

            print(f"Prepared GPS day: {day_text}", flush=True)
            gps_day += timedelta(days=1)

    return {
        "file_path": output_path,
        "state_count": state_count,
    }


def read_arguments():
    """Input: command-line text
    Output: {month}"""
    parser = argparse.ArgumentParser(description="Prepare one month of Swarm-A states.")
    parser.add_argument("month", help="UTC month: YYYY-MM")
    return parser.parse_args()


def main():
    """Input: python -m satellite_orbit.prep_month_states YYYY-MM
    Output: prepared CSV summary"""
    arguments = read_arguments()
    result = prepare_month_states(arguments.month)
    print(f"Saved: {result['file_path']}")
    print(f"States: {result['state_count']}")


if __name__ == "__main__":
    main()
