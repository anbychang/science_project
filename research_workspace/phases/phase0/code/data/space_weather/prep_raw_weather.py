"""Write local space-weather CSV data into SQLite."""

import csv
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from research_workspace.phases.phase0.code.data.database.prep_raw_identifiers import file_signature, time_to_us
from research_workspace.phases.phase0.code.data.space_weather.load_space_weather import load_space_weather

WEATHER_PREPARATION_VERSION = "3"


def weather_days(weather_file):
    """Input: space-weather CSV path
    Output: (first day, last day) with complete data"""
    first_day = None
    last_day = None
    missing_ap1_days = []

    with Path(weather_file).open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            if not row["AP1"]:
                if first_day is not None:
                    missing_ap1_days.append(row["DATE"])
                continue
            if missing_ap1_days:
                raise ValueError(
                    "Space-weather row has missing or invalid Ap data: "
                    f"{missing_ap1_days[0]}"
                )
            try:
                for slot in range(1, 9):
                    float(row[f"AP{slot}"])
            except (KeyError, ValueError) as error:
                raise ValueError(
                    "Space-weather row has missing or invalid Ap data: "
                    f"{row['DATE']}"
                ) from error
            day = datetime.fromisoformat(row["DATE"]).date()
            first_day = first_day or day
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
    metadata = dict(
        connection.execute(
            "SELECT name, value FROM metadata "
            "WHERE name IN ('weather_signature', 'weather_preparation_version')"
        )
    )
    if metadata:
        if metadata == {
            "weather_signature": signature,
            "weather_preparation_version": WEATHER_PREPARATION_VERSION,
        }:
            return 0
        raise ValueError(
            "Space-weather source or preparation version changed. "
            "Rebuild a fresh database instead of replacing raw rows."
        )

    first_day, last_day = weather_days(weather_file)
    current_time = datetime.combine(first_day, time.min, tzinfo=timezone.utc)
    end_time = datetime.combine(last_day, time(21), tzinfo=timezone.utc)
    rows = []

    while current_time <= end_time:
        try:
            rows.append(weather_row(load_space_weather({"time": current_time}, weather_file)))
        except (KeyError, ValueError):
            pass
        current_time += timedelta(hours=3)

    connection.executemany(
        """
        INSERT OR IGNORE INTO space_weather (
            time_us, f107_sfu, f107a_sfu, f107a_last81_sfu,
            ap_daily, ap_now, ap_3h, ap_6h, ap_9h,
            ap_12_to_33h_avg, ap_36_to_57h_avg, f107_data_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    connection.executemany(
        "INSERT OR REPLACE INTO metadata VALUES (?, ?)",
        [
            ("weather_signature", signature),
            ("weather_preparation_version", WEATHER_PREPARATION_VERSION),
        ],
    )
    return len(rows)
