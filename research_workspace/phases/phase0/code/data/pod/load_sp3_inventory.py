"""Read fixed provenance fields from one Swarm POD SP3 header."""

from datetime import datetime, timedelta
from zipfile import ZipFile

from research_workspace.phases.phase0.code.calculation.pod.calc_time import gps_times_to_utc


def load_sp3_inventory(zip_path):
    """Input: POD ZIP path
    Output: {frame_label, coverage, epoch_count, cadence_s, time_system}"""
    with ZipFile(zip_path) as zip_file:
        sp3_name = next(
            (name for name in zip_file.namelist() if name.lower().endswith(".sp3")),
            None,
        )
        if sp3_name is None:
            raise ValueError("No SP3 file found in the ZIP file.")
        with zip_file.open(sp3_name) as sp3_file:
            header_lines = [sp3_file.readline().decode("ascii") for _ in range(13)]

    first_fields = header_lines[0].split()
    interval_fields = header_lines[1].split()
    time_system_fields = header_lines[12].split()
    if len(first_fields) < 11 or len(interval_fields) < 4 or len(time_system_fields) < 4:
        raise ValueError("SP3 header is incomplete.")

    start_gps = datetime(
        int(first_fields[0][3:]),
        int(first_fields[1]),
        int(first_fields[2]),
        int(first_fields[3]),
        int(first_fields[4]),
        int(float(first_fields[5])),
    )
    epoch_count = int(first_fields[6])
    cadence_s = float(interval_fields[3])
    frame_label = first_fields[-3]
    time_system = time_system_fields[3]
    if epoch_count <= 0 or cadence_s <= 0.0 or not frame_label.startswith("IG"):
        raise ValueError("SP3 header has invalid provenance fields.")

    start_utc = gps_times_to_utc([start_gps])[0]
    end_gps = start_gps + timedelta(seconds=(epoch_count - 1) * cadence_s)
    end_utc = gps_times_to_utc([end_gps])[0]
    return {
        "sp3_frame_label": frame_label,
        "coverage_start": start_utc,
        "coverage_end": end_utc,
        "epoch_count": epoch_count,
        "cadence_s": cadence_s,
        "time_system": time_system,
    }
