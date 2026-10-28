"""Copy the P2.1 checkpoint and detect merged SYM-H storm events."""

import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from research_workspace.phases.phase0.code.data.geomagnetic.down_supermag_sme import sha256_file
from research_workspace.phases.phase2.code.prep_21_geomag_1min import ALGORITHM_VERSION as INPUT_VERSION


ALGORITHM_VERSION = "storm_event_symh_v2"
MINUTE_US = 60_000_000
HOUR_US = 60 * MINUTE_US
NEAR_GAP_US = 72 * HOUR_US
BEFORE_US = 48 * HOUR_US
AFTER_US = 96 * HOUR_US
THRESHOLD_NT = -100
DEFAULT_INPUT_DB = Path("research_workspace/phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_1_v2.sqlite")
DEFAULT_OUTPUT_DB = Path("research_workspace/phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_2_v2.sqlite")


def constant_runs(rows):
    """Input: time-ordered minute rows. Output: constant contiguous SYM-H runs."""
    current = None
    for time_us, value, version, file_name in rows:
        if current is not None and time_us == current[1] + MINUTE_US and value == current[2]:
            current[1] = time_us
        else:
            if current is not None:
                yield current
            current = [time_us, time_us, value, version, file_name]
    if current is not None:
        yield current


def find_local_minima(rows) -> list[dict]:
    """Input: ordered observed SYM-H rows. Output: sub-threshold local minima."""
    previous = current = None
    minima = []
    for upcoming in constant_runs(rows):
        if previous is not None and current is not None:
            start, end, value, version, file_name = current
            if (value is not None and value < THRESHOLD_NT
                    and previous[2] is not None and upcoming[2] is not None
                    and previous[1] + MINUTE_US == start
                    and end + MINUTE_US == upcoming[0]
                    and value < previous[2] and value < upcoming[2]):
                minima.append({
                    "minimum_time_us": start,
                    "symh_min_nt": value,
                    "symh_version": version,
                    "symh_source_file_name": file_name,
                })
        previous, current = current, upcoming
    return minima


def nearby_groups(minima: list[dict]) -> list[list[dict]]:
    """Input: ordered minima. Output: groups with adjacent gaps below 72 h."""
    groups = []
    for minimum in minima:
        if not groups or minimum["minimum_time_us"] - groups[-1][-1]["minimum_time_us"] >= NEAR_GAP_US:
            groups.append([minimum])
        else:
            groups[-1].append(minimum)
    return groups


def overlapping_groups(near_groups: list[list[dict]]) -> list[list[list[dict]]]:
    """Input: nearby groups. Output: groups with connected storm windows."""
    events = []
    for group in near_groups:
        window_start = group[0]["minimum_time_us"] - BEFORE_US
        if events:
            current_end = max(
                minimum["minimum_time_us"] + AFTER_US
                for near_group in events[-1] for minimum in near_group
            )
            if window_start < current_end:
                events[-1].append(group)
                continue
        events.append([group])
    return events


