"""Build storm features on complete Phase 1 phase orbits."""

import math
import os
import shutil
import sqlite3
import sys
import tempfile
from bisect import bisect_left
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from satellite_orbit.calculation.density.calc_msis_p2_4 import (
    load_msis_weather,
    sample_drivers,
)
from satellite_orbit.data.geomagnetic.down_supermag_sme import sha256_file
from satellite_orbit.phase2.prep_22_storm_event import ALGORITHM_VERSION as INPUT_VERSION


ALGORITHM_VERSION = "storm_orbit_sme_v1"
MINUTE_US = 60_000_000
SECOND_US = 1_000_000
HOUR_US = 3_600_000_000
TWO_PI = 2 * math.pi
MAX_SHORT_GAP_MINUTES = 10
MIN_VALID_FRACTION = 0.8


@dataclass(frozen=True)
class OrbitFeaturePaths:
    """Input: P2.2, Phase 1, weather, output paths. Output: path record."""

    storms: Path = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_2_v2.sqlite")
    phase1: Path = Path("data/sqlite/swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite")
    gfz_ap: Path = Path("data/geomagnetic/gfz_ap_2023-07-01_2026-06-30.json")
    solar: Path = Path("data/space_weather/SW-All.csv")
    output: Path = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_3_orbit_v1.sqlite")


@dataclass(frozen=True)
class EventSources:
    """Input: Phase 1, P2.2, and weather. Output: event-processing inputs."""

    phase1: sqlite3.Connection
    storms: sqlite3.Connection
    weather: dict


def crossing_time_us(source: sqlite3.Connection, orbit_start_us: int, chunk_id: int) -> int | None:
    """Input: Phase 1 source, first POD epoch, chunk. Output: interpolated u=0 UTC us."""
    rows = source.execute(
        "SELECT mean.time_us, quality.chunk_id, "
        "mean.mean_argument_of_perigee_rad, mean.mean_anomaly_rad "
        "FROM swarm_a_mean_orbit_elements_v1 AS mean "
        "JOIN swarm_a_pod_quality AS quality ON quality.time_us = mean.time_us "
        "WHERE mean.time_us <= ? ORDER BY mean.time_us DESC LIMIT 2",
        (orbit_start_us,),
    ).fetchall()
    if len(rows) != 2:
        return None
    after, before = rows
    if (after[0] != orbit_start_us or after[1] != chunk_id or before[1] != chunk_id
            or after[0] - before[0] != 10 * SECOND_US):
        return None
    phase_before = (before[2] + before[3]) % TWO_PI
    phase_after = (after[2] + after[3]) % TWO_PI
    if not (phase_before > math.pi and phase_after < math.pi):
        return None
    fraction = (TWO_PI - phase_before) / (TWO_PI - phase_before + phase_after)
    return round(before[0] + fraction * (after[0] - before[0]))


def fill_short_gaps(rows: list[list], column: int) -> None:
    """Input: ordered minute rows and value column. Output: short interior gaps filled in place."""
    index = 0
    while index < len(rows):
        if rows[index][column] is not None:
            index += 1
            continue
        start = index
        while index < len(rows) and rows[index][column] is None:
            index += 1
        if (start == 0 or index == len(rows) or index - start > MAX_SHORT_GAP_MINUTES
                or rows[index][0] - rows[start - 1][0] != (index - start + 1) * MINUTE_US):
            continue
        left = rows[start - 1][column]
        right = rows[index][column]
        for offset in range(index - start):
            rows[start + offset][column] = left + (right - left) * (offset + 1) / (index - start + 1)


def orbit_means(minutes: list[list], start_index: int, stop_index: int) -> tuple:
    """Input: minute rows and orbit slice. Output: Q, SYM-H, stations, counts, valid flag."""
    selected = minutes[start_index:stop_index]
    sme = [row[1] for row in selected if row[1] is not None]
    symh = [row[2] for row in selected if row[2] is not None]
    stations = [row[3] for row in selected if row[3] > 0]
    total = len(selected)
    valid = total > 0 and len(sme) / total >= MIN_VALID_FRACTION and len(symh) / total >= MIN_VALID_FRACTION
    return (
        sum(sme) / len(sme) if sme else None,
        sum(symh) / len(symh) if symh else None,
        sum(stations) / len(stations) if stations else None,
        total, len(sme), len(symh), int(valid),
    )


