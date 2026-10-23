"""Copy P2.2 and join minute geomagnetic data to Phase 1 orbit data."""

import math
import os
import shutil
import sqlite3
import sys
import tempfile
from bisect import bisect_left, bisect_right
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from satellite_orbit.calculation.density.calc_msis_p2_4 import (
    load_msis_weather,
    sample_drivers,
)
from satellite_orbit.data.geomagnetic.down_supermag_sme import sha256_file
from satellite_orbit.phase2.prep_22_storm_event import ALGORITHM_VERSION as INPUT_VERSION


ALGORITHM_VERSION = "storm_minute_feature_v2"
MINUTE_US = 60_000_000
HALF_MINUTE_US = MINUTE_US // 2
SECOND_US = 1_000_000
HOUR_US = 3_600_000_000
MAX_PHASE_GAP_US = 20 * SECOND_US
TWO_PI = math.tau


@dataclass(frozen=True)
class MinuteFeaturePaths:
    """Input: P2.2, Phase 1, weather, and output paths. Output: path record."""

    storms: Path = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_2_v2.sqlite")
    phase1: Path = Path("data/sqlite/swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite")
    gfz_ap: Path = Path("data/geomagnetic/gfz_ap_2023-07-01_2026-06-30.json")
    solar: Path = Path("data/space_weather/SW-All.csv")
    output: Path = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_3_minute_v2.sqlite")


@dataclass(frozen=True)
class EventSources:
    """Input: source connections and weather map. Output: event input record."""

    phase1: sqlite3.Connection
    storms: sqlite3.Connection
    weather: dict


DECAY_FIELDS = (
    "raw_3", "raw_5", "joint_3", "joint_5",
)


def source_rows(connection: sqlite3.Connection, start_us: int, end_us: int) -> list[sqlite3.Row]:
    """Input: Phase 1 connection and UTC bounds. Output: ordered 10-s source rows."""
    return connection.execute(
        "SELECT mean.time_us, quality.is_usable, quality.chunk_id, "
        "mean.mean_semi_major_axis_m, mean.mean_argument_of_perigee_rad, "
        "mean.mean_anomaly_rad, "
        "raw.orbit_3_decay_rate_m_s AS raw_3_rate, "
        "raw.orbit_3_decay_rate_1sigma_m_s AS raw_3_sigma, "
        "raw.orbit_3_sample_count AS raw_3_count, "
        "raw.orbit_3_reject_reason AS raw_3_reject, "
        "raw.orbit_5_decay_rate_m_s AS raw_5_rate, "
        "raw.orbit_5_decay_rate_1sigma_m_s AS raw_5_sigma, "
        "raw.orbit_5_sample_count AS raw_5_count, "
        "raw.orbit_5_reject_reason AS raw_5_reject, "
        "joint.orbit_3_decay_rate_m_s AS joint_3_rate, "
        "joint.orbit_3_decay_rate_1sigma_m_s AS joint_3_sigma, "
        "joint.orbit_3_sample_count AS joint_3_count, "
        "joint.orbit_3_reject_reason AS joint_3_reject, "
        "joint.orbit_5_decay_rate_m_s AS joint_5_rate, "
        "joint.orbit_5_decay_rate_1sigma_m_s AS joint_5_sigma, "
        "joint.orbit_5_sample_count AS joint_5_count, "
        "joint.orbit_5_reject_reason AS joint_5_reject "
        "FROM swarm_a_mean_orbit_elements_v1 AS mean "
        "JOIN swarm_a_pod_quality AS quality ON quality.time_us = mean.time_us "
        "LEFT JOIN swarm_a_phase_harmonic_decay_raw_b_l_sets_v2 AS raw "
        "ON raw.time_us = mean.time_us "
        "LEFT JOIN swarm_a_phase_harmonic_decay_joint_h2_h3_sets_v2 AS joint "
        "ON joint.time_us = mean.time_us "
        "WHERE mean.time_us >= ? AND mean.time_us <= ? ORDER BY mean.time_us",
        (start_us, end_us),
    ).fetchall()


