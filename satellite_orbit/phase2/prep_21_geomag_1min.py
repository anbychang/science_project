"""Build the observed one-minute Phase 2 geomagnetic checkpoint."""

import csv
import hashlib
import json
import math
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from satellite_orbit.data.geomagnetic.down_supermag_sme import sha256_file
from satellite_orbit.phase2.prep_20_source_checkpoint import ALGORITHM_VERSION as INPUT_VERSION


ALGORITHM_VERSION = "geomag_1min_raw_v2"
MINUTE_US = 60_000_000
DEFAULT_DATA_ROOT = Path("data")
DEFAULT_OUTPUT_DB = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_1_v2.sqlite")
DEFAULT_INPUT_DB = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_0_v2.sqlite")


def source_audit(connection: sqlite3.Connection) -> dict:
    """Input: copied P2.0 SQLite. Output: verified embedded source audit."""
    audit_hash, audit_text = connection.execute(
        "SELECT audit_sha256, audit_json FROM source_audit_v2"
    ).fetchone()
    if hashlib.sha256(audit_text.encode("utf-8")).hexdigest() != audit_hash:
        raise ValueError("Embedded P2.0 audit hash is invalid.")
    audit = json.loads(audit_text)
    if audit["date_range_utc"] != ["2023-07-01", "2026-06-30"]:
        raise ValueError("P2.1 requires the verified three-year source audit.")
    stored_hash = connection.execute(
        "SELECT value FROM phase2_metadata WHERE name = 'source_audit_sha256'"
    ).fetchone()
    if stored_hash != (audit_hash,):
        raise ValueError("P2.0 metadata and embedded audit differ.")
    return audit


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: new SQLite connection. Output: source, minute, and metadata tables."""
    connection.executescript(
        """
        CREATE TABLE geomag_source_files_v2 (
            file_name TEXT PRIMARY KEY,
            source_kind TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            modification_date TEXT,
            downloaded_at_utc TEXT,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE geomag_1min_v2 (
            time_us INTEGER PRIMARY KEY,
            sme_nt REAL,
            sme_station_count INTEGER NOT NULL,
            sme_valid INTEGER NOT NULL CHECK (sme_valid IN (0, 1)),
            symh_nt INTEGER,
            symh_version INTEGER,
            ae_nt INTEGER,
            ae_version INTEGER,
            sme_source_file_name TEXT NOT NULL REFERENCES geomag_source_files_v2(file_name),
            symh_source_file_name TEXT REFERENCES geomag_source_files_v2(file_name),
            ae_source_file_name TEXT REFERENCES geomag_source_files_v2(file_name),
            sme_not_before_time_us INTEGER NOT NULL,
            kyoto_not_before_time_us INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS phase2_metadata (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )


def sme_rows(path: Path, day: date):
    """Input: one raw SME CSV and UTC day. Output: ordered minute records."""
    day_start = int(datetime.combine(day, time.min, timezone.utc).timestamp())
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != ["tval", "SME", "SMEnum"]:
            raise ValueError(f"Unexpected SME columns: {path.name}")
        row_count = 0
        for minute, row in enumerate(reader):
            row_count += 1
            second = int(float(row["tval"]))
            if float(row["tval"]) != second or second != day_start + minute * 60:
                raise ValueError(f"Unexpected SME minute: {path.name}:{minute}")
            value = float(row["SME"])
            stations = int(row["SMEnum"])
            missing = value == 999999.0 and stations == 0
            if not missing and (not math.isfinite(value) or value < 0 or value >= 999998 or stations < 1):
                raise ValueError(f"Unexpected SME value: {path.name}:{minute}")
            if (value == 999999.0) != (stations == 0):
                raise ValueError(f"Ambiguous SME fill: {path.name}:{minute}")
            time_us = second * 1_000_000
            yield (
                time_us, None if missing else value, stations, int(not missing),
                path.name, time_us + MINUTE_US, time_us + MINUTE_US // 2,
                ALGORITHM_VERSION,
            )
        if row_count != 1440:
            raise ValueError(f"Incomplete SME day: {path.name}")


def import_sme(connection: sqlite3.Connection, data_root: Path, audit: dict) -> None:
    """Input: new SQLite, raw data root, audit. Output: SME-backed minute grid."""
    folder = data_root / "sme"
    manifest_path = folder / "manifest_p2_0_sme.json"
    if sha256_file(manifest_path) != audit["sme"]["manifest_sha256"]:
        raise ValueError("SME manifest changed since P2.0.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    first_day = date.fromisoformat(audit["date_range_utc"][0])
    files = manifest["files"]
    if len(files) != audit["sme"]["day_files"]:
        raise ValueError("SME manifest day count changed.")
    for offset, record in enumerate(files):
        day = first_day + timedelta(days=offset)
        expected_name = f"SME_{day:%Y%m%d}.csv"
        path = folder / expected_name
        if record["file_name"] != expected_name or sha256_file(path) != record["sha256"]:
            raise ValueError(f"SME source changed: {expected_name}")
        connection.execute(
            "INSERT INTO geomag_source_files_v2 VALUES (?, ?, ?, ?, ?, ?)",
            (expected_name, "SME", record["sha256"], None,
             record["downloaded_at_utc"], ALGORITHM_VERSION),
        )
        connection.executemany(
            "INSERT INTO geomag_1min_v2 "
            "(time_us, sme_nt, sme_station_count, sme_valid, sme_source_file_name, "
            "sme_not_before_time_us, kyoto_not_before_time_us, algorithm_version) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            sme_rows(path, day),
        )


def kyoto_rows(path: Path, first_day: date, last_day: date):
    """Input: raw HAPI CSV and inclusive UTC days. Output: observed minute rows."""
    first_stamp = first_day.isoformat() + "T00:00:00Z"
    last_stamp = (last_day + timedelta(days=1)).isoformat() + "T00:00:00Z"
    with path.open(newline="", encoding="utf-8") as source:
        source.readline()
        for stamp, value, version in csv.reader(source):
            if not first_stamp <= stamp < last_stamp:
                continue
            if len(stamp) != 20 or stamp[17:] != "00Z":
                raise ValueError(f"Kyoto minute is off-grid: {path.name}:{stamp}")
            number = int(value)
            if number == 99999:
                continue
            moment = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            yield number, int(version), path.name, int(moment.timestamp()) * 1_000_000


def import_kyoto(connection: sqlite3.Connection, data_root: Path, audit: dict) -> None:
    """Input: SME minute grid, raw data root, audit. Output: SYM-H and AE columns."""
    first_day, last_day = map(date.fromisoformat, audit["date_range_utc"])
    for prefix, kind, field in (("sym_h", "SYM-H", "symh"), ("ae", "AE", "ae")):
        for file_name, source_record in sorted(audit[field]["source_sha256"].items()):
            path = data_root / "geomagnetic" / file_name
            if sha256_file(path) != source_record["sha256"]:
                raise ValueError(f"Kyoto source changed: {file_name}")
            with path.open(encoding="utf-8") as source:
                header = json.loads(source.readline()[1:])
            column = "symHValue" if prefix == "sym_h" else "aeValue"
            names = [item["name"] for item in header["parameters"]]
            if (header["cadence"] != "PT1M" or header["timeStampLocation"] != "center"
                    or names != ["Time", column, "versionCode"]
                    or header["modificationDate"] != source_record["modification_date"]):
                raise ValueError(f"Unexpected Kyoto metadata: {file_name}")
            connection.execute(
                "INSERT INTO geomag_source_files_v2 VALUES (?, ?, ?, ?, ?, ?)",
                (file_name, kind, source_record["sha256"],
                 source_record["modification_date"], None, ALGORITHM_VERSION),
            )
            connection.executemany(
                f"UPDATE geomag_1min_v2 SET {field}_nt = ?, {field}_version = ?, "
                f"{field}_source_file_name = ? WHERE time_us = ? AND {field}_nt IS NULL",
                kyoto_rows(path, first_day, last_day),
            )


def verify_counts(connection: sqlite3.Connection, audit: dict) -> dict[str, int]:
    """Input: populated SQLite and P2.0 audit. Output: verified minute counts."""
    row = connection.execute(
        "SELECT count(*), sum(sme_valid), count(symh_nt), count(ae_nt), "
        "min(time_us), max(time_us) FROM geomag_1min_v2"
    ).fetchone()
    first_day, last_day = map(date.fromisoformat, audit["date_range_utc"])
    first_us = int(datetime.combine(first_day, time.min, timezone.utc).timestamp()) * 1_000_000
    last_us = int(datetime.combine(last_day + timedelta(days=1), time.min, timezone.utc).timestamp()) * 1_000_000 - MINUTE_US
    expected = (
        audit["sme"]["minute_slots"], audit["sme"]["valid_minutes"],
        audit["symh"]["observed_minutes"], audit["ae"]["observed_minutes"],
        first_us, last_us,
    )
    if row != expected:
        raise ValueError(f"P2.1 minute counts differ from P2.0: {row} != {expected}")
    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("P2.1 SQLite integrity check failed.")
    return dict(zip(("minute_rows", "valid_sme", "valid_symh", "valid_ae"), row[:4]))


def write_geomag_1min(data_root: Path = DEFAULT_DATA_ROOT,
                      input_db: Path = DEFAULT_INPUT_DB,
                      output_db: Path = DEFAULT_OUTPUT_DB) -> dict:
    """Input: raw root, frozen P2.0, new SQLite path. Output: P2.1 counts."""
    data_root = Path(data_root).resolve()
    input_db = Path(input_db).resolve()
    output_db = Path(output_db).resolve()
    if not input_db.is_file():
        raise FileNotFoundError(input_db)
    if output_db.exists():
        raise FileExistsError(output_db)
    source_hash = sha256_file(input_db)
    output_db.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=output_db.stem + ".", suffix=".building", dir=output_db.parent)
    os.close(handle)
    temporary_path = Path(temporary_name)
    try:
        shutil.copyfile(input_db, temporary_path)
        if sha256_file(temporary_path) != source_hash:
            raise ValueError("P2.0 checkpoint changed during copy.")
        connection = sqlite3.connect(temporary_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = OFF")
            connection.execute("PRAGMA synchronous = OFF")
            version = connection.execute(
                "SELECT value FROM phase2_metadata WHERE name = 'algorithm_version'"
            ).fetchone()
            if version != (INPUT_VERSION,):
                raise ValueError("Input is not a P2.0 source checkpoint.")
            audit = source_audit(connection)
            create_tables(connection)
            with connection:
                import_sme(connection, data_root, audit)
                import_kyoto(connection, data_root, audit)
                connection.executemany(
                    "INSERT OR REPLACE INTO phase2_metadata VALUES (?, ?)",
                    (
                        ("algorithm_version", ALGORITHM_VERSION),
                        ("p2_0_sha256", source_hash),
                        ("first_day_utc", audit["date_range_utc"][0]),
                        ("last_day_utc", audit["date_range_utc"][1]),
                        ("sme_time_rule", "source label plus 60 seconds; not publication time"),
                        ("kyoto_time_rule", "center label plus 30 seconds; not publication time"),
                        ("missing_policy", "NULL; no interpolation"),
                    ),
                )
            counts = verify_counts(connection, audit)
        finally:
            connection.close()
        if sha256_file(input_db) != source_hash:
            raise ValueError("P2.0 checkpoint changed while P2.1 was built.")
        if output_db.exists():
            raise FileExistsError(output_db)
        os.rename(temporary_path, output_db)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return counts


def main() -> None:
    """Input: optional DATA_ROOT P2_0_DB OUTPUT_DB. Output: printed P2.1 counts."""
    arguments = sys.argv[1:]
    if len(arguments) not in (0, 3):
        raise SystemExit("Usage: python -m satellite_orbit.phase2.prep_21_geomag_1min [DATA_ROOT P2_0_DB OUTPUT_DB]")
    print(write_geomag_1min(*map(Path, arguments)) if arguments else write_geomag_1min())


if __name__ == "__main__":
    main()
