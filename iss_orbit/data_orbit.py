"""Read NASA's ISS orbit files and skip reboost periods."""

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path


UTC = timezone.utc


def load_orbit_csv(file_path):
    """輸入：CSV 軌道資料
    輸出：[{time, position_km, velocity_km_s}, ...]"""
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


def load_iss_oem(file_path):
    """輸入：NASA OEM 檔
    輸出：{orbit_points, reboost_times}"""
    orbit_points = []
    reboost_tigs = []
    year = None

    for raw_line in Path(file_path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if line.startswith("START_TIME"):
            year = int(line.split("=", 1)[1].strip()[:4])

        if "Reboost" in line:
            reboost_tigs.append(
                next(field for field in line.split() if field.count(":") == 3)
            )

        fields = line.split()
        is_orbit_row = len(fields) == 7 and fields[0].startswith("20")
        if not is_orbit_row:
            continue

        orbit_points.append(
            {
                "time": datetime.fromisoformat(fields[0]).replace(tzinfo=UTC),
                "position_km": tuple(float(value) for value in fields[1:4]),
                "velocity_km_s": tuple(float(value) for value in fields[4:7]),
            }
        )

    reboost_times = []
    for tig in reboost_tigs:
        day, hour, minute, second = tig.split(":")
        reboost_times.append(
            datetime.strptime(
                f"{year} {day} {hour}:{minute}:{second}",
                "%Y %j %H:%M:%S.%f",
            ).replace(tzinfo=UTC)
        )

    return orbit_points, reboost_times


def remove_reboost_periods(orbit_points, reboost_times, padding_minutes):
    """輸入：{orbit_points, reboost_times, padding_minutes}
    輸出：[{time, position_km, velocity_km_s}, ...]"""
    padding = timedelta(minutes=padding_minutes)
    clean_points = []

    for point in orbit_points:
        is_near_reboost = False

        for reboost_time in reboost_times:
            time_difference = abs(point["time"] - reboost_time)
            if time_difference <= padding:
                is_near_reboost = True
                break

        if not is_near_reboost:
            clean_points.append(point)

    return clean_points
