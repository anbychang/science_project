"""Build one local SQLite file for Swarm-A orbit work."""

import csv
import sqlite3
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from satellite_orbit.load_space_weather import load_space_weather
from satellite_orbit.load_swarm_pod import load_swarm_pod

DEFAULT_DATABASE = Path("data/swarm_a_data.sqlite")
DEFAULT_POD_FOLDER = Path("data/swarm_a_pod")
DEFAULT_WEATHER_FILE = Path("data/space_weather/SW-All.csv")


def _time_to_us(time_utc):
    """Input: UTC datetime
    Output: Unix time in microseconds"""
    time_utc = time_utc.astimezone(timezone.utc)
    return round(time_utc.timestamp() * 1_000_000)


def _weather_time(time_utc):
    """Input: UTC datetime
    Output: start of its 3-hour weather block"""
    start_hour = time_utc.hour - time_utc.hour % 3
    return time_utc.replace(
        hour=start_hour,
        minute=0,
        second=0,
        microsecond=0,
    )


def _file_signature(file_path):
    """Input: file path
    Output: "size:last_write_time"""
    file_info = Path(file_path).stat()
    return f"{file_info.st_size}:{file_info.st_mtime_ns}"


def _create_tables(connection):
    """Input: SQLite connection
    Output: database tables"""
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS space_weather (
            time_us INTEGER PRIMARY KEY,
            f107_sfu REAL NOT NULL,
            f107a_sfu REAL NOT NULL,
            ap_daily REAL NOT NULL,
            ap_now REAL NOT NULL,
            ap_3h REAL NOT NULL,
            ap_6h REAL NOT NULL,
            ap_9h REAL NOT NULL,
            ap_12_to_33h_avg REAL NOT NULL,
            ap_36_to_57h_avg REAL NOT NULL,
            f107_data_type TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS swarm_a_states (
            time_us INTEGER PRIMARY KEY,
            x_m REAL NOT NULL,
            y_m REAL NOT NULL,
            z_m REAL NOT NULL,
            vx_m_s REAL NOT NULL,
            vy_m_s REAL NOT NULL,
            vz_m_s REAL NOT NULL,
            weather_time_us INTEGER NOT NULL,
            source_id INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS source_files (
            source_id INTEGER PRIMARY KEY,
            file_name TEXT NOT NULL UNIQUE,
            signature TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS metadata (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )


def _weather_date_bounds(file_path):
    """Input: raw space-weather CSV path
    Output: {first_day, last_day}"""
    first_day = None
    last_day = None

    with Path(file_path).open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            if not row["AP1"]:
                continue

            row_day = datetime.fromisoformat(row["DATE"]).date()
            if first_day is None:
                first_day = row_day
            last_day = row_day

    if first_day is None:
        raise ValueError("No complete space-weather row was found.")

    return first_day, last_day


def _weather_row(weather_state):
    """Input: state + space weather
    Output: [time, F10.7, F10.7A, 7 Ap values, data type]"""
    ap = weather_state["ap_values"]
    return (
        _time_to_us(weather_state["time"]),
        weather_state["f107_sfu"],
        weather_state["f107a_sfu"],
        ap[0],
        ap[1],
        ap[2],
        ap[3],
        ap[4],
        ap[5],
        ap[6],
        weather_state["f107_data_type"],
    )


def _prepare_space_weather(connection, weather_file):
    """Input: {SQLite connection, raw weather CSV}
    Output: number of inserted 3-hour rows"""
    weather_file = Path(weather_file).resolve()
    signature = _file_signature(weather_file)
    old_row = connection.execute(
        "SELECT value FROM metadata WHERE name = 'weather_signature'"
    ).fetchone()

    if old_row is not None and old_row[0] == signature:
        return 0

    first_day, last_day = _weather_date_bounds(weather_file)
    current_time = datetime.combine(first_day, time.min, tzinfo=timezone.utc)
    end_time = datetime.combine(last_day, time(21), tzinfo=timezone.utc)
    rows = []

    while current_time <= end_time:
        try:
            weather_state = load_space_weather(
                {"time": current_time},
                weather_file,
            )
            rows.append(_weather_row(weather_state))
        except (KeyError, ValueError):
            pass

        current_time += timedelta(hours=3)

    connection.executemany(
        """
        INSERT OR REPLACE INTO space_weather VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        rows,
    )
    connection.execute(
        "INSERT OR REPLACE INTO metadata VALUES ('weather_signature', ?)",
        (signature,),
    )
    connection.commit()
    return len(rows)


def _orbit_row(state, source_id):
    """Input: {ITRF state, source_id}
    Output: [time, x, y, z, vx, vy, vz, weather_time, source_id]"""
    position = state["position_m"]
    velocity = state["velocity_m_s"]
    weather_time = _weather_time(state["time"])
    return (
        _time_to_us(state["time"]),
        float(position[0]),
        float(position[1]),
        float(position[2]),
        float(velocity[0]),
        float(velocity[1]),
        float(velocity[2]),
        _time_to_us(weather_time),
        source_id,
    )


def _prepare_pod_file(connection, zip_path, weather_times):
    """Input: {SQLite connection, POD ZIP, known weather times}
    Output: number of inserted orbit states"""
    zip_path = Path(zip_path).resolve()
    file_name = zip_path.name
    signature = _file_signature(zip_path)
    old_row = connection.execute(
        "SELECT source_id, signature FROM source_files WHERE file_name = ?",
        (file_name,),
    ).fetchone()

    if old_row is not None and old_row[1] == signature:
        return 0

    if old_row is None:
        cursor = connection.execute(
            "INSERT INTO source_files (file_name, signature) VALUES (?, ?)",
            (file_name, signature),
        )
        source_id = cursor.lastrowid
    else:
        source_id = old_row[0]
        connection.execute(
            "DELETE FROM swarm_a_states WHERE source_id = ?",
            (source_id,),
        )
        connection.execute(
            "UPDATE source_files SET signature = ? WHERE source_id = ?",
            (signature, source_id),
        )

    rows = []
    states = load_swarm_pod(zip_path)
    for state in states:
        weather_time_us = _time_to_us(_weather_time(state["time"]))
        if weather_time_us not in weather_times:
            continue
        rows.append(_orbit_row(state, source_id))

    connection.executemany(
        """
        INSERT OR REPLACE INTO swarm_a_states VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        rows,
    )
    return len(rows)


def prepare_database(
    database_path=DEFAULT_DATABASE,
    pod_folder=DEFAULT_POD_FOLDER,
    weather_file=DEFAULT_WEATHER_FILE,
):
    """Input: {database_path, pod_folder, weather_file}
    Output: {database_path, weather_rows, pod_files, state_rows, missing_files}"""
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA journal_mode = OFF")
        connection.execute("PRAGMA synchronous = OFF")
        connection.execute("PRAGMA locking_mode = EXCLUSIVE")
        connection.execute("PRAGMA cache_size = -262144")
        connection.execute("PRAGMA temp_store = MEMORY")
        _create_tables(connection)
        weather_rows = _prepare_space_weather(connection, weather_file)
        weather_times = set()
        for row in connection.execute("SELECT time_us FROM space_weather"):
            weather_times.add(row[0])

        zip_paths = sorted(Path(pod_folder).rglob("*.ZIP"))
        changed_file_count = 0
        inserted_state_count = 0
        missing_file_count = 0

        for file_number, zip_path in enumerate(zip_paths, start=1):
            try:
                inserted_rows = _prepare_pod_file(
                    connection,
                    zip_path,
                    weather_times,
                )
            except FileNotFoundError:
                missing_file_count += 1
                inserted_rows = 0

            if inserted_rows > 0:
                changed_file_count += 1
                inserted_state_count += inserted_rows

            if file_number % 100 == 0 or file_number == len(zip_paths):
                connection.commit()

            if file_number % 100 == 0 or file_number == len(zip_paths):
                print(
                    f"POD files: {file_number}/{len(zip_paths)}",
                    flush=True,
                )

    return {
        "database_path": database_path,
        "weather_rows": weather_rows,
        "pod_files": changed_file_count,
        "state_rows": inserted_state_count,
        "missing_files": missing_file_count,
    }


def main():
    """Input: python -m satellite_orbit.prep_states
    Output: database update summary"""
    result = prepare_database()
    print(f"Database: {result['database_path']}")
    print(f"Weather rows added: {result['weather_rows']}")
    print(f"POD files changed: {result['pod_files']}")
    print(f"Orbit states added: {result['state_rows']}")
    print(f"Files moved during work: {result['missing_files']}")


if __name__ == "__main__":
    main()