def event_rows(event: tuple, inputs: EventSources):
    """Input: storm event and source connections. Output: orbit feature rows."""
    storm_id, t0_us, window_start_us, window_end_us = event
    padding_us = 2 * HOUR_US
    orbits = inputs.phase1.execute(
        "SELECT time_us, orbit_start_time_us, phase_weighted_mean_semi_major_axis_m, "
        "chunk_id FROM swarm_a_phase_orbit_mean_v2 "
        "WHERE orbit_start_time_us >= ? AND orbit_start_time_us < ? "
        "ORDER BY orbit_start_time_us",
        (window_start_us - padding_us, window_end_us + padding_us),
    ).fetchall()
    boundaries = [crossing_time_us(inputs.phase1, orbit[1], orbit[3]) for orbit in orbits]
    minutes = [list(row) for row in inputs.storms.execute(
        "SELECT time_us, sme_nt, symh_nt, sme_station_count "
        "FROM geomag_1min_v2 WHERE time_us >= ? AND time_us < ? ORDER BY time_us",
        (window_start_us - padding_us, window_end_us + padding_us),
    )]
    fill_short_gaps(minutes, 1)
    fill_short_gaps(minutes, 2)
    minute_times = [row[0] for row in minutes]
    previous = None
    for index, orbit in enumerate(orbits[:-1]):
        next_orbit = orbits[index + 1]
        start_us, end_us = boundaries[index:index + 2]
        if (start_us is None or end_us is None or orbit[3] != next_orbit[3]
                or next_orbit[1] - orbit[0] != 10 * SECOND_US):
            previous = None
            continue
        mid_us = (start_us + end_us) // 2
        first = bisect_left(minute_times, start_us)
        last = bisect_left(minute_times, end_us)
        q, symh, station_mean, total, n_sme, n_symh, valid = orbit_means(minutes, first, last)
        dsymh = None
        if previous is not None and symh is not None and previous[1] is not None:
            dsymh = (symh - previous[1]) / ((mid_us - previous[0]) / HOUR_US)
        previous = (mid_us, symh)
        if not window_start_us <= mid_us < window_end_us:
            continue
        drivers = sample_drivers(mid_us, inputs.weather)
        yield (
            storm_id, orbit[0], orbit[1], start_us, end_us, mid_us, orbit[2],
            q, symh, dsymh, station_mean, total, n_sme, n_symh, valid,
            drivers["ap_values"][1] if drivers else None,
            drivers["ap_last_slot_end_time_us"] if drivers else None,
            drivers["f107_sfu"] if drivers else None,
            drivers["f107a_sfu"] if drivers else None,
            (mid_us - t0_us) / HOUR_US, orbit[3], ALGORITHM_VERSION,
        )


def create_table(destination: sqlite3.Connection) -> None:
    """Input: copied P2.2 SQLite. Output: empty per-orbit feature table."""
    destination.execute(
        """
        CREATE TABLE storm_orbit_feature_v1 (
            storm_id TEXT NOT NULL REFERENCES storm_event_v2(storm_id),
            orbit_id INTEGER NOT NULL,
            source_orbit_start_time_us INTEGER NOT NULL,
            start_time_us INTEGER NOT NULL,
            end_time_us INTEGER NOT NULL,
            t_mid_time_us INTEGER NOT NULL,
            a_mean_m REAL NOT NULL,
            q_sme_nt REAL,
            symh_nt REAL,
            dsymh_dt_nt_h REAL,
            sme_station_count_mean REAL,
            minute_count INTEGER NOT NULL,
            sme_valid_minutes INTEGER NOT NULL,
            symh_valid_minutes INTEGER NOT NULL,
            is_valid INTEGER NOT NULL CHECK (is_valid IN (0, 1)),
            ap_step REAL,
            ap_source_end_time_us INTEGER,
            f107_sfu REAL,
            f107a_sfu REAL,
            t_rel_h REAL NOT NULL,
            chunk_id INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id, orbit_id),
            CHECK (start_time_us < t_mid_time_us AND t_mid_time_us < end_time_us),
            CHECK (ap_source_end_time_us IS NULL OR ap_source_end_time_us <= t_mid_time_us)
        )
        """
    )


