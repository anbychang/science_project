"""Load a Swarm-A POD file."""

from datetime import datetime
from zipfile import ZipFile


DM_S_TO_KM_S = 0.0001


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
