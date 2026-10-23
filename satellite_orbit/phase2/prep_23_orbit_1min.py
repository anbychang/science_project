"""Copy P2.2 and summarize Phase 1 orbit records by UTC minute."""

import math
import os
import shutil
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

from satellite_orbit.data.geomagnetic.down_supermag_sme import sha256_file
from satellite_orbit.phase2.prep_22_storm_event import ALGORITHM_VERSION as INPUT_VERSION


ALGORITHM_VERSION = "storm_orbit_1min_v2"
MINUTE_US = 60_000_000
EXPECTED_EPOCHS = 6
NOMINAL_GAP_S = 10.0
DEFAULT_INPUT_DB = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_2_v2.sqlite")
DEFAULT_PHASE1_DB = Path("data/sqlite/swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite")
DEFAULT_OUTPUT_DB = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_3_v2.sqlite")


def create_table(connection: sqlite3.Connection) -> None:
    """Input: copied P2.2 SQLite. Output: empty derived minute-orbit table."""
    connection.execute(
        """
        CREATE TABLE storm_orbit_1min_v2 (
            storm_id TEXT NOT NULL REFERENCES storm_event_v2(storm_id),
            bin_start_time_us INTEGER NOT NULL,
            bin_end_time_us INTEGER NOT NULL,
            mean_semi_major_axis_m REAL,
            orbit_phase_u_rad REAL,
            representative_time_us INTEGER,
            first_source_time_us INTEGER,
            last_source_time_us INTEGER,
            raw_epoch_count INTEGER NOT NULL,
            source_epoch_count INTEGER NOT NULL,
            max_source_gap_s REAL,
            chunk_id INTEGER,
            orbit_status TEXT NOT NULL CHECK (
                orbit_status IN ('complete', 'partial', 'no_usable_source', 'mixed_chunk')
            ),
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id, bin_end_time_us),
            CHECK (bin_end_time_us = bin_start_time_us + 60000000),
            CHECK (source_epoch_count <= raw_epoch_count)
        )
        """
    )


def source_rows(connection: sqlite3.Connection, start_us: int, end_us: int):
    """Input: read-only Phase 1 SQLite and UTC bounds. Output: ordered 10-s rows."""
    return connection.execute(
        """
        SELECT state.time_us, quality.is_usable, quality.chunk_id,
               mean.mean_semi_major_axis_m, mean.mean_argument_of_perigee_rad,
               mean.mean_anomaly_rad
        FROM swarm_a_states AS state
        LEFT JOIN swarm_a_pod_quality AS quality ON quality.time_us = state.time_us
        LEFT JOIN swarm_a_mean_orbit_elements_v1 AS mean ON mean.time_us = state.time_us
        WHERE state.time_us >= ? AND state.time_us < ?
        ORDER BY state.time_us
        """,
        (start_us, end_us),
    )


def summarize_minute(storm_id: str, start_us: int, rows: list[tuple]) -> tuple:
    """Input: storm ID, UTC minute start, source rows. Output: one derived bin row."""
    usable = [
        row for row in rows
        if row[1] == 1 and row[2] is not None and row[3] is not None
    ]
    source_count = len(usable)
    first_time = usable[0][0] if usable else None
    last_time = usable[-1][0] if usable else None
    max_gap_s = (
        max((later[0] - earlier[0]) / 1_000_000 for earlier, later in zip(usable, usable[1:]))
        if source_count >= 2 else None
    )
    chunks = {row[2] for row in usable}
    chunk_id = next(iter(chunks)) if len(chunks) == 1 else None
    mean_axis = None
    phase_u = None
    representative_time = None
    if not usable:
        status = "no_usable_source"
    elif len(chunks) > 1:
        status = "mixed_chunk"
    else:
        mean_axis = sum(row[3] for row in usable) / source_count
        if not math.isfinite(mean_axis):
            raise ValueError(f"Non-finite mean semi-major axis in {storm_id}:{start_us}")
        representative_time = last_time
        if usable[-1][4] is not None and usable[-1][5] is not None:
            phase_u = (usable[-1][4] + usable[-1][5]) % math.tau
        status = (
            "complete" if len(rows) == EXPECTED_EPOCHS and source_count == EXPECTED_EPOCHS
            and max_gap_s is not None and max_gap_s <= NOMINAL_GAP_S and phase_u is not None
            else "partial"
        )
    return (
        storm_id, start_us, start_us + MINUTE_US, mean_axis, phase_u,
        representative_time, first_time, last_time, len(rows), source_count,
        max_gap_s, chunk_id, status, ALGORITHM_VERSION,
    )


