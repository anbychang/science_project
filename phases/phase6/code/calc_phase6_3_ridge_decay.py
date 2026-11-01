"""Apply the fixed P6.1 B_eff to Phase 5 V2 Ridge density."""

import os
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from phases.phase6.code.calc_phase6_1_beff import MINUTE_US, read_only
from phases.phase6.code.calc_phase6_2_m0_error import (
    DensityValue,
    ErrorSummary,
    kernel_increment,
    load_beff,
    summarize_errors,
)


ALGORITHM_VERSION = "phase6_3_fixed_beff_ridge_decay_v1"
EXPECTED_EVENT_COUNT = 25
EXPECTED_MINUTE_COUNT = 214_907


@dataclass(frozen=True)
class RidgePaths:
    """Input: {Ridge density, P6.1 pairs, B_eff}. Output: P6.3 paths."""

    ridge_density: Path = Path(
        "phases/phase5-v2/data/sqlite/storm_r_ridge_density_v1.sqlite",
    )
    minute_pairs: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_1_l2_minute_pairs_v1.sqlite",
    )
    beff: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_1_beff_v1.sqlite",
    )
    output: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_3_ridge_decay_v1.sqlite",
    )


@dataclass(frozen=True)
class JoinedMinute:
    """Input: {Ridge density, POD minute}. Output: one integration row."""

    storm_id: str
    time_us: int
    chunk_id: int
    semi_major_axis_m: float
    ridge_density_kg_m3: float


@dataclass(frozen=True)
class EventAggregate:
    """Input: one storm's covered blocks. Output: one event error aggregate."""

    start_time_us: int
    minute_count: int
    block_count: int
    observed_delta_a_m: float
    predicted_ridge_delta_a_m: float


