"""Build Phase 2R event minutes without crossing Phase 1 chunk boundaries."""

import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from phases.phase0.code.calculation.density.calc_msis_p2_4 import load_msis_weather
from phases.phase0.code.data.density.down_swarm_density_pod import sha256_file
from phases.phase2.code.prep_23_t0_phase_window import (
    ALGORITHM_VERSION as PHASE2_ALGORITHM_VERSION,
    PHASE_ORBITS_AFTER,
    PHASE_ORBITS_BEFORE,
    SECOND_10_US,
    TWO_PI,
    create_tables,
    insert_event,
    minute_rows,
    phase_series,
    phase_source_rows,
    phase_value_at_time,
    phase_window,
    verify_output,
)


ALGORITHM_VERSION = "phase2r_t0_phase_v1"


@dataclass(frozen=True)
class Phase2RWindowPaths:
    """Input: P2R.2, Phase 1, weather. Output: P2R.3 SQLite path record."""

    storms: Path = Path("phases/phase2r/data/sqlite/swarm_a_phase2r_p2r_2_storms_v1.sqlite")
    phase1: Path = Path("phases/phase1r/data/sqlite/swarm_a_analysis_2014_2026_phase_candidate_working_v2.sqlite")
    gfz_ap: Path = Path("phases/phase0/data/raw/geomagnetic/gfz_ap_2014-07-01_2026-06-30.json")
    solar: Path = Path("phases/phase0/data/raw/space_weather/SW-All.csv")
    output: Path = Path("phases/phase2r/data/sqlite/swarm_a_phase2r_p2r_3_t0_phase_v1.sqlite")


def contiguous_segments(rows: list[sqlite3.Row]) -> list[list[sqlite3.Row]]:
    """Input: ordered Phase 1 rows. Output: single-chunk contiguous segments."""
    segments = []
    current = []
    for row in rows:
        if current and (
            row["chunk_id"] != current[-1]["chunk_id"]
            or row["time_us"] - current[-1]["time_us"] != SECOND_10_US
        ):
            segments.append(current)
            current = []
        current.append(row)
    if current:
        segments.append(current)
    return segments


def segment_at_time(rows: list[sqlite3.Row], time_us: int) -> list[sqlite3.Row] | None:
    """Input: Phase 1 rows and storm t0. Output: contiguous segment bracketing t0."""
    matches = [
        segment for segment in contiguous_segments(rows)
        if segment[0]["time_us"] <= time_us <= segment[-1]["time_us"]
    ]
    if len(matches) > 1:
        raise ValueError("Multiple Phase 1 segments bracket one storm t0.")
    return matches[0] if matches else None


def prepare_event(event: sqlite3.Row,
                  rows: list[sqlite3.Row]):
    """Input: one storm and nearby Phase 1 rows. Output: window, series, or exclusion."""
    segment = segment_at_time(rows, event["t0_time_us"])
    if segment is None:
        return None, None, "no_contiguous_phase_at_t0"
    series = phase_series(segment)
    t0_phase = phase_value_at_time(series, event["t0_time_us"])
    required_start = t0_phase - PHASE_ORBITS_BEFORE * TWO_PI
    required_end = t0_phase + PHASE_ORBITS_AFTER * TWO_PI
    if series.phases_rad[0] > required_start:
        return None, None, "insufficient_phase_before_t0"
    if series.phases_rad[-1] < required_end:
        return None, None, "insufficient_phase_after_t0"
    return phase_window(event, series), series, None


def create_exclusion_table(destination: sqlite3.Connection) -> None:
    """Input: P2R.3 SQLite. Output: empty event-exclusion audit table."""
    destination.execute(
        "CREATE TABLE storm_event_phase_exclusion_p2r_v1 ("
        "storm_id TEXT PRIMARY KEY, t0_time_us INTEGER NOT NULL, "
        "reason TEXT NOT NULL, algorithm_version TEXT NOT NULL)"
    )


def verify_replication(destination: sqlite3.Connection) -> dict:
    """Input: populated P2R.3. Output: used, excluded, and minute counts."""
    result = verify_output(destination)
    total_events = destination.execute("SELECT count(*) FROM storm_event_v2").fetchone()[0]
    excluded = destination.execute(
        "SELECT count(*) FROM storm_event_phase_exclusion_p2r_v1"
    ).fetchone()[0]
    if result["storms"] + excluded != total_events:
        raise ValueError("P2R.3 did not account for every P2R.2 event.")
    result["excluded_storms"] = excluded
    return result