def phase_at_time(rows: list[sqlite3.Row], times: list[int], time_us: int) -> dict:
    """Input: 10-s rows, epochs, UTC target. Output: local mean orbit and causal rates."""
    index = bisect_left(times, time_us)
    if index == len(rows):
        return {"status": "no_source"}
    right = rows[index]
    left = right if right["time_us"] == time_us else rows[index - 1] if index else None
    if left is None:
        return {"status": "no_source"}
    if (right["time_us"] - left["time_us"] > MAX_PHASE_GAP_US
            or left["chunk_id"] != right["chunk_id"]):
        return {"status": "gap_or_chunk"}
    if any(row["is_usable"] != 1 or row["chunk_id"] is None or
           row["mean_semi_major_axis_m"] is None or
           row["mean_argument_of_perigee_rad"] is None or
           row["mean_anomaly_rad"] is None for row in (left, right)):
        return {"status": "invalid_source"}
    fraction = (time_us - left["time_us"]) / (right["time_us"] - left["time_us"]) \
        if right["time_us"] != left["time_us"] else 0.0
    left_u = (left["mean_argument_of_perigee_rad"] + left["mean_anomaly_rad"]) % TWO_PI
    right_u = (right["mean_argument_of_perigee_rad"] + right["mean_anomaly_rad"]) % TWO_PI
    phase_step = (right_u - left_u + math.pi) % TWO_PI - math.pi
    decay = tuple(left[f"{field}_{suffix}"] for field in DECAY_FIELDS
                  for suffix in ("rate", "sigma", "count", "reject"))
    return {
        "status": "exact" if left["time_us"] == right["time_us"] else "interpolated",
        "a_m": left["mean_semi_major_axis_m"] + fraction *
        (right["mean_semi_major_axis_m"] - left["mean_semi_major_axis_m"]),
        "u_rad": (left_u + fraction * phase_step) % TWO_PI,
        "left_us": left["time_us"],
        "right_us": right["time_us"],
        "chunk_id": left["chunk_id"],
        "decay": decay,
    }


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


def complete_orbits(source: sqlite3.Connection, start_us: int, end_us: int) -> list[tuple]:
    """Input: Phase 1 source and UTC bounds. Output: complete phase-orbit records."""
    padding_us = 2 * HOUR_US
    orbits = source.execute(
        "SELECT time_us, orbit_start_time_us, phase_weighted_mean_semi_major_axis_m, "
        "chunk_id FROM swarm_a_phase_orbit_mean_v2 "
        "WHERE orbit_start_time_us >= ? AND orbit_start_time_us < ? "
        "ORDER BY orbit_start_time_us",
        (start_us - padding_us, end_us + padding_us),
    ).fetchall()
    boundaries = [crossing_time_us(source, orbit[1], orbit[3]) for orbit in orbits]
    complete = []
    for index, orbit in enumerate(orbits[:-1]):
        next_orbit = orbits[index + 1]
        start, stop = boundaries[index:index + 2]
        if (start is not None and stop is not None and orbit[3] == next_orbit[3]
                and next_orbit[1] - orbit[0] == 10 * SECOND_US):
            complete.append((start, stop, orbit[0], orbit[2], orbit[3]))
    return complete


def orbit_at_time(orbits: list[tuple], starts: list[int], time_us: int) -> tuple:
    """Input: complete orbits, starts, UTC target. Output: orbit ID and retrospective mean."""
    index = bisect_right(starts, time_us) - 1
    if index < 0 or time_us >= orbits[index][1]:
        return (None, None, None, None, None)
    return orbits[index]