def storm_id(time_us: int) -> str:
    """Input: UTC minimum time in us. Output: minute-specific storm identifier."""
    moment = datetime.fromtimestamp(time_us // 1_000_000, timezone.utc)
    return moment.strftime("S%Y%m%dT%H%M")


def merge_minima(minima: list[dict]) -> tuple[list[dict], list[dict]]:
    """Input: ordered minima. Output: assigned minima and merged event records."""
    events = []
    for event_groups in overlapping_groups(nearby_groups(minima)):
        members = [minimum for group in event_groups for minimum in group]
        deepest = min(members, key=lambda row: (row["symh_min_nt"], row["minimum_time_us"]))
        event_id = storm_id(deepest["minimum_time_us"])
        events.append({
            "storm_id": event_id,
            "t0_time_us": deepest["minimum_time_us"],
            "symh_min_nt": deepest["symh_min_nt"],
            "window_start_time_us": min(row["minimum_time_us"] - BEFORE_US for row in members),
            "window_end_time_us": max(row["minimum_time_us"] + AFTER_US for row in members),
            "compound": int(len(members) > 1),
            "n_minima": len(members),
        })
        for group in event_groups:
            near_deepest = min(group, key=lambda row: (row["symh_min_nt"], row["minimum_time_us"]))
            for row in group:
                row["storm_id"] = event_id
                row["merge_reason"] = (
                    "representative" if row is deepest else
                    "within_72h" if row is not near_deepest else "overlap_window"
                )
    return minima, events


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: copied P2.1 connection. Output: versioned event tables."""
    connection.executescript(
        """
        CREATE TABLE storm_event_v2 (
            storm_id TEXT PRIMARY KEY,
            t0_time_us INTEGER NOT NULL UNIQUE,
            symh_min_nt INTEGER NOT NULL,
            window_start_time_us INTEGER NOT NULL,
            window_end_time_us INTEGER NOT NULL,
            compound INTEGER NOT NULL CHECK (compound IN (0, 1)),
            n_minima INTEGER NOT NULL CHECK (n_minima >= 1),
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE storm_minimum_v2 (
            minimum_time_us INTEGER PRIMARY KEY,
            symh_min_nt INTEGER NOT NULL,
            symh_version INTEGER NOT NULL,
            symh_source_file_name TEXT NOT NULL REFERENCES geomag_source_files_v2(file_name),
            storm_id TEXT NOT NULL REFERENCES storm_event_v2(storm_id),
            merge_reason TEXT NOT NULL CHECK (
                merge_reason IN ('representative', 'within_72h', 'overlap_window')
            ),
            algorithm_version TEXT NOT NULL
        );
        CREATE INDEX storm_minimum_event_v2 ON storm_minimum_v2(storm_id);
        """
    )


def store_events(connection: sqlite3.Connection, minima: list[dict], events: list[dict]) -> None:
    """Input: copied SQLite, assigned minima, events. Output: persisted event tables."""
    connection.executemany(
        "INSERT INTO storm_event_v2 VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            (event["storm_id"], event["t0_time_us"], event["symh_min_nt"],
             event["window_start_time_us"], event["window_end_time_us"],
             event["compound"], event["n_minima"], ALGORITHM_VERSION)
            for event in events
        ),
    )
    connection.executemany(
        "INSERT INTO storm_minimum_v2 VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            (minimum["minimum_time_us"], minimum["symh_min_nt"],
             minimum["symh_version"], minimum["symh_source_file_name"],
             minimum["storm_id"], minimum["merge_reason"], ALGORITHM_VERSION)
            for minimum in minima
        ),
    )


def verify_events(connection: sqlite3.Connection, minima: list[dict], events: list[dict]) -> None:
    """Input: populated P2.2 SQLite and expected records. Output: validated tables."""
    if connection.execute("SELECT count(*) FROM storm_minimum_v2").fetchone()[0] != len(minima):
        raise ValueError("P2.2 minimum count changed during storage.")
    if connection.execute("SELECT count(*) FROM storm_event_v2").fetchone()[0] != len(events):
        raise ValueError("P2.2 event count changed during storage.")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("P2.2 foreign-key check failed.")
    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("P2.2 SQLite integrity check failed.")
    for earlier, later in zip(events, events[1:]):
        if earlier["window_end_time_us"] > later["window_start_time_us"]:
            raise ValueError("P2.2 merged events still overlap.")


def write_storm_events(input_db: Path = DEFAULT_INPUT_DB, output_db: Path = DEFAULT_OUTPUT_DB) -> dict:
    """Input: frozen P2.1 SQLite and new output path. Output: P2.2 counts."""
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
            raise ValueError("P2.1 checkpoint changed during copy.")
        connection = sqlite3.connect(temporary_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            version = connection.execute(
                "SELECT value FROM phase2_metadata WHERE name = 'algorithm_version'"
            ).fetchone()
            if version != (INPUT_VERSION,):
                raise ValueError("Input is not the new P2.1 checkpoint.")
            rows = connection.execute(
                "SELECT time_us, symh_nt, symh_version, symh_source_file_name "
                "FROM geomag_1min_v2 ORDER BY time_us"
            )
            minima, events = merge_minima(find_local_minima(rows))
            create_tables(connection)
            with connection:
                store_events(connection, minima, events)
                connection.executemany(
                    "INSERT INTO phase2_metadata VALUES (?, ?)",
                    (
                        ("p2_1_sha256", source_hash),
                        ("p2_2_algorithm_version", ALGORITHM_VERSION),
                        ("p2_2_symh_threshold_nt", str(THRESHOLD_NT)),
                        ("p2_2_near_gap_h", "72"),
                        ("p2_2_window_before_h", "48"),
                        ("p2_2_window_after_h", "96"),
                    ),
                )
            verify_events(connection, minima, events)
        finally:
            connection.close()
        if sha256_file(input_db) != source_hash:
            raise ValueError("P2.1 checkpoint changed while P2.2 was built.")
        if output_db.exists():
            raise FileExistsError(output_db)
        os.rename(temporary_path, output_db)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return {"local_minima": len(minima), "merged_events": len(events),
            "compound_events": sum(event["compound"] for event in events)}


def main() -> None:
    """Input: optional INPUT_DB OUTPUT_DB. Output: printed P2.2 counts."""
    arguments = sys.argv[1:]
    if len(arguments) not in (0, 2):
        raise SystemExit("Usage: python -m research_workspace.phases.phase2.code.prep_22_storm_event [INPUT_DB OUTPUT_DB]")
    print(write_storm_events(*map(Path, arguments)) if arguments else write_storm_events())


if __name__ == "__main__":
    main()