def write_t0_phase_minutes(paths: Phase2RWindowPaths = Phase2RWindowPaths()) -> dict:
    """Input: P2R.2, Phase 1, weather. Output: checked P2R.3 SQLite."""
    if paths.output.exists():
        raise FileExistsError(paths.output)
    source_paths = {
        "storms": paths.storms,
        "phase1": paths.phase1,
        "gfz_ap": paths.gfz_ap,
        "solar": paths.solar,
    }
    for path in source_paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    hashes = {name: sha256_file(path) for name, path in source_paths.items()}
    weather = load_msis_weather(paths.gfz_ap, paths.solar)
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=paths.output.stem + ".", suffix=".building", dir=paths.output.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        shutil.copyfile(paths.storms, temporary)
        if sha256_file(temporary) != hashes["storms"]:
            raise ValueError("P2R.2 changed during copy.")
        phase1_uri = f"file:{paths.phase1.resolve().as_posix()}?mode=ro"
        with closing(sqlite3.connect(temporary)) as destination, closing(
            sqlite3.connect(phase1_uri, uri=True)
        ) as phase1:
            destination.row_factory = sqlite3.Row
            phase1.row_factory = sqlite3.Row
            destination.execute("PRAGMA foreign_keys=ON")
            events = destination.execute(
                "SELECT storm_id,t0_time_us,symh_min_nt,compound,n_minima "
                "FROM storm_event_v2 ORDER BY t0_time_us"
            ).fetchall()
            with destination:
                create_tables(destination)
                create_exclusion_table(destination)
                column_count = len(destination.execute(
                    "PRAGMA table_info(storm_minute_feature_v5)"
                ).fetchall())
                statement = "INSERT INTO storm_minute_feature_v5 VALUES (" + ",".join(
                    "?" * column_count
                ) + ")"
                for event in events:
                    rows = phase_source_rows(phase1, event["t0_time_us"])
                    window, series, exclusion = prepare_event(event, rows)
                    if exclusion is not None:
                        destination.execute(
                            "INSERT INTO storm_event_phase_exclusion_p2r_v1 VALUES (?,?,?,?)",
                            (event["storm_id"], event["t0_time_us"], exclusion, ALGORITHM_VERSION),
                        )
                        continue
                    insert_event(destination, window)
                    destination.executemany(
                        statement,
                        minute_rows(window, series, destination, weather),
                    )
                destination.executemany(
                    "INSERT OR REPLACE INTO phase2_metadata VALUES (?,?)",
                    (
                        ("replication_phase", "Phase 2R"),
                        ("p2r_3_algorithm_version", ALGORITHM_VERSION),
                        ("p2r_3_phase2_algorithm_version", PHASE2_ALGORITHM_VERSION),
                        ("p2_3_t0_phase_version", PHASE2_ALGORITHM_VERSION),
                        ("p2_3_t0_phase_before", str(PHASE_ORBITS_BEFORE)),
                        ("p2_3_t0_phase_after", str(PHASE_ORBITS_AFTER)),
                        ("p2_3_t0_phase_p2_2_sha256", hashes["storms"]),
                        ("p2_3_t0_phase_phase1_sha256", hashes["phase1"]),
                        ("p2_3_t0_phase_gfz_sha256", hashes["gfz_ap"]),
                        ("p2_3_t0_phase_solar_sha256", hashes["solar"]),
                        ("p2r_3_phase_before", str(PHASE_ORBITS_BEFORE)),
                        ("p2r_3_phase_after", str(PHASE_ORBITS_AFTER)),
                        ("p2r_3_p2r_2_sha256", hashes["storms"]),
                        ("p2r_3_phase1_sha256", hashes["phase1"]),
                        ("p2r_3_gfz_sha256", hashes["gfz_ap"]),
                        ("p2r_3_solar_sha256", hashes["solar"]),
                    ),
                )
            result = verify_replication(destination)
        if any(sha256_file(path) != hashes[name] for name, path in source_paths.items()):
            raise ValueError("P2R.3 source changed during build.")
        if paths.output.exists():
            raise FileExistsError(paths.output)
        os.rename(temporary, paths.output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return result


def main() -> None:
    """Input: fixed Phase 2R paths. Output: P2R.3 counts."""
    print(write_t0_phase_minutes())


if __name__ == "__main__":
    main()
