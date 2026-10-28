"""Freeze the verified Phase 2 source audit in a SQLite checkpoint."""

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

from research_workspace.phases.phase0.code.data.geomagnetic.down_supermag_sme import sha256_file


ALGORITHM_VERSION = "source_audit_v2"
DEFAULT_AUDIT = Path("research_workspace/phases/phase2/data/sqlite/phase2_p2_0_source_audit.json")
DEFAULT_OUTPUT_DB = Path("research_workspace/phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_0_v2.sqlite")


def write_source_checkpoint(audit_path: Path = DEFAULT_AUDIT,
                            output_db: Path = DEFAULT_OUTPUT_DB) -> str:
    """Input: verified audit JSON and new SQLite path. Output: source audit SHA-256."""
    audit_path = Path(audit_path).resolve()
    output_db = Path(output_db).resolve()
    if output_db.exists():
        raise FileExistsError(output_db)
    audit_text = audit_path.read_text(encoding="utf-8")
    audit = json.loads(audit_text)
    if audit["date_range_utc"] != ["2023-07-01", "2026-06-30"]:
        raise ValueError("P2.0 requires the verified three-year source audit.")
    audit_hash = sha256_file(audit_path)
    output_db.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=output_db.stem + ".", suffix=".building", dir=output_db.parent
    )
    os.close(handle)
    temporary_path = Path(temporary_name)
    try:
        connection = sqlite3.connect(temporary_path)
        try:
            with connection:
                connection.execute(
                    "CREATE TABLE source_audit_v2 (audit_sha256 TEXT PRIMARY KEY, "
                    "audit_json TEXT NOT NULL, algorithm_version TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE phase2_metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL)"
                )
                connection.execute(
                    "INSERT INTO source_audit_v2 VALUES (?, ?, ?)",
                    (audit_hash, audit_text, ALGORITHM_VERSION),
                )
                connection.executemany(
                    "INSERT INTO phase2_metadata VALUES (?, ?)",
                    (("algorithm_version", ALGORITHM_VERSION),
                     ("source_audit_sha256", audit_hash),
                     ("first_day_utc", audit["date_range_utc"][0]),
                     ("last_day_utc", audit["date_range_utc"][1])),
                )
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("P2.0 SQLite integrity check failed.")
        finally:
            connection.close()
        if sha256_file(audit_path) != audit_hash:
            raise ValueError("P2.0 audit changed during checkpoint creation.")
        if output_db.exists():
            raise FileExistsError(output_db)
        os.rename(temporary_path, output_db)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return audit_hash


def main() -> None:
    """Input: optional AUDIT_JSON OUTPUT_DB. Output: printed audit SHA-256."""
    arguments = sys.argv[1:]
    if len(arguments) not in (0, 2):
        raise SystemExit("Usage: python -m research_workspace.phases.phase2.code.prep_20_source_checkpoint [AUDIT_JSON OUTPUT_DB]")
    print(write_source_checkpoint(*map(Path, arguments)) if arguments else write_source_checkpoint())


if __name__ == "__main__":
    main()