def event_rows(event: tuple, inputs: EventSources, version: str = ALGORITHM_VERSION):
    """Input: event and source connections. Output: one feature row per UTC minute."""
    storm_id, t0_us, start_us, end_us = event
    samples = source_rows(inputs.phase1, start_us - MAX_PHASE_GAP_US,
                          end_us + MAX_PHASE_GAP_US)
    times = [sample["time_us"] for sample in samples]
    orbits = complete_orbits(inputs.phase1, start_us, end_us)
    orbit_starts = [orbit[0] for orbit in orbits]
    geomag = iter(inputs.storms.execute(
        "SELECT time_us, sme_nt, symh_nt, sme_station_count, "
        "sme_not_before_time_us, kyoto_not_before_time_us "
        "FROM geomag_1min_v2 WHERE time_us >= ? AND time_us < ? ORDER BY time_us",
        (start_us, end_us),
    ))
    for source_time_us in range(start_us, end_us, MINUTE_US):
        minute = next(geomag, None)
        if minute is None or minute[0] != source_time_us:
            raise ValueError(f"Missing geomagnetic minute: {storm_id}:{source_time_us}")
        target_us = source_time_us
        phase = phase_at_time(samples, times, target_us)
        orbit = orbit_at_time(orbits, orbit_starts, target_us)
        if orbit[4] is not None and phase.get("chunk_id") != orbit[4]:
            orbit = (None, None, None, None, None)
        weather = sample_drivers(source_time_us, inputs.weather)
        phase_ready_us = phase.get("right_us")
        core_ready_us = max(minute[4], minute[5], phase_ready_us or source_time_us)
        yield (
            storm_id, source_time_us, source_time_us - HALF_MINUTE_US,
            source_time_us + HALF_MINUTE_US, target_us,
            minute[1], minute[2], minute[3], minute[4], minute[5],
            phase.get("a_m"), phase.get("u_rad"), phase.get("left_us"),
            phase_ready_us, phase.get("chunk_id"), phase["status"],
            orbit[2], orbit[0], orbit[1], orbit[3], orbit[2],
            phase.get("left_us") if phase.get("decay") is not None else None,
            *(phase.get("decay") or (None,) * 16),
            weather["ap_values"][1] if weather else None,
            weather["ap_last_slot_end_time_us"] if weather else None,
            weather["f107_sfu"] if weather else None,
            weather["f107a_sfu"] if weather else None,
            (source_time_us - t0_us) / HOUR_US, core_ready_us, version,
        )


def create_table(destination: sqlite3.Connection, table_name: str = "storm_minute_feature_v2",
                 event_table: str = "storm_event_v2") -> None:
    """Input: copied P2.2 SQLite. Output: empty derived minute-feature table."""
    if (table_name, event_table) not in {
        ("storm_minute_feature_v2", "storm_event_v2"),
        ("storm_minute_feature_v3", "storm_event_full_orbit_v3"),
    }:
        raise ValueError("Unsupported minute-feature table pair.")
    rate_columns = ",\n".join(
        f"{field}_rate_m_s REAL, {field}_sigma_m_s REAL, "
        f"{field}_sample_count INTEGER, {field}_reject_reason TEXT"
        for field in DECAY_FIELDS
    )
    destination.execute(f"""
        CREATE TABLE {table_name} (
            storm_id TEXT NOT NULL REFERENCES {event_table}(storm_id),
            source_time_us INTEGER NOT NULL,
            assumed_support_start_time_us INTEGER NOT NULL,
            assumed_support_end_time_us INTEGER NOT NULL,
            target_time_us INTEGER NOT NULL,
            sme_nt REAL,
            symh_nt REAL,
            sme_station_count INTEGER,
            sme_not_before_time_us INTEGER NOT NULL,
            kyoto_not_before_time_us INTEGER NOT NULL,
            mean_semi_major_axis_m REAL,
            orbit_phase_u_rad REAL,
            phase_left_time_us INTEGER,
            phase_right_time_us INTEGER,
            chunk_id INTEGER,
            phase_status TEXT NOT NULL,
            orbit_id INTEGER,
            orbit_start_time_us INTEGER,
            orbit_end_time_us INTEGER,
            phase_weighted_orbit_mean_a_m REAL,
            orbit_mean_source_end_time_us INTEGER,
            decay_source_time_us INTEGER,
            {rate_columns},
            ap_step REAL,
            ap_source_end_time_us INTEGER,
            f107_sfu REAL,
            f107a_sfu REAL,
            t_rel_h REAL NOT NULL,
            core_ready_time_us INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id, source_time_us),
            CHECK (assumed_support_start_time_us = source_time_us - {HALF_MINUTE_US}),
            CHECK (assumed_support_end_time_us = source_time_us + {HALF_MINUTE_US}),
            CHECK (target_time_us = source_time_us),
            CHECK (decay_source_time_us IS NULL OR decay_source_time_us <= target_time_us),
            CHECK (ap_source_end_time_us IS NULL OR ap_source_end_time_us <= source_time_us)
        )
    """)


