"""Build the twelve-year observed one-minute geomagnetic checkpoint."""

import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from research_workspace.phases.phase0.code.data.geomagnetic.down_supermag_sme import sha256_file
from research_workspace.phases.phase2.code.prep_21_geomag_1min import (
    ALGORITHM_VERSION,
    create_tables,
    import_kyoto,
    sme_rows,
    verify_counts,
)
from research_workspace.phases.phase2r.code.prep_2r0_source_audit import FIRST_DAY, LAST_DAY
from research_workspace.phases.phase2r.code.prep_2r0_source_checkpoint import (
    ALGORITHM_VERSION as INPUT_VERSION,
    DEFAULT_OUTPUT_DB as DEFAULT_INPUT_DB,
)


DEFAULT_OUTPUT_DB = Path("research_workspace/phases/phase2r/data/sqlite/swarm_a_phase2r_p2r_1_geomag_v1.sqlite")
EXPECTED_RANGE = [FIRST_DAY.isoformat(), LAST_DAY.isoformat()]


@dataclass(frozen=True)
class GeomagPaths:
    """Input: raw root and P2R.0. Output: P2R.1 SQLite path record."""

    data_root: Path = Path("research_workspace/phases/phase0/data/raw")
    input_db: Path = DEFAULT_INPUT_DB
    output_db: Path = DEFAULT_OUTPUT_DB


def source_audit(connection: sqlite3.Connection) -> dict:
    """Input: copied P2R.0 SQLite. Output: verified embedded source audit."""
    audit_hash, audit_text = connection.execute(
        "SELECT audit_sha256, audit_json FROM source_audit_v2"
    ).fetchone()
    if hashlib.sha256(audit_text.encode("utf-8")).hexdigest() != audit_hash:
        raise ValueError("Embedded P2R.0 audit hash is invalid.")
    audit = json.loads(audit_text)
    if audit["date_range_utc"] != EXPECTED_RANGE:
        raise ValueError("P2R.1 requires the fixed twelve-year source audit.")
    stored_hash = connection.execute(
        "SELECT value FROM phase2_metadata WHERE name='source_audit_sha256'"
    ).fetchone()
    if stored_hash != (audit_hash,):
        raise ValueError("P2R.0 metadata and embedded audit differ.")
    return audit


def sme_manifest_records(path: Path) -> dict[str, dict]:
    """Input: full SME manifest. Output: unique records keyed by file name."""
    records = {}
    for record in json.loads(path.read_text(encoding="utf-8"))["files"]:
        if record["file_name"] in records:
            raise ValueError(f"Duplicate SME manifest record: {record['file_name']}")
        records[record["file_name"]] = record
    return records


def import_sme(connection: sqlite3.Connection, data_root: Path, audit: dict) -> None:
    """Input: new SQLite, raw root, audit. Output: selected SME minute grid."""
    folder = data_root / "sme"
    manifest_path = folder / "manifest_p2_0_sme.json"
    if sha256_file(manifest_path) != audit["sme"]["manifest_sha256"]:
        raise ValueError("SME manifest changed since P2R.0.")
    records = sme_manifest_records(manifest_path)
    first_day, last_day = map(date.fromisoformat, audit["date_range_utc"])
    day_count = (last_day - first_day).days + 1
    if day_count != audit["sme"]["day_files"]:
        raise ValueError("SME selected day count changed.")
    for offset in range(day_count):
        day = first_day + timedelta(days=offset)
        file_name = f"SME_{day:%Y%m%d}.csv"
        record = records.get(file_name)
        path = folder / file_name
        if record is None or sha256_file(path) != record["sha256"]:
            raise ValueError(f"SME source changed: {file_name}")
        connection.execute(
            "INSERT INTO geomag_source_files_v2 VALUES (?, ?, ?, ?, ?, ?)",
            (
                file_name,
                "SME",
                record["sha256"],
                None,
                record.get("downloaded_at_utc"),
                ALGORITHM_VERSION,
            ),
        )
        connection.executemany(
            "INSERT INTO geomag_1min_v2 "
            "(time_us, sme_nt, sme_station_count, sme_valid, sme_source_file_name, "
            "sme_not_before_time_us, kyoto_not_before_time_us, algorithm_version) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            sme_rows(path, day),
        )


def write_geomag_1min(paths: GeomagPaths = GeomagPaths()) -> dict:
    """Input: raw root and P2R.0. Output: checked twelve-year minute SQLite."""
    data_root = Path(paths.data_root).resolve()
    input_db = Path(paths.input_db).resolve()
    output_db = Path(paths.output_db).resolve()
    if not input_db.is_file():
        raise FileNotFoundError(input_db)
    if output_db.exists():
        raise FileExistsError(output_db)
    source_hash = sha256_file(input_db)
    output_db.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=output_db.stem + ".", suffix=".building", dir=output_db.parent
    )
    os.close(handle)
    temporary_path = Path(temporary_name)
    try:
        shutil.copyfile(input_db, temporary_path)
        if sha256_file(temporary_path) != source_hash:
            raise ValueError("P2R.0 checkpoint changed during copy.")
        connection = sqlite3.connect(temporary_path)
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=OFF")
            connection.execute("PRAGMA synchronous=OFF")
            version = connection.execute(
                "SELECT value FROM phase2_metadata WHERE name='algorithm_version'"
            ).fetchone()
            if version != (INPUT_VERSION,):
                raise ValueError("Input is not a P2R.0 source checkpoint.")
            audit = source_audit(connection)
            create_tables(connection)
            with connection:
                import_sme(connection, data_root, audit)
                import_kyoto(connection, data_root, audit)
                connection.executemany(
                    "INSERT OR REPLACE INTO phase2_metadata VALUES (?, ?)",
                    (
                        ("algorithm_version", ALGORITHM_VERSION),
                        ("replication_phase", "Phase 2R"),
                        ("p2r_0_sha256", source_hash),
                        ("first_day_utc", EXPECTED_RANGE[0]),
                        ("last_day_utc", EXPECTED_RANGE[1]),
                        ("sme_time_rule", "source label plus 60 seconds; not publication time"),
                        ("kyoto_time_rule", "center label plus 30 seconds; not publication time"),
                        ("missing_policy", "NULL; no interpolation"),
                    ),
                )
            counts = verify_counts(connection, audit)
        finally:
            connection.close()
        if sha256_file(input_db) != source_hash:
            raise ValueError("P2R.0 checkpoint changed while P2R.1 was built.")
        if output_db.exists():
            raise FileExistsError(output_db)
        os.rename(temporary_path, output_db)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return counts


def main() -> None:
    """Input: optional DATA_ROOT P2R0_DB OUTPUT_DB. Output: P2R.1 counts."""
    arguments = sys.argv[1:]
    if len(arguments) not in (0, 3):
        raise SystemExit(
            "Usage: python -m research_workspace.phases.phase2r.code.prep_2r1_geomag_1min "
            "[DATA_ROOT P2R0_DB OUTPUT_DB]"
        )
    paths = GeomagPaths(*map(Path, arguments)) if arguments else GeomagPaths()
    print(write_geomag_1min(paths))


if __name__ == "__main__":
    main()
