"""Apply the fixed P6.1 B_eff to Phase 4 minute density."""

import math
import os
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from phases.phase6.code.calc_phase6_1_beff import (
    EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
    MINUTE_S,
    MINUTE_US,
    read_only,
)


ALGORITHM_VERSION = "phase6_2_fixed_beff_phase4_decay_v1"


@dataclass(frozen=True)
class Phase4Paths:
    """Input: Phase 4, P6.1 pairs/B_eff, and output paths. Output: immutable P6.2 paths."""

    phase4: Path = Path(
        "phases/phase4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite",
    )
    minute_pairs: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_1_l2_minute_pairs_v1.sqlite",
    )
    beff: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_1_beff_v1.sqlite",
    )
    output: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_2_phase4_decay_v1.sqlite",
    )


@dataclass(frozen=True)
class DensityValue:
    """Input: semi-major axis m and density kg/m^3. Output: one kernel endpoint."""

    semi_major_axis_m: float
    density_kg_m3: float


@dataclass(frozen=True)
class JoinedMinute:
    """Input: exact Phase 4/P6.1 minute join. Output: one P6.2 integration row."""

    storm_id: str
    time_us: int
    chunk_id: int
    semi_major_axis_m: float
    l2_phase_density_kg_m3: float
    phase4_density_kg_m3: float


def kernel_increment(previous: DensityValue, current: DensityValue) -> float:
    """Input: two consecutive density endpoints. Output: 60-second kernel kg/m."""
    previous_value = previous.density_kg_m3 * math.sqrt(
        EARTH_GRAVITATIONAL_PARAMETER_M3_S2 * previous.semi_major_axis_m,
    )
    current_value = current.density_kg_m3 * math.sqrt(
        EARTH_GRAVITATIONAL_PARAMETER_M3_S2 * current.semi_major_axis_m,
    )
    return 0.5 * (previous_value + current_value) * MINUTE_S


def load_beff(connection: sqlite3.Connection) -> float:
    """Input: P6.1 fit SQLite. Output: the single positive global B_eff m^2/kg."""
    rows = connection.execute(
        "SELECT beta_eff_m2_kg FROM phase6_1_beff_fit_v1",
    ).fetchall()
    if len(rows) != 1 or float(rows[0][0]) <= 0.0:
        raise ValueError("P6.2 requires exactly one positive P6.1 B_eff.")
    return float(rows[0][0])