def event_minutes(source: sqlite3.Connection, event: tuple):
    """Input: Phase 1 SQLite and {storm_id, start_us, end_us}. Output: minute rows."""
    storm_id, start_us, end_us = event
    if start_us % MINUTE_US or end_us % MINUTE_US or end_us <= start_us:
        raise ValueError(f"Storm window is not an aligned UTC minute range: {storm_id}")
    rows = iter(source_rows(source, start_us, end_us))
    current = next(rows, None)
    for minute_start in range(start_us, end_us, MINUTE_US):
        minute_end = minute_start + MINUTE_US
        bucket = []
        while current is not None and current[0] < minute_end:
            bucket.append(current)
            current = next(rows, None)
        yield summarize_minute(storm_id, minute_start, bucket)


def verify_output(connection: sqlite3.Connection, expected_bins: int) -> dict:
    """Input: populated P2.3 SQLite and expected bins. Output: checked counts."""
    count, complete, partial, absent, mixed = connection.execute(
        "SELECT count(*), sum(orbit_status = 'complete'), "
        "sum(orbit_status = 'partial'), sum(orbit_status = 'no_usable_source'), "
        "sum(orbit_status = 'mixed_chunk') FROM storm_orbit_1min_v2"
    ).fetchone()
    if count != expected_bins or count != complete + partial + absent + mixed:
        raise ValueError("P2.3 minute coverage does not match event windows.")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("P2.3 foreign-key check failed.")
    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("P2.3 SQLite integrity check failed.")
    return {"minute_rows": count, "complete": complete, "partial": partial,
            "no_usable_source": absent, "mixed_chunk": mixed}


def write_orbit_1min(input_db: Path = DEFAULT_INPUT_DB,
                     phase1_db: Path = DEFAULT_PHASE1_DB,
                     output_db: Path = DEFAULT_OUTPUT_DB) -> dict:
    """Input: frozen P2.2, Phase 1, new path. Output: verified P2.3 counts."""
    input_db = Path(input_db).resolve()
    phase1_db = Path(phase1_db).resolve()
    output_db = Path(output_db).resolve()
    if not input_db.is_file() or not phase1_db.is_file():
        raise FileNotFoundError("P2.2 and Phase 1 SQLite must both exist.")
    if output_db.exists():
        raise FileExistsError(output_db)
    input_hash = sha256_file(input_db)
    phase1_hash = sha256_file(phase1_db)
    output_db.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=output_db.stem + ".", suffix=".building", dir=output_db.parent
    )
    os.close(handle)
    temporary_path = Path(temporary_name)
    try:
        shutil.copyfile(input_db, temporary_path)
        if sha256_file(temporary_path) != input_hash:
            raise ValueError("P2.2 checkpoint changed during copy.")
        with closing(sqlite3.connect(temporary_path)) as destination, closing(
            sqlite3.connect(f"file:{phase1_db.as_posix()}?mode=ro", uri=True)
        ) as source:
            destination.execute("PRAGMA foreign_keys = ON")
            version = destination.execute(
                "SELECT value FROM phase2_metadata WHERE name = 'p2_2_algorithm_version'"
            ).fetchone()
            if version != (INPUT_VERSION,):
                raise ValueError("Input is not the P2.2 storm checkpoint.")
            events = destination.execute(
                "SELECT storm_id, window_start_time_us, window_end_time_us "
                "FROM storm_event_v2 ORDER BY window_start_time_us"
            ).fetchall()
            if not events:
                raise ValueError("P2.2 has no storm events.")
            for earlier, later in zip(events, events[1:]):
                if earlier[2] > later[1]:
                    raise ValueError("P2.2 storm windows overlap.")
            expected_bins = sum((end - start) // MINUTE_US for _, start, end in events)
            with destination:
                create_table(destination)
                for event in events:
                    destination.executemany(
                        "INSERT INTO storm_orbit_1min_v2 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        event_minutes(source, event),
                    )
                destination.executemany(
                    "INSERT INTO phase2_metadata VALUES (?, ?)",
                    (("p2_2_sha256", input_hash),
                     ("p2_3_phase1_file", phase1_db.name),
                     ("p2_3_phase1_sha256", phase1_hash),
                     ("p2_3_algorithm_version", ALGORITHM_VERSION),
                     ("p2_3_expected_bins", str(expected_bins))),
                )
            counts = verify_output(destination, expected_bins)
        if sha256_file(input_db) != input_hash or sha256_file(phase1_db) != phase1_hash:
            raise ValueError("An input checkpoint changed while P2.3 was built.")
        if output_db.exists():
            raise FileExistsError(output_db)
        os.rename(temporary_path, output_db)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return counts


def main() -> None:
    """Input: optional P2_2_DB PHASE1_DB OUTPUT_DB. Output: P2.3 counts."""
    arguments = sys.argv[1:]
    if len(arguments) not in (0, 3):
        raise SystemExit(
            "Usage: python -m satellite_orbit.phase2.prep_23_orbit_1min "
            "[P2_2_DB PHASE1_DB OUTPUT_DB]"
        )
    print(write_orbit_1min(*map(Path, arguments)) if arguments else write_orbit_1min())


if __name__ == "__main__":
    main()
