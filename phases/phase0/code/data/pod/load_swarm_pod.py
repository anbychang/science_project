"""Load a Swarm-A POD file."""

from datetime import datetime, timedelta
from zipfile import ZipFile

from phases.phase0.code.calculation.pod.calc_time import gps_times_to_utc

KM_TO_M = 1000.0
DM_S_TO_M_S = 0.1


def _read_time(line):
    """Input: SP3 time line
    Output: GPS datetime"""
    fields = line[1:].split()
    second = float(fields[5])
    whole_second = int(second)
    microsecond = round((second - whole_second) * 1_000_000)

    time_gps = datetime(
        int(fields[0]),
        int(fields[1]),
        int(fields[2]),
        int(fields[3]),
        int(fields[4]),
        whole_second,
    )
    return time_gps + timedelta(microseconds=microsecond)


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


def load_swarm_pod(zip_path):
    """Input: Swarm-A POD ZIP
    Output: [{time, frame, position_m, velocity_m_s}, ...]"""
    orbit_states = []

    with ZipFile(zip_path) as zip_file:
        sp3_name = next(
            (name for name in zip_file.namelist() if name.lower().endswith(".sp3")),
            None,
        )
        if sp3_name is None:
            raise ValueError("No SP3 file found in the ZIP file.")

        with zip_file.open(sp3_name) as sp3_file:
            for raw_line in sp3_file:
                line = raw_line.decode("ascii")

                if line.startswith("*"):
                    time_gps = _read_time(line)
                elif line.startswith("P"):
                    position = _read_position(line)
                elif line.startswith("V"):
                    velocity = _read_velocity(line)
                    orbit_states.append(
                        {
                            "time": time_gps,
                            "frame": "ITRF",
                            "position_m": position,
                            "velocity_m_s": velocity,
                        }
                    )

    times_utc = gps_times_to_utc([state["time"] for state in orbit_states])
    for state, time_utc in zip(orbit_states, times_utc):
        state["time"] = time_utc

    return orbit_states
