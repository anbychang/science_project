"""Load a Swarm-A POD file."""

from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

from .down_swarm_pod import download_swarm_a_pod


DM_S_TO_KM_S = 0.0001
DEFAULT_POD_FOLDER = "data/swarm_a_pod"


def load_swarm_pod(zip_path):
    """Input: Swarm-A POD ZIP
    Output: [{time_gps, position_itrf_km, velocity_itrf_km_s}, ...]"""
    orbit_points = []

    with ZipFile(zip_path) as zip_file:
        sp3_name = None

        for file_name in zip_file.namelist():
            if file_name.lower().endswith(".sp3"):
                sp3_name = file_name
                break

        if sp3_name is None:
            raise ValueError("No SP3 file found in the ZIP file.")

        time_gps = None
        position_itrf_km = None

        with zip_file.open(sp3_name) as sp3_file:
            for raw_line in sp3_file:
                line = raw_line.decode("ascii").strip()

                if line.startswith("*"):
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
                        microsecond,
                    )

                elif line.startswith("P"):
                    position_itrf_km = (
                        float(line[4:18]),
                        float(line[18:32]),
                        float(line[32:46]),
                    )

                elif line.startswith("V"):
                    velocity_itrf_km_s = (
                        float(line[4:18]) * DM_S_TO_KM_S,
                        float(line[18:32]) * DM_S_TO_KM_S,
                        float(line[32:46]) * DM_S_TO_KM_S,
                    )

                    orbit_points.append(
                        {
                            "time_gps": time_gps,
                            "position_itrf_km": position_itrf_km,
                            "velocity_itrf_km_s": velocity_itrf_km_s,
                        }
                    )

    return orbit_points


def find_swarm_pod_zip(day_gps, data_folder=DEFAULT_POD_FOLDER):
    """Input: {day_gps: "YYYY-MM-DD", data_folder}
    Output: ZIP path for that GPS day"""
    day_text = day_gps.replace("-", "")
    year_folder = Path(data_folder) / day_text[:4]
    zip_paths = []

    for zip_path in year_folder.glob("*.ZIP"):
        time_range = zip_path.name.split("__")[1].split("_")
        file_day = time_range[1][:8]

        if file_day == day_text:
            zip_paths.append(zip_path)

    if zip_paths:
        zip_paths.sort()
        return zip_paths[-1]

    return download_swarm_a_pod(day_gps, year_folder)


def load_swarm_pod_period(
    day_gps,
    start_time_gps,
    end_time_gps,
    data_folder=DEFAULT_POD_FOLDER,
):
    """Input: {day_gps, start_time_gps, end_time_gps}
    Output: [{time_gps, x, y, z, vx, vy, vz}, ...]"""
    start = datetime.fromisoformat(f"{day_gps}T{start_time_gps}")
    end = datetime.fromisoformat(f"{day_gps}T{end_time_gps}")

    if end <= start:
        raise ValueError("End time must be later than start time.")

    zip_path = find_swarm_pod_zip(day_gps, data_folder)
    orbit_points = load_swarm_pod(zip_path)
    selected_points = []

    for point in orbit_points:
        time_gps = point["time_gps"]
        if time_gps < start or time_gps >= end:
            continue

        x, y, z = point["position_itrf_km"]
        vx, vy, vz = point["velocity_itrf_km_s"]

        selected_points.append(
            {
                "time_gps": time_gps,
                "x_itrf_km": x,
                "y_itrf_km": y,
                "z_itrf_km": z,
                "vx_itrf_km_s": vx,
                "vy_itrf_km_s": vy,
                "vz_itrf_km_s": vz,
            }
        )

    return selected_points