def load_joined_minutes(
    phase4: sqlite3.Connection,
    minute_pairs_path: Path,
):
    """Input: Phase 4 and P6.1 pair SQLite. Output: exact joined minute iterator."""
    phase4.execute(
        "ATTACH DATABASE ? AS p6",
        (f"file:{minute_pairs_path.resolve().as_posix()}?mode=ro",),
    )
    rows = phase4.execute("""
        SELECT d.storm_id,d.time_us,p.chunk_id,p.mean_semi_major_axis_m,
               d.rho_l2_phase_kg_m3,d.rho_trial4_joint_phase_kg_m3
        FROM trial4_joint_fit_minute AS d
        JOIN p6.phase6_1_l2_pod_minute_pair_v1 AS p ON p.time_us = d.time_us
        ORDER BY d.storm_id,d.time_us
    """)
    for row in rows:
        yield JoinedMinute(
            str(row[0]), int(row[1]), int(row[2]), float(row[3]), float(row[4]), float(row[5]),
        )


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: empty SQLite connection. Output: P6.2 minute, event, and metadata tables."""
    connection.executescript("""
        CREATE TABLE phase6_2_phase4_decay_minute_v1 (
            storm_id TEXT NOT NULL,
            time_us INTEGER NOT NULL,
            block_index INTEGER NOT NULL,
            chunk_id INTEGER NOT NULL,
            observed_a_m REAL NOT NULL,
            rho_l2_phase_kg_m3 REAL NOT NULL,
            rho_phase4_kg_m3 REAL NOT NULL,
            cumulative_l2_kernel_kg_m REAL NOT NULL,
            cumulative_phase4_kernel_kg_m REAL NOT NULL,
            observed_delta_a_m REAL NOT NULL,
            predicted_l2_delta_a_m REAL NOT NULL,
            predicted_phase4_delta_a_m REAL NOT NULL,
            phase4_residual_m REAL NOT NULL,
            b_eff_m2_kg REAL NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id, time_us)
        );
        CREATE TABLE phase6_2_phase4_decay_event_v1 (
            storm_id TEXT PRIMARY KEY,
            start_time_us INTEGER NOT NULL,
            stop_time_us INTEGER NOT NULL,
            minute_count INTEGER NOT NULL,
            block_count INTEGER NOT NULL,
            observed_covered_delta_a_m REAL NOT NULL,
            predicted_l2_covered_delta_a_m REAL NOT NULL,
            predicted_phase4_covered_delta_a_m REAL NOT NULL,
            phase4_covered_error_m REAL NOT NULL,
            b_eff_m2_kg REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_2_phase4_decay_metadata_v1 (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def store_decay(
    output: sqlite3.Connection,
    minutes,
    b_eff: float,
) -> tuple[int, int]:
    """Input: joined minutes and fixed B_eff. Output: stored minute/event decay row counts."""
    previous = None
    block_start = None
    event_start_time_us = None
    block_index = 0
    cumulative_l2 = 0.0
    cumulative_phase4 = 0.0
    minute_batch = []
    event_rows = []
    event_count = 0
    minute_count = 0
    event_minute_count = 0
    event_block_count = 0
    event_observed_sum = 0.0
    event_l2_sum = 0.0
    event_phase4_sum = 0.0
    observed_delta = 0.0
    predicted_l2 = 0.0
    predicted_phase4 = 0.0
    for current in minutes:
        new_event = previous is None or current.storm_id != previous.storm_id
        gap = not new_event and (
            current.time_us - previous.time_us != MINUTE_US
            or current.chunk_id != previous.chunk_id
        )
        if new_event:
            if previous is not None:
                event_observed_sum += observed_delta
                event_l2_sum += predicted_l2
                event_phase4_sum += predicted_phase4
                event_rows.append((
                    previous.storm_id,
                    event_start_time_us,
                    previous.time_us,
                    event_minute_count,
                    event_block_count,
                    event_observed_sum,
                    event_l2_sum,
                    event_phase4_sum,
                    event_phase4_sum - event_observed_sum,
                    b_eff,
                    ALGORITHM_VERSION,
                ))
            event_count += 1
            event_minute_count = 0
            event_block_count = 1
            event_start_time_us = current.time_us
            event_observed_sum = 0.0
            event_l2_sum = 0.0
            event_phase4_sum = 0.0
            block_index += 1
            block_start = current
            cumulative_l2 = 0.0
            cumulative_phase4 = 0.0
        elif gap:
            event_observed_sum += observed_delta
            event_l2_sum += predicted_l2
            event_phase4_sum += predicted_phase4
            event_block_count += 1
            block_index += 1
            block_start = current
            cumulative_l2 = 0.0
            cumulative_phase4 = 0.0
        if block_start is None:
            raise ValueError("P6.2 block start is missing.")
        if not new_event and not gap:
            cumulative_l2 += kernel_increment(
                DensityValue(previous.semi_major_axis_m, previous.l2_phase_density_kg_m3),
                DensityValue(current.semi_major_axis_m, current.l2_phase_density_kg_m3),
            )
            cumulative_phase4 += kernel_increment(
                DensityValue(previous.semi_major_axis_m, previous.phase4_density_kg_m3),
                DensityValue(current.semi_major_axis_m, current.phase4_density_kg_m3),
            )
        observed_delta = current.semi_major_axis_m - block_start.semi_major_axis_m
        predicted_l2 = -b_eff * cumulative_l2
        predicted_phase4 = -b_eff * cumulative_phase4
        residual = predicted_phase4 - observed_delta
        event_minute_count += 1
        minute_count += 1
        minute_batch.append((
            current.storm_id,
            current.time_us,
            block_index,
            current.chunk_id,
            current.semi_major_axis_m,
            current.l2_phase_density_kg_m3,
            current.phase4_density_kg_m3,
            cumulative_l2,
            cumulative_phase4,
            observed_delta,
            predicted_l2,
            predicted_phase4,
            residual,
            b_eff,
            ALGORITHM_VERSION,
        ))
        if len(minute_batch) == 10_000:
            output.executemany(
                "INSERT INTO phase6_2_phase4_decay_minute_v1 VALUES ("
                + ",".join("?" for _ in range(15)) + ")",
                minute_batch,
            )
            minute_batch.clear()
        previous = current
    if previous is not None:
        event_observed_sum += observed_delta
        event_l2_sum += predicted_l2
        event_phase4_sum += predicted_phase4
        event_rows.append((
            previous.storm_id,
            event_start_time_us,
            previous.time_us,
            event_minute_count,
            event_block_count,
            event_observed_sum,
            event_l2_sum,
            event_phase4_sum,
            event_phase4_sum - event_observed_sum,
            b_eff,
            ALGORITHM_VERSION,
        ))
    output.executemany(
        "INSERT INTO phase6_2_phase4_decay_minute_v1 VALUES ("
        + ",".join("?" for _ in range(15)) + ")",
        minute_batch,
    )
    output.executemany(
        "INSERT INTO phase6_2_phase4_decay_event_v1 VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        event_rows,
    )
    if len(event_rows) != event_count:
        raise ValueError("P6.2 event summary count does not match the integrated events.")
    return minute_count, event_count


def write_result(paths: Phase4Paths) -> dict[str, float | int]:
    """Input: Phase 4 and P6.1 paths. Output: new fixed-B_eff P6.2 SQLite."""
    if paths.output.exists():
        raise FileExistsError(f"Refusing to overwrite existing Phase 6 output: {paths.output}")
    with closing(read_only(paths.beff)) as beff_database:
        b_eff = load_beff(beff_database)
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = paths.output.with_suffix(".part")
    temporary.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(temporary)) as output:
            create_tables(output)
            with closing(read_only(paths.phase4)) as phase4:
                counts = store_decay(
                    output,
                    load_joined_minutes(phase4, paths.minute_pairs),
                    b_eff,
                )
            minute_count, event_count = counts
            if event_count != 25 or minute_count != 214_907:
                raise ValueError(
                    "P6.2 expected 25 events and 214907 minutes, "
                    f"found {event_count} and {minute_count}.",
                )
            output.executemany(
                "INSERT INTO phase6_2_phase4_decay_metadata_v1 VALUES (?,?)",
                [
                    ("algorithm_version", ALGORITHM_VERSION),
                    ("phase4_database", str(paths.phase4)),
                    ("minute_pair_database", str(paths.minute_pairs)),
                    ("beff_database", str(paths.beff)),
                    ("beff_policy", "fixed P6.1 B_eff; no Phase 4 refit"),
                    ("density_field", "rho_trial4_joint_phase_kg_m3"),
                    ("limitation", "Phase 4 is retrospective and L2-fitted"),
                ],
            )
            output.commit()
        os.replace(temporary, paths.output)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "b_eff_m2_kg": b_eff,
        "minute_count": minute_count,
        "event_count": event_count,
    }


def run(paths: Phase4Paths = Phase4Paths()) -> dict[str, float | int]:
    """Input: default Phase 4 and P6.1 sources. Output: P6.2 result summary."""
    return write_result(paths)


def main() -> None:
    """Input: no command-line arguments. Output: P6.2 fixed-B_eff summary."""
    if sys.argv[1:]:
        raise SystemExit("Usage: python -m phases.phase6.code.calc_phase6_2_phase4_decay")
    print(run())


if __name__ == "__main__":
    main()
