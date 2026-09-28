"""Write local space-weather CSV data into SQLite."""

import csv
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from satellite_orbit.data.load_space_weather import load_space_weather
from satellite_orbit.data.prep_sqlite_common import file_signature, time_to_us

WEATHER_PREPARATION_VERSION = "2"


def weather_days(weather_file):
    """Input: space-weather CSV path
    Output: (first day, last day) with complete data"""
    first_day = None
    last_day = None

    with Path(weather_file).open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            if row["AP1"]:
                day = datetime.fromisoformat(row["DATE"]).date()
                if first_day is None:
                    first_day = day
                last_day = day

    if first_day is None:
        raise ValueError("No complete space-weather row was found.")
    return first_day, last_day


def weather_row(weather_state):
    """Input: state with weather values
    Output: one space_weather table row"""
    ap = weather_state["ap_values"]
    return (
        time_to_us(weather_state["time"]), weather_state["f107_sfu"],
        weather_state["f107a_sfu"], weather_state["f107a_last81_sfu"],
        ap[0], ap[1], ap[2], ap[3], ap[4],
        ap[5], ap[6], weather_state["f107_data_type"],
    )


def write_space_weather(connection, weather_file):
    """Input: {SQLite connection, raw weather CSV}
    Output: number of new 3-hour rows"""
    weather_file = Path(weather_file)
    signature = file_signature(weather_file)
    old_signature = connection.execute(
        "SELECT value FROM metadata WHERE name = 'weather_signature'"
    ).fetchone()
    old_version = connection.execute(
        "SELECT value FROM metadata WHERE name = 'weather_preparation_version'"
    ).fetchone()
    if (
        old_signature is not None
        and old_signature[0] == signature
        and old_version is not None
        and old_version[0] == WEATHER_PREPARATION_VERSION
    ):
        return 0

    first_day, last_day = weather_days(weather_file)
    current_time = datetime.combine(first_day, time.min, tzinfo=timezone.utc)
    end_time = datetime.combine(last_day, time(21), tzinfo=timezone.utc)
    rows = []

    while current_time <= end_time:
        try:
            state = load_space_weather({"time": current_time}, weather_file)
        except (KeyError, ValueError):
            current_time += timedelta(hours=3)
            continue
        rows.append(weather_row(state))
        current_time += timedelta(hours=3)

    connection.executemany(
        """
        INSERT OR REPLACE INTO space_weather (
            time_us, f107_sfu, f107a_sfu, f107a_last81_sfu,
            ap_daily, ap_now, ap_3h, ap_6h, ap_9h,
            ap_12_to_33h_avg, ap_36_to_57h_avg, f107_data_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    connection.execute(
        "INSERT OR REPLACE INTO metadata VALUES ('weather_signature', ?)",
        (signature,),
    )
    connection.execute(
        "INSERT OR REPLACE INTO metadata VALUES ('weather_preparation_version', ?)",
        (WEATHER_PREPARATION_VERSION,),
    )
    return len(rows)