def write_minute_features(paths: MinuteFeaturePaths = MinuteFeaturePaths()) -> dict:
    """Input: frozen P2.2, Phase 1, weather, new path. Output: checked minute counts."""
    if paths.output.exists():
        raise FileExistsError(paths.output)
    for input_path in (paths.storms, paths.phase1, paths.gfz_ap, paths.solar):
        if not input_path.is_file():
            raise FileNotFoundError(input_path)
    hashes = {name: sha256_file(getattr(paths, name))
              for name in ("storms", "phase1", "gfz_ap", "solar")}
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
            version = destination.execute(
                "SELECT value FROM phase2_metadata WHERE name = 'p2_2_algorithm_version'"
            ).fetchone()
            if version != (INPUT_VERSION,):
                raise ValueError("Input is not the P2.2 storm checkpoint.")
            events = destination.execute(
                "SELECT storm_id, t0_time_us, window_start_time_us, window_end_time_us "
                "FROM storm_event_v2 ORDER BY window_start_time_us"
            ).fetchall()
            if not events:
                raise ValueError("P2.2 has no storm events.")
            expected = sum((event[3] - event[2]) // MINUTE_US for event in events)
            inputs = EventSources(phase1, destination, weather)
            with destination:
                create_table(destination)
                columns = len(destination.execute(
                    "PRAGMA table_info(storm_minute_feature_v2)"
                ).fetchall())
                statement = ("INSERT INTO storm_minute_feature_v2 VALUES (" +
                             ",".join("?" * columns) + ")")
                for event in events:
                    destination.executemany(statement, event_rows(event, inputs))
                destination.executemany(
                    "INSERT INTO phase2_metadata VALUES (?, ?)",
                    (("p2_2_sha256", hashes["storms"]),
                     ("p2_3_algorithm_version", ALGORITHM_VERSION),
                     ("p2_3_sme_time_semantics", "assumed_centered_1min_unverified"),
                     ("p2_3_kyoto_time_semantics", "centered_1min_official"),
                     ("p2_3_phase1_file", paths.phase1.name),
                     ("p2_3_phase1_sha256", hashes["phase1"]),
                     ("p2_3_gfz_sha256", hashes["gfz_ap"]),
                     ("p2_3_solar_sha256", hashes["solar"])),
                )
            count, phase_ok, orbit_ok, storms = destination.execute(
                "SELECT count(*), sum(orbit_phase_u_rad IS NOT NULL), "
                "sum(orbit_id IS NOT NULL), count(DISTINCT storm_id) "
                "FROM storm_minute_feature_v2"
            ).fetchone()
            if (count != expected or storms != len(events)
                    or destination.execute("PRAGMA foreign_key_check").fetchone() is not None
                    or destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok"):
                raise ValueError("P2.3 minute output failed validation.")
        if (any(sha256_file(getattr(paths, name)) != digest for name, digest in hashes.items())
                or paths.output.exists()):
            raise ValueError("P2.3 input changed or output appeared during build.")
        os.rename(temporary_path, paths.output)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return {"minute_rows": count, "phase_rows": phase_ok,
            "orbit_link_rows": orbit_ok, "storms": storms}


def main() -> None:
    """Input: optional P2_2_DB PHASE1_DB GFZ_JSON SOLAR_CSV OUTPUT_DB. Output: counts."""
    arguments = sys.argv[1:]
    if len(arguments) not in (0, 5):
        raise SystemExit("Usage: python -m satellite_orbit.phase2.prep_23_minute_features "
                         "[P2_2_DB PHASE1_DB GFZ_JSON SOLAR_CSV OUTPUT_DB]")
    paths = MinuteFeaturePaths(*map(Path, arguments)) if arguments else MinuteFeaturePaths()
    print(write_minute_features(paths))


if __name__ == "__main__":
    main()
