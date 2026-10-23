"""Build a versioned minute checkpoint with complete phase-orbit storm windows."""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from satellite_orbit.calculation.density.calc_msis_p2_4 import load_msis_weather
from satellite_orbit.data.geomagnetic.down_supermag_sme import sha256_file
from satellite_orbit.phase2.prep_23_minute_features import (
    EventSources,
    HOUR_US,
    MINUTE_US,
    complete_orbits,
    create_table,
    event_rows,
)


ALGORITHM_VERSION = "storm_minute_feature_v3"
ORBIT_BEFORE = 31
ORBIT_AFTER = 61
ORBIT_COUNT = ORBIT_BEFORE + 1 + ORBIT_AFTER


@dataclass(frozen=True)
class FullOrbitPaths:
    """Input: source and output locations. Output: immutable path record."""

    storms: Path = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_2_v2.sqlite")
    phase1: Path = Path("data/sqlite/swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite")
    gfz_ap: Path = Path("data/geomagnetic/gfz_ap_2023-07-01_2026-06-30.json")
    solar: Path = Path("data/space_weather/SW-All.csv")
    output: Path = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_3_full_orbit_v3.sqlite")


def selected_orbits(source: sqlite3.Connection, t0_us: int) -> list[tuple]:
    """Input: Phase 1 connection and storm t0 us. Output: 93 contiguous orbits."""
    orbits = complete_orbits(source, t0_us - 60 * HOUR_US, t0_us + 110 * HOUR_US)
    anchor = next((index for index, orbit in enumerate(orbits)
                   if orbit[0] <= t0_us < orbit[1]), None)
    if anchor is None or anchor < ORBIT_BEFORE or anchor + ORBIT_AFTER >= len(orbits):
        raise ValueError(f"No complete {ORBIT_COUNT}-orbit window at {t0_us}.")
    window = orbits[anchor - ORBIT_BEFORE:anchor + ORBIT_AFTER + 1]
    # ponytail: The three-year candidates are contiguous; model missing orbits for 12-year runs.
    if any(left[1] != right[0] for left, right in zip(window, window[1:])):
        raise ValueError(f"Phase 1 orbit gap inside storm window at {t0_us}.")
    return window


def merge_orbit_windows(candidates: list[dict]) -> list[dict]:
    """Input: candidate windows. Output: connected overlap groups with unique orbits."""
    groups = []
    for candidate in sorted(candidates, key=lambda row: row["orbits"][0][0]):
        if groups and candidate["orbits"][0][0] < groups[-1][-1]["end_us"]:
            groups[-1].append(candidate)
            groups[-1][-1]["end_us"] = max(
                member["orbits"][-1][1] for member in groups[-1]
            )
        else:
            candidate["end_us"] = candidate["orbits"][-1][1]
            groups.append([candidate])
    merged = []
    for members in groups:
        representative = min(members, key=lambda row: (row["symh_min_nt"], row["t0_us"]))
        unique = {orbit[2]: orbit for member in members for orbit in member["orbits"]}
        orbits = sorted(unique.values(), key=lambda orbit: orbit[0])
        if any(left[1] != right[0] for left, right in zip(orbits, orbits[1:])):
            raise ValueError("Merged storm orbits are not contiguous.")
        merged.append({
            "storm_id": representative["storm_id"],
            "t0_us": representative["t0_us"],
            "symh_min_nt": representative["symh_min_nt"],
            "compound": int(len(members) > 1 or any(row["compound"] for row in members)),
            "n_minima": sum(row["n_minima"] for row in members),
            "source_ids": [row["storm_id"] for row in members],
            "orbits": orbits,
        })
    return merged


def create_event_tables(destination: sqlite3.Connection) -> None:
    """Input: copied P2.2 connection. Output: empty full-orbit event tables."""
    destination.executescript("""
        CREATE TABLE storm_event_full_orbit_v3 (
            storm_id TEXT PRIMARY KEY,
            t0_time_us INTEGER NOT NULL,
            symh_min_nt INTEGER NOT NULL,
            window_start_time_us INTEGER NOT NULL,
            window_end_time_us INTEGER NOT NULL,
            compound INTEGER NOT NULL,
            n_minima INTEGER NOT NULL,
            n_orbits INTEGER NOT NULL,
            source_storm_ids_json TEXT NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE storm_event_orbit_v3 (
            storm_id TEXT NOT NULL REFERENCES storm_event_full_orbit_v3(storm_id),
            orbit_id INTEGER NOT NULL,
            orbit_index INTEGER NOT NULL,
            orbit_start_time_us INTEGER NOT NULL,
            orbit_end_time_us INTEGER NOT NULL,
            phase_weighted_mean_semi_major_axis_m REAL NOT NULL,
            chunk_id INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id, orbit_id),
            UNIQUE (orbit_id)
        );
    """)


def insert_events(destination: sqlite3.Connection, events: list[dict]) -> None:
    """Input: copied P2.2 and merged windows. Output: persisted event/orbit rows."""
    destination.executemany(
        "INSERT INTO storm_event_full_orbit_v3 VALUES (?,?,?,?,?,?,?,?,?,?)",
        ((event["storm_id"], event["t0_us"], event["symh_min_nt"],
          event["orbits"][0][0], event["orbits"][-1][1], event["compound"],
          event["n_minima"], len(event["orbits"]), json.dumps(event["source_ids"]),
          ALGORITHM_VERSION) for event in events),
    )
    destination.executemany(
        "INSERT INTO storm_event_orbit_v3 VALUES (?,?,?,?,?,?,?,?)",
        ((event["storm_id"], orbit[2], index, orbit[0], orbit[1], orbit[3],
          orbit[4], ALGORITHM_VERSION)
         for event in events for index, orbit in enumerate(event["orbits"])),
    )