def write_orbit_features(paths: OrbitFeaturePaths = OrbitFeaturePaths()) -> dict:
    """Input: frozen P2.2, Phase 1, weather, new path. Output: verified orbit counts."""
    if paths.output.exists():
        raise FileExistsError(paths.output)
    for input_path in (paths.storms, paths.phase1, paths.gfz_ap, paths.solar):
        if not input_path.is_file():
            raise FileNotFoundError(input_path)
    storm_hash = sha256_file(paths.storms)
    phase1_hash = sha256_file(paths.phase1)
    gfz_hash = sha256_file(paths.gfz_ap)
    solar_hash = sha256_file(paths.solar)
    weather = load_msis_weather(paths.gfz_ap, paths.solar)
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=paths.output.stem + ".", suffix=".building", dir=paths.output.parent
    )
    os.close(handle)
    temporary_path = Path(temporary_name)
    try:
        shutil.copyfile(paths.storms, temporary_path)
        if sha256_file(temporary_path) != storm_hash:
            raise ValueError("P2.2 changed during copy.")
        with closing(sqlite3.connect(temporary_path)) as destination, closing(
            sqlite3.connect(f"file:{paths.phase1.resolve().as_posix()}?mode=ro", uri=True)
        ) as source:
            destination.execute("PRAGMA foreign_keys = ON")
            version = destination.execute(
                "SELECT value FROM phase2_metadata WHERE name = 'p2_2_algorithm_version'"
            ).fetchone()
            if version != (INPUT_VERSION,):
                raise ValueError("Input is not the P2.2 storm checkpoint.")
            events = destination.execute(
                "SELECT storm_id, t0_time_us, window_start_time_us, window_end_time_us "
                "FROM storm_event_v2 ORDER BY window_start_time_us"
            ).fetchall()
            inputs = EventSources(source, destination, weather)
            with destination:
                create_table(destination)
                for event in events:
                    destination.executemany(
                        "INSERT INTO storm_orbit_feature_v1 VALUES (" + ",".join("?" * 22) + ")",
                        event_rows(event, inputs),
                    )
                destination.executemany(
                    "INSERT INTO phase2_metadata VALUES (?, ?)",
                    (("p2_2_sha256", storm_hash),
                     ("p2_3_orbit_algorithm_version", ALGORITHM_VERSION),
                     ("p2_3_phase1_file", paths.phase1.name),
                     ("p2_3_phase1_sha256", phase1_hash),
                     ("p2_3_gfz_sha256", gfz_hash),
                     ("p2_3_solar_sha256", solar_hash)),
                )
            count, valid, storms = destination.execute(
                "SELECT count(*), sum(is_valid), count(DISTINCT storm_id) "
                "FROM storm_orbit_feature_v1"
            ).fetchone()
            if (count == 0 or storms != len(events)
                    or destination.execute("PRAGMA foreign_key_check").fetchone() is not None
                    or destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok"):
                raise ValueError("P2.3 per-orbit output failed validation.")
        if (sha256_file(paths.storms) != storm_hash
                or sha256_file(paths.phase1) != phase1_hash
                or sha256_file(paths.gfz_ap) != gfz_hash
                or sha256_file(paths.solar) != solar_hash
                or paths.output.exists()):
            raise ValueError("P2.3 input changed or output appeared during build.")
        os.rename(temporary_path, paths.output)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return {"orbit_rows": count, "valid_orbits": valid, "storms": storms}


def main() -> None:
    """Input: optional P2_2_DB PHASE1_DB GFZ_JSON SOLAR_CSV OUTPUT_DB. Output: counts."""
    arguments = sys.argv[1:]
    if len(arguments) not in (0, 5):
        raise SystemExit("Usage: python -m satellite_orbit.phase2.prep_23_orbit_features "
                         "[P2_2_DB PHASE1_DB GFZ_JSON SOLAR_CSV OUTPUT_DB]")
    print(write_orbit_features(OrbitFeaturePaths(*map(Path, arguments)) if arguments else OrbitFeaturePaths()))


if __name__ == "__main__":
    main()
