"""Store observed one-minute SYM-H from local WDC Kyoto CSV files."""

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from satellite_orbit.data.database.prep_raw_identifiers import time_to_us
from satellite_orbit.data.geomagnetic.load_geomagnetic import load_geomagnetic_file


ALGORITHM_VERSION = "symh_1min_csv_v1"
MINUTE_US = 60_000_000
PILOT_DATES = (date(2023, 7, 1), date(2026, 6, 30))
DEFAULT_SOURCE_DIR = Path("data/geomagnetic")
DEFAULT_OUTPUT_DB = Path("data/sqlite/2023/swarm_a_phase2_symh_p2_0_1min.sqlite")


def sha256_file(file_path: Path) -> str:
    """Input: local file path. Output: SHA-256 hex digest."""
    digest = hashlib.sha256()
    with file_path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def symh_header(file_path: Path) -> dict:
    """Input: SYM-H CSV path. Output: checked HAPI header mapping."""
    with file_path.open(encoding="utf-8") as source:
        first_line = source.readline()
    if not first_line.startswith("#"):
        raise ValueError(f"{file_path} has no HAPI header.")
    header = json.loads(first_line[1:])
    if header.get("cadence") != "PT1M" or header.get("timeStampLocation") != "center":
        raise ValueError(f"{file_path} must have centered 1-minute timestamps.")
    names = [parameter["name"] for parameter in header["parameters"]]
    if names != ["Time", "symHValue", "versionCode"]:
        raise ValueError(f"{file_path} has unexpected SYM-H columns: {names}.")
    return header


def source_files(source_dir: Path, first_day: date, last_day: date) -> list[Path]:
    """Input: CSV folder and inclusive UTC dates. Output: overlapping CSV paths."""
    selected = []
    for file_path in sorted(source_dir.glob("sym_h_*.csv")):
        parts = file_path.stem.split("_")
        if len(parts) != 4:
            raise ValueError(f"Unexpected SYM-H file name: {file_path.name}.")
        file_first_day = date.fromisoformat(parts[2])
        file_last_day = date.fromisoformat(parts[3])
        if file_first_day <= last_day and file_last_day >= first_day:
            selected.append(file_path)
    if not selected:
        raise ValueError(f"No SYM-H CSV covers {first_day} to {last_day}.")
    return selected


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: new output connection. Output: source, minute, and metadata tables."""
    connection.executescript(
        """
        CREATE TABLE symh_source_files_v1 (
            file_name TEXT PRIMARY KEY,
            sha256 TEXT NOT NULL,
            modification_date TEXT NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE symh_1min_v1 (
            source_time_us INTEGER PRIMARY KEY,
            symh_nt INTEGER NOT NULL,
            symh_version INTEGER NOT NULL,
            source_file_name TEXT NOT NULL REFERENCES symh_source_files_v1(file_name),
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase2_metadata (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )


def import_symh_csv(
    connection: sqlite3.Connection, file_path: Path, source_range: tuple[int, int]
) -> None:
    """Input: output connection, CSV path, inclusive UTC range. Output: stored minute rows."""
    header = symh_header(file_path)
    connection.execute(
        "INSERT INTO symh_source_files_v1 VALUES (?, ?, ?, ?)",
        (file_path.name, sha256_file(file_path), header["modificationDate"], ALGORITHM_VERSION),
    )
    first_us, last_us = source_range
    rows = []
    for observation in load_geomagnetic_file(file_path):
        source_time_us = time_to_us(observation["time"])
        if not first_us <= source_time_us <= last_us:
            continue
        if source_time_us % MINUTE_US:
            raise ValueError(f"{file_path} has a source time off the UTC minute grid.")
        rows.append(
            (
                source_time_us,
                observation["value_nt"],
                observation["version"],
                file_path.name,
                ALGORITHM_VERSION,
            )
        )
    connection.executemany("INSERT OR IGNORE INTO symh_1min_v1 VALUES (?, ?, ?, ?, ?)", rows)


def write_symh_1min(
    source_dir: Path = DEFAULT_SOURCE_DIR,
    date_range: tuple[date, date] = PILOT_DATES,
    output_db: Path = DEFAULT_OUTPUT_DB,
) -> dict[str, int]:
    """Input: raw CSV folder, inclusive UTC dates, new output path. Output: stored counts."""
    source_dir = Path(source_dir).resolve()
    output_db = Path(output_db).resolve()
    first_day, last_day = date_range
    if first_day > last_day:
        raise ValueError("The first UTC day must not be after the last day.")
    if not source_dir.is_dir():
        raise FileNotFoundError(f"SYM-H CSV folder does not exist: {source_dir}")
    if output_db.exists():
        raise FileExistsError(f"Phase 2 output already exists: {output_db}")
    output_db.parent.mkdir(parents=True, exist_ok=True)

    first_us = time_to_us(datetime.combine(first_day, time.min, timezone.utc))
    last_us = time_to_us(
        datetime.combine(last_day + timedelta(days=1), time.min, timezone.utc)
    ) - MINUTE_US
    handle, temporary_name = tempfile.mkstemp(
        prefix=f"{output_db.stem}.", suffix=".building", dir=output_db.parent
    )
    os.close(handle)
    temporary_path = Path(temporary_name)
    connection = sqlite3.connect(temporary_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        create_tables(connection)
        with connection:
            for file_path in source_files(source_dir, first_day, last_day):
                import_symh_csv(connection, file_path, (first_us, last_us))
            connection.executemany(
                "INSERT INTO phase2_metadata VALUES (?, ?)",
                (
                    ("algorithm_version", ALGORITHM_VERSION),
                    ("first_day_utc", first_day.isoformat()),
                    ("last_day_utc", last_day.isoformat()),
                    ("source_time_semantics", "center of observed 1-minute interval"),
                    ("source_selection", "sorted filename; first non-fill minute wins"),
                    ("missing_policy", "observed minutes only; no interpolation or fill"),
                ),
            )
        minute_count = connection.execute("SELECT count(*) FROM symh_1min_v1").fetchone()[0]
        file_count = connection.execute("SELECT count(*) FROM symh_source_files_v1").fetchone()[0]
        if not minute_count:
            raise ValueError("No observed SYM-H minutes in the requested UTC dates.")
    except BaseException:
        connection.close()
        temporary_path.unlink(missing_ok=True)
        raise
    connection.close()
    if output_db.exists():
        temporary_path.unlink()
        raise FileExistsError(f"Phase 2 output appeared during build: {output_db}")
    temporary_path.replace(output_db)
    return {"source_files": file_count, "minute_rows": minute_count}


def main() -> None:
    """Input: optional CSV folder, UTC date range, output DB. Output: printed counts."""
    arguments = sys.argv[1:]
    if len(arguments) not in (0, 4):
        raise SystemExit(
            "Usage: python -m satellite_orbit.phase2.prep_20_symh_1min "
            "[CSV_DIR FIRST_DAY LAST_DAY OUTPUT_DB]"
        )
    if arguments:
        source_dir, first_day, last_day, output_db = arguments
        result = write_symh_1min(
            Path(source_dir),
            (date.fromisoformat(first_day), date.fromisoformat(last_day)),
            Path(output_db),
        )
    else:
        result = write_symh_1min()
    print(result)


if __name__ == "__main__":
    main()