def load_joined_minutes(
    ridge_density: sqlite3.Connection,
    minute_pairs_path: Path,
):
    """Input: {Ridge SQLite, P6.1 pair path}. Output: joined minute iterator."""
    ridge_density.execute(
        "ATTACH DATABASE ? AS p6",
        (f"file:{minute_pairs_path.resolve().as_posix()}?mode=ro",),
    )
    rows = ridge_density.execute("""
        SELECT d.storm_id,d.time_us,p.chunk_id,p.mean_semi_major_axis_m,
               d.rho_ridge_phase_kg_m3
        FROM density_comparison AS d
        JOIN p6.phase6_1_l2_pod_minute_pair_v1 AS p ON p.time_us = d.time_us
        ORDER BY d.storm_id,d.time_us
    """)
    for row in rows:
        yield JoinedMinute(
            str(row[0]), int(row[1]), int(row[2]), float(row[3]), float(row[4]),
        )


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: empty SQLite. Output: P6.3 minute, event, summary tables."""
    connection.executescript("""
        CREATE TABLE phase6_3_ridge_decay_minute_v1 (
            storm_id TEXT NOT NULL,
            time_us INTEGER NOT NULL,
            block_index INTEGER NOT NULL,
            chunk_id INTEGER NOT NULL,
            observed_a_m REAL NOT NULL,
            rho_ridge_kg_m3 REAL NOT NULL,
            cumulative_ridge_kernel_kg_m REAL NOT NULL,
            observed_delta_a_m REAL NOT NULL,
            predicted_ridge_delta_a_m REAL NOT NULL,
            ridge_residual_m REAL NOT NULL,
            b_eff_m2_kg REAL NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id, time_us)
        );
        CREATE TABLE phase6_3_ridge_decay_event_v1 (
            storm_id TEXT PRIMARY KEY,
            start_time_us INTEGER NOT NULL,
            stop_time_us INTEGER NOT NULL,
            minute_count INTEGER NOT NULL,
            block_count INTEGER NOT NULL,
            observed_covered_delta_a_m REAL NOT NULL,
            predicted_ridge_covered_delta_a_m REAL NOT NULL,
            ridge_error_m REAL NOT NULL,
            absolute_error_m REAL NOT NULL,
            absolute_percentage_error REAL NOT NULL,
            b_eff_m2_kg REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_3_ridge_decay_summary_v1 (
            summary_id TEXT PRIMARY KEY,
            event_count INTEGER NOT NULL,
            underestimated_count INTEGER NOT NULL,
            overestimated_count INTEGER NOT NULL,
            mean_error_m REAL NOT NULL,
            mean_absolute_error_m REAL NOT NULL,
            root_mean_square_error_m REAL NOT NULL,
            mean_absolute_percentage_error REAL NOT NULL,
            b_eff_m2_kg REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_3_ridge_decay_metadata_v1 (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def store_decay(
    output: sqlite3.Connection,
    minutes,
    b_eff: float,
) -> tuple[int, ErrorSummary]:
    """Input: {joined minutes, fixed B_eff}. Output: stored rows and summary."""
    previous = None
    block_start = None
    event_start_time_us = None
    block_index = 0
    cumulative_ridge = 0.0
    minute_batch = []
    event_rows = []
    minute_count = 0
    event_minute_count = 0
    event_block_count = 0
    event_observed_sum = 0.0
    event_ridge_sum = 0.0
    observed_delta = 0.0
    predicted_ridge = 0.0
    for current in minutes:
        new_event = previous is None or current.storm_id != previous.storm_id
        gap = not new_event and (
            current.time_us - previous.time_us != MINUTE_US
            or current.chunk_id != previous.chunk_id
        )
        if new_event:
            if previous is not None:
                event_observed_sum += observed_delta
                event_ridge_sum += predicted_ridge
                event_rows.append(event_output_row(
                    previous,
                    EventAggregate(
                        event_start_time_us,
                        event_minute_count,
                        event_block_count,
                        event_observed_sum,
                        event_ridge_sum,
                    ),
                    b_eff,
                ))
            event_minute_count = 0
            event_block_count = 1
            event_start_time_us = current.time_us
            event_observed_sum = 0.0
            event_ridge_sum = 0.0
            block_index += 1
            block_start = current
            cumulative_ridge = 0.0
        elif gap:
            event_observed_sum += observed_delta
            event_ridge_sum += predicted_ridge
            event_block_count += 1
            block_index += 1
            block_start = current
            cumulative_ridge = 0.0
        if block_start is None:
            raise ValueError("P6.3 block start is missing.")
        if not new_event and not gap:
            cumulative_ridge += kernel_increment(
                DensityValue(previous.semi_major_axis_m, previous.ridge_density_kg_m3),
                DensityValue(current.semi_major_axis_m, current.ridge_density_kg_m3),
            )
        observed_delta = current.semi_major_axis_m - block_start.semi_major_axis_m
        predicted_ridge = -b_eff * cumulative_ridge
        residual = predicted_ridge - observed_delta
        event_minute_count += 1
        minute_count += 1
        minute_batch.append((
            current.storm_id,
            current.time_us,
            block_index,
            current.chunk_id,
            current.semi_major_axis_m,
            current.ridge_density_kg_m3,
            cumulative_ridge,
            observed_delta,
            predicted_ridge,
            residual,
            b_eff,
            ALGORITHM_VERSION,
        ))
        if len(minute_batch) == 10_000:
            insert_minutes(output, minute_batch)
            minute_batch.clear()
        previous = current
    if previous is not None:
        event_observed_sum += observed_delta
        event_ridge_sum += predicted_ridge
        event_rows.append(event_output_row(
            previous,
            EventAggregate(
                event_start_time_us,
                event_minute_count,
                event_block_count,
                event_observed_sum,
                event_ridge_sum,
            ),
            b_eff,
        ))
    insert_minutes(output, minute_batch)
    output.executemany(
        "INSERT INTO phase6_3_ridge_decay_event_v1 VALUES ("
        + ",".join("?" for _ in range(12)) + ")",
        event_rows,
    )
    summary = summarize_errors(event_rows)
    output.execute(
        "INSERT INTO phase6_3_ridge_decay_summary_v1 VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            "all_25_storms",
            summary.event_count,
            summary.underestimated_count,
            summary.overestimated_count,
            summary.mean_error_m,
            summary.mean_absolute_error_m,
            summary.root_mean_square_error_m,
            summary.mean_absolute_percentage_error,
            b_eff,
            ALGORITHM_VERSION,
        ),
    )
    return minute_count, summary


def insert_minutes(output: sqlite3.Connection, minute_rows: list[tuple]) -> None:
    """Input: {output SQLite, minute rows}. Output: inserted P6.3 rows."""
    output.executemany(
        "INSERT INTO phase6_3_ridge_decay_minute_v1 VALUES ("
        + ",".join("?" for _ in range(12)) + ")",
        minute_rows,
    )


def event_output_row(
    last_minute: JoinedMinute,
    aggregate: EventAggregate,
    b_eff: float,
) -> tuple:
    """Input: {event endpoint, aggregate, B_eff}. Output: event error row."""
    observed_delta = aggregate.observed_delta_a_m
    predicted_ridge = aggregate.predicted_ridge_delta_a_m
    if observed_delta == 0.0:
        raise ValueError(f"P6.3 event has zero observed change: {last_minute.storm_id}")
    error = predicted_ridge - observed_delta
    return (
        last_minute.storm_id,
        aggregate.start_time_us,
        last_minute.time_us,
        aggregate.minute_count,
        aggregate.block_count,
        observed_delta,
        predicted_ridge,
        error,
        abs(error),
        abs(error / observed_delta) * 100.0,
        b_eff,
        ALGORITHM_VERSION,
    )


def write_result(paths: RidgePaths) -> dict[str, float | int]:
    """Input: P5V2 Ridge and P6.1 paths. Output: P6.3 SQLite and summary."""
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
            with closing(read_only(paths.ridge_density)) as ridge_density:
                minute_count, summary = store_decay(
                    output,
                    load_joined_minutes(ridge_density, paths.minute_pairs),
                    b_eff,
                )
            if (
                summary.event_count != EXPECTED_EVENT_COUNT
                or minute_count != EXPECTED_MINUTE_COUNT
            ):
                raise ValueError(
                    "P6.3 expected 25 events and 214907 minutes, "
                    f"found {summary.event_count} and {minute_count}.",
                )
            output.executemany(
                "INSERT INTO phase6_3_ridge_decay_metadata_v1 VALUES (?,?)",
                [
                    ("algorithm_version", ALGORITHM_VERSION),
                    ("ridge_density_database", str(paths.ridge_density)),
                    ("minute_pair_database", str(paths.minute_pairs)),
                    ("beff_database", str(paths.beff)),
                    ("beff_policy", "fixed P6.1 B_eff; no P6.3 refit"),
                    ("density_model", "Phase 5 V2 held-out Ridge R + Phase 4 V2 response"),
                    ("density_field", "rho_ridge_phase_kg_m3"),
                    ("error", "predicted Ridge change minus observed POD change"),
                    (
                        "validation_scope",
                        "exploratory; feature set selected using the same 25 storms",
                    ),
                ],
            )
            output.commit()
        os.replace(temporary, paths.output)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "b_eff_m2_kg": b_eff,
        "minute_count": minute_count,
        "event_count": summary.event_count,
        "mae_m": summary.mean_absolute_error_m,
        "rmse_m": summary.root_mean_square_error_m,
        "mape_percent": summary.mean_absolute_percentage_error,
    }


def run(paths: RidgePaths = RidgePaths()) -> dict[str, float | int]:
    """Input: default P5V2/P6.1 paths. Output: P6.3 error summary."""
    return write_result(paths)


def main() -> None:
    """Input: no arguments. Output: P6.3 Ridge decay summary."""
    if sys.argv[1:]:
        raise SystemExit("Usage: python -m phases.phase6.code.calc_phase6_3_ridge_decay")
    print(run())


if __name__ == "__main__":
    main()
