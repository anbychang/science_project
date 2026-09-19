"""Load a Swarm-A POD file."""

from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

import numpy as np

from .calc_time import gps_time_to_utc, gps_times_to_utc
KM_TO_M = 1000.0
DM_S_TO_M_S = 0.1
DEFAULT_POD_FOLDER = "data/swarm_a_pod"


def _find_sp3_name(zip_file):
    """Input: POD ZIP
    Output: "path/to/orbit.sp3"""
    for file_name in zip_file.namelist():
        if file_name.lower().endswith(".sp3"):
            return file_name

    raise ValueError("No SP3 file found in the ZIP file.")


def _read_time(line):
    """Input: SP3 time line
    Output: GPS datetime"""
    fields = line[1:].split()
    second = float(fields[5])
    whole_second = int(second)
    microsecond = round((second - whole_second) * 1_000_000)

    return datetime(
        int(fields[0]),
        int(fields[1]),
        int(fields[2]),
        int(fields[3]),
        int(fields[4]),
        whole_second,
        microsecond,
    )


def _read_position(line):
    """Input: SP3 position line
    Output: [x_m, y_m, z_m]"""
    x = float(line[4:18]) * KM_TO_M
    y = float(line[18:32]) * KM_TO_M
    z = float(line[32:46]) * KM_TO_M
    return x, y, z


def _read_velocity(line):
    """Input: SP3 velocity line
    Output: [vx_m_s, vy_m_s, vz_m_s]"""
    vx = float(line[4:18]) * DM_S_TO_M_S
    vy = float(line[18:32]) * DM_S_TO_M_S
    vz = float(line[32:46]) * DM_S_TO_M_S
    return vx, vy, vz


def _make_orbit_state(time_gps, position, velocity):
    """Input: {time_gps, position, velocity}
    Output: {time, frame, position_m, velocity_m_s}"""
    return {
        "time": time_gps,
        "frame": "ITRF",
        "position_m": np.array(position),
        "velocity_m_s": np.array(velocity),
    }


def load_swarm_pod(zip_path):
    """Input: Swarm-A POD ZIP
    Output: [{time, frame, position_m, velocity_m_s}, ...]"""
    orbit_states = []

    with ZipFile(zip_path) as zip_file:
        sp3_name = _find_sp3_name(zip_file)

        with zip_file.open(sp3_name) as sp3_file:
            for raw_line in sp3_file:
                line = raw_line.decode("ascii")

                if line.startswith("*"):
                    time_gps = _read_time(line)
                elif line.startswith("P"):
                    position = _read_position(line)
                elif line.startswith("V"):
                    velocity = _read_velocity(line)
                    state = _make_orbit_state(time_gps, position, velocity)
                    orbit_states.append(state)

    times_gps = []
    for state in orbit_states:
        times_gps.append(state["time"])

    times_utc = gps_times_to_utc(times_gps)
    for index in range(len(orbit_states)):
        orbit_states[index]["time"] = times_utc[index]

    return orbit_states


def _find_swarm_pod_zip(day_gps, data_folder):
    """Input: {day_gps: "YYYY-MM-DD", data_folder}
    Output: ZIP path for that GPS day"""
    day_text = day_gps.replace("-", "")
    year_folder = Path(data_folder) / day_text[:4]
    zip_paths = []

    for zip_path in year_folder.glob("*.ZIP"):
        file_day = zip_path.name.split("_")[-2][:8]

        if file_day == day_text:
            zip_paths.append(zip_path)

    if zip_paths:
        zip_paths.sort()
        return zip_paths[-1]

    raise FileNotFoundError(
        f"No local Swarm-A POD file for {day_gps}. "
        "Run down_swarm_pod.py first."
    )


def load_swarm_pod_period(
    day_gps,
    start_time_gps,
    end_time_gps,
    data_folder=DEFAULT_POD_FOLDER,
):
    """Input: {day_gps, start_time_gps, end_time_gps}
    Output: [{time, frame, position_m, velocity_m_s}, ...]"""
    start_gps = datetime.fromisoformat(f"{day_gps}T{start_time_gps}")
    end_gps = datetime.fromisoformat(f"{day_gps}T{end_time_gps}")

    if end_gps <= start_gps:
        raise ValueError("End time must be later than start time.")

    start_utc = gps_time_to_utc(start_gps)
    end_utc = gps_time_to_utc(end_gps)

    zip_path = _find_swarm_pod_zip(day_gps, data_folder)
    all_states = load_swarm_pod(zip_path)
    selected_states = []

    for state in all_states:
        time_utc = state["time"]
        if time_utc < start_utc or time_utc >= end_utc:
            continue

        selected_states.append(state)

    return selected_states
