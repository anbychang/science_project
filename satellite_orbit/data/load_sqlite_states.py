"""Load prepared Swarm-A states from one SQLite file."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DATABASE = Path("data/swarm_a_data.sqlite")


def _time_to_us(time_utc):
    """Input: UTC datetime
    Output: Unix time in microseconds"""
    time_utc = time_utc.astimezone(timezone.utc)
    return round(time_utc.timestamp() * 1_000_000)


def _us_to_time(time_us):
    """Input: Unix time in microseconds
    Output: UTC datetime"""
    return datetime.fromtimestamp(time_us / 1_000_000, tz=timezone.utc)


def _row_to_state(row):
    """Input: one database row
    Output: ITRF state with space weather"""
    return {
        "time": _us_to_time(row["time_us"]),
        "frame": "ITRF",
        "position_m": (row["x_m"], row["y_m"], row["z_m"]),
        "velocity_m_s": (row["vx_m_s"], row["vy_m_s"], row["vz_m_s"]),
        "f107_sfu": row["f107_sfu"],
        "f107a_sfu": row["f107a_sfu"],
        "ap_values": [
            row["ap_daily"],
            row["ap_now"],
            row["ap_3h"],
            row["ap_6h"],
            row["ap_9h"],
            row["ap_12_to_33h_avg"],
            row["ap_36_to_57h_avg"],
        ],
        "f107_data_type": row["f107_data_type"],
    }


def load_sqlite_states(
    start_time,
    end_time,
    database_path=DEFAULT_DATABASE,
):
    """Input: {start_time, end_time, database_path}
    Output: [ITRF state_1, ITRF state_2, ...]"""
    query = """
        SELECT
            orbit.time_us,
            orbit.x_m,
            orbit.y_m,
            orbit.z_m,
            orbit.vx_m_s,
            orbit.vy_m_s,
            orbit.vz_m_s,
            weather.f107_sfu,
            weather.f107a_sfu,
            weather.ap_daily,
            weather.ap_now,
            weather.ap_3h,
            weather.ap_6h,
            weather.ap_9h,
            weather.ap_12_to_33h_avg,
            weather.ap_36_to_57h_avg,
            weather.f107_data_type
        FROM swarm_a_states AS orbit
        JOIN space_weather AS weather
            ON weather.time_us = orbit.weather_time_us
        WHERE orbit.time_us >= ? AND orbit.time_us <= ?
        ORDER BY orbit.time_us
    """

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            query,
            (_time_to_us(start_time), _time_to_us(end_time)),
        )
        states_itrf = []
        for row in rows:
            states_itrf.append(_row_to_state(row))

    return states_itrf