def build_minute_rows(destination: sqlite3.Connection, inputs: EventSources,
                      events: list[dict]) -> int:
    """Input: event windows and source connections. Output: inserted minute count."""
    columns = len(destination.execute("PRAGMA table_info(storm_minute_feature_v3)").fetchall())
    statement = "INSERT INTO storm_minute_feature_v3 VALUES (" + ",".join("?" * columns) + ")"
    expected = 0
    for event in events:
        start_us = (event["orbits"][0][0] + MINUTE_US - 1) // MINUTE_US * MINUTE_US
        end_us = (event["orbits"][-1][1] + MINUTE_US - 1) // MINUTE_US * MINUTE_US
        window = (event["storm_id"], event["t0_us"], start_us, end_us)
        destination.executemany(statement, event_rows(window, inputs, ALGORITHM_VERSION))
        expected += (end_us - start_us) // MINUTE_US
    return expected


def verify_checkpoint(destination: sqlite3.Connection, expected: int,
                      events: list[dict]) -> dict:
    """Input: completed SQLite and expected counts. Output: checked row counts."""
    minutes, linked, n_events = destination.execute(
        "SELECT count(*), sum(orbit_id IS NOT NULL), count(DISTINCT storm_id) "
        "FROM storm_minute_feature_v3"
    ).fetchone()
    orbit_count = destination.execute("SELECT count(*) FROM storm_event_orbit_v3").fetchone()[0]
    if minutes != expected or n_events != len(events) or linked != minutes:
        raise ValueError("Full-orbit minute rows are missing or unlinked.")
    if orbit_count != sum(len(event["orbits"]) for event in events):
        raise ValueError("Full-orbit event membership differs from source windows.")
    if destination.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("Full-orbit checkpoint has broken foreign keys.")
    if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("Full-orbit checkpoint failed SQLite integrity check.")
    return {"minute_rows": minutes, "orbit_rows": orbit_count, "storms": n_events}


def write_full_orbit_minutes(paths: FullOrbitPaths = FullOrbitPaths()) -> dict:
    """Input: frozen P2.2/Phase 1/weather files. Output: new checked P2.3 SQLite."""
    if paths.output.exists():
        raise FileExistsError(paths.output)
    source_paths = {name: getattr(paths, name) for name in ("storms", "phase1", "gfz_ap", "solar")}
    for source_path in source_paths.values():
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
    hashes = {name: sha256_file(path) for name, path in source_paths.items()}
    weather = load_msis_weather(paths.gfz_ap, paths.solar)
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=paths.output.stem + ".", suffix=".building", dir=paths.output.parent
    )
    os.close(handle)
    temporary_path = Path(temporary_name)
    try:
        shutil.copyfile(paths.storms, temporary_path)
        if sha256_file(temporary_path) != hashes["storms"]:
            raise ValueError("P2.2 changed during copy.")
        with closing(sqlite3.connect(temporary_path)) as destination, closing(
            sqlite3.connect(f"file:{paths.phase1.resolve().as_posix()}?mode=ro", uri=True)
        ) as phase1:
            destination.execute("PRAGMA foreign_keys = ON")
            phase1.row_factory = sqlite3.Row
            rows = destination.execute(
                "SELECT storm_id,t0_time_us,symh_min_nt,compound,n_minima "
                "FROM storm_event_v2 ORDER BY t0_time_us"
            ).fetchall()
            candidates = [
                {"storm_id": row[0], "t0_us": row[1], "symh_min_nt": row[2],
                 "compound": row[3], "n_minima": row[4],
                 "orbits": selected_orbits(phase1, row[1])}
                for row in rows
            ]
            events = merge_orbit_windows(candidates)
            inputs = EventSources(phase1, destination, weather)
            with destination:
                create_event_tables(destination)
                insert_events(destination, events)
                create_table(destination, "storm_minute_feature_v3", "storm_event_full_orbit_v3")
                expected = build_minute_rows(destination, inputs, events)
                destination.executemany(
                    "INSERT INTO phase2_metadata VALUES (?,?)",
                    (("p2_3_full_orbit_version", ALGORITHM_VERSION),
                     ("p2_3_full_orbit_before", str(ORBIT_BEFORE)),
                     ("p2_3_full_orbit_after", str(ORBIT_AFTER)),
                     ("p2_3_full_orbit_p2_2_sha256", hashes["storms"]),
                     ("p2_3_full_orbit_phase1_sha256", hashes["phase1"]),
                     ("p2_3_full_orbit_gfz_sha256", hashes["gfz_ap"]),
                     ("p2_3_full_orbit_solar_sha256", hashes["solar"])),
                )
            result = verify_checkpoint(destination, expected, events)
        if any(sha256_file(path) != hashes[name] for name, path in source_paths.items()):
            raise ValueError("Full-orbit input changed during build.")
        if paths.output.exists():
            raise FileExistsError(paths.output)
        os.rename(temporary_path, paths.output)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return result


def main() -> None:
    """Input: optional P2_2_DB PHASE1_DB GFZ_JSON SOLAR_CSV OUTPUT_DB. Output: counts."""
    arguments = sys.argv[1:]
    if len(arguments) not in (0, 5):
        raise SystemExit("Usage: python -m satellite_orbit.phase2.prep_23_full_orbit "
                         "[P2_2_DB PHASE1_DB GFZ_JSON SOLAR_CSV OUTPUT_DB]")
    paths = FullOrbitPaths(*map(Path, arguments)) if arguments else FullOrbitPaths()
    print(write_full_orbit_minutes(paths))


if __name__ == "__main__":
    main()
