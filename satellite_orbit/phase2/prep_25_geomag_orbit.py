"""Summarize Phase 2 minute geomagnetic measurements by complete orbit."""

import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

from satellite_orbit.data.density.down_swarm_density_pod import sha256_file


SOURCE_DB = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_4_density_v3.sqlite")
OUTPUT_DB = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_5_geomag_orbit_v1.sqlite")
ALGORITHM_VERSION = "storm_geomag_orbit_v1"
MINUTE_US = 60_000_000
HOUR_US = 3_600_000_000
COVERAGE_PARTS = 5
COVERAGE_REQUIRED_PARTS = 4


def expected_minute_count(start_us: int, end_us: int) -> int:
    """Input: [start, end) UTC orbit bounds in us. Output: minute-center count."""
    if end_us <= start_us:
        raise ValueError("Orbit end must follow start.")
    first = (start_us + MINUTE_US - 1) // MINUTE_US
    after_last = (end_us + MINUTE_US - 1) // MINUTE_US
    return after_last - first


def minute_aggregates(source: sqlite3.Connection) -> dict:
    """Input: P2.4 minute table. Output: {(storm_id, orbit_id): minute statistics}."""
    rows = source.execute("""
        SELECT storm_id,orbit_id,COUNT(*),COUNT(sme_nt),COUNT(symh_nt),
               AVG(sme_nt),AVG(symh_nt),
               AVG(CASE WHEN sme_nt IS NOT NULL THEN sme_station_count END),
               MIN(CASE WHEN sme_nt IS NOT NULL THEN sme_station_count END),
               MAX(CASE WHEN sme_nt IS NOT NULL THEN sme_station_count END)
        FROM storm_minute_feature_v3
        GROUP BY storm_id,orbit_id
    """)
    return {(row[0], row[1]): row[2:] for row in rows}


def orbit_rows(source: sqlite3.Connection) -> list[tuple]:
    """Input: P2.4 event orbits and minute statistics. Output: ordered summary rows."""
    aggregate = minute_aggregates(source)
    rows = []
    previous = None
    for storm_id, orbit_id, start_us, end_us in source.execute("""
        SELECT storm_id,orbit_id,orbit_start_time_us,orbit_end_time_us
        FROM storm_event_orbit_v3 ORDER BY storm_id,orbit_start_time_us
    """):
        expected = expected_minute_count(start_us, end_us)
        if expected == 0:
            raise ValueError(f"Orbit has no minute center: {orbit_id}")
        summary = aggregate.get((storm_id, orbit_id), (0, 0, 0, None, None,
                                                        None, None, None))
        total, sme_count, symh_count, q_nt, symh_nt, stations, stations_min, stations_max = summary
        if total > expected or sme_count > total or symh_count > total:
            raise ValueError(f"Invalid minute counts for orbit {orbit_id}.")
        is_valid = int(sme_count * COVERAGE_PARTS >= expected * COVERAGE_REQUIRED_PARTS
                       and symh_count * COVERAGE_PARTS >= expected * COVERAGE_REQUIRED_PARTS)
        midpoint_us = (start_us + end_us) // 2
        rate_nt_h = None
        if (is_valid and previous is not None and previous[0] == storm_id
                and previous[2] and symh_nt is not None):
            elapsed_us = midpoint_us - previous[1]
            if elapsed_us <= 0:
                raise ValueError(f"Non-increasing orbit midpoint: {orbit_id}")
            rate_nt_h = (symh_nt - previous[3]) * HOUR_US / elapsed_us
        rows.append((storm_id, orbit_id, midpoint_us, expected, total,
                     sme_count, symh_count, sme_count / expected, symh_count / expected,
                     q_nt, symh_nt, rate_nt_h, stations, stations_min, stations_max,
                     is_valid, ALGORITHM_VERSION))
        previous = (storm_id, midpoint_us, is_valid, symh_nt)
    return rows


def write_geomag_orbit(source_path: Path = SOURCE_DB, output_path: Path = OUTPUT_DB) -> dict:
    """Input: frozen P2.4 SQLite and new path. Output: compact P2.5 SQLite counts."""
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if output_path.exists():
        raise FileExistsError(output_path)
    source_hash = sha256_file(source_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=output_path.stem + ".", suffix=".building", dir=output_path.parent
    )
    os.close(handle)
    temporary_path = Path(temporary_name)
    try:
        with closing(sqlite3.connect(
            f"file:{source_path.resolve().as_posix()}?mode=ro", uri=True
        )) as source, closing(sqlite3.connect(temporary_path)) as output:
            version = source.execute(
                "SELECT value FROM phase2_metadata WHERE name='p2_4_algorithm_version'"
            ).fetchone()
            if version is None or version[0] != "storm_density_1min_v3":
                raise ValueError("P2.5 requires the current P2.4 checkpoint.")
            summaries = orbit_rows(source)
            with output:
                output.executescript("""
                    CREATE TABLE storm_geomag_orbit_v1 (
                        storm_id TEXT NOT NULL,
                        orbit_id INTEGER NOT NULL,
                        t_mid_time_us INTEGER NOT NULL,
                        expected_minute_count INTEGER NOT NULL,
                        minute_count INTEGER NOT NULL,
                        sme_valid_count INTEGER NOT NULL,
                        symh_valid_count INTEGER NOT NULL,
                        sme_coverage REAL NOT NULL,
                        symh_coverage REAL NOT NULL,
                        q_sme_nt REAL,
                        symh_mean_nt REAL,
                        dsymh_dt_nt_h REAL,
                        sme_station_count_mean REAL,
                        sme_station_count_min INTEGER,
                        sme_station_count_max INTEGER,
                        is_valid INTEGER NOT NULL,
                        algorithm_version TEXT NOT NULL,
                        PRIMARY KEY (storm_id, orbit_id)
                    );
                    CREATE TABLE phase2_metadata (
                        name TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );
                """)
                output.executemany(
                    "INSERT INTO storm_geomag_orbit_v1 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    summaries,
                )
                output.executemany("INSERT INTO phase2_metadata VALUES (?,?)", (
                    ("p2_5_algorithm_version", ALGORITHM_VERSION),
                    ("p2_5_source_sha256", source_hash),
                    ("p2_5_orbit_rows", str(len(summaries))),
                ))
            if output.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("P2.5 SQLite integrity check failed.")
            if len(summaries) != source.execute(
                "SELECT COUNT(*) FROM storm_event_orbit_v3"
            ).fetchone()[0]:
                raise ValueError("P2.5 orbit count differs from P2.4.")
        if sha256_file(source_path) != source_hash or output_path.exists():
            raise ValueError("P2.4 source changed or P2.5 output appeared during build.")
        os.rename(temporary_path, output_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return {"orbit_rows": len(summaries), "valid_orbits": sum(row[-2] for row in summaries)}


def main() -> None:
    """Input: optional P2_4_DB OUTPUT_DB arguments. Output: P2.5 row counts."""
    arguments = sys.argv[1:]
    if len(arguments) not in (0, 2):
        raise SystemExit("Usage: python -m satellite_orbit.phase2.prep_25_geomag_orbit "
                         "[P2_4_DB OUTPUT_DB]")
    paths = tuple(map(Path, arguments)) if arguments else (SOURCE_DB, OUTPUT_DB)
    print(write_geomag_orbit(*paths))


if __name__ == "__main__":
    main()
