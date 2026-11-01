"""Apply the fixed P6.1 B_eff to Phase 3 M0 storm-window density."""

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


ALGORITHM_VERSION = "phase6_2_fixed_beff_m0_error_v1"


@dataclass(frozen=True)
class M0Paths:
    """Input: Phase 3 M0 snapshot, P6.1 pairs/B_eff, output. Output: P6.2 paths."""

    density_snapshot: Path = Path(
        "phases/phase3/data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite",
    )
    minute_pairs: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_1_l2_minute_pairs_v1.sqlite",
    )
    beff: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_1_beff_v1.sqlite",
    )
    output: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_2_m0_error_v1.sqlite",
    )


@dataclass(frozen=True)
class DensityValue:
    """Input: semi-major axis m and density kg/m^3. Output: one kernel endpoint."""

    semi_major_axis_m: float
    density_kg_m3: float


@dataclass(frozen=True)
class JoinedMinute:
    """Input: exact M0/P6.1 minute join. Output: one P6.2 integration row."""

    storm_id: str
    time_us: int
    chunk_id: int
    semi_major_axis_m: float
    m0_density_kg_m3: float


@dataclass(frozen=True)
class ErrorSummary:
    """Input: 25 event errors. Output: P6.2 aggregate descriptive metrics."""

    event_count: int
    underestimated_count: int
    overestimated_count: int
    mean_error_m: float
    mean_absolute_error_m: float
    root_mean_square_error_m: float
    mean_absolute_percentage_error: float


@dataclass(frozen=True)
class EventAggregate:
    """Input: one storm's covered blocks. Output: values needed for its error row."""

    start_time_us: int
    minute_count: int
    block_count: int
    observed_delta_a_m: float
    predicted_m0_delta_a_m: float


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
    density_snapshot: sqlite3.Connection,
    minute_pairs_path: Path,
):
    """Input: Phase 3 M0 snapshot and P6.1 pairs. Output: joined minute iterator."""
    density_snapshot.execute(
        "ATTACH DATABASE ? AS p6",
        (f"file:{minute_pairs_path.resolve().as_posix()}?mode=ro",),
    )
    rows = density_snapshot.execute("""
        SELECT d.storm_id,d.time_us,p.chunk_id,p.mean_semi_major_axis_m,
               d.rho_msis_full_phase_kg_m3
        FROM phase3_prediction_minute AS d
        JOIN p6.phase6_1_l2_pod_minute_pair_v1 AS p ON p.time_us = d.time_us
        ORDER BY d.storm_id,d.time_us
    """)
    for row in rows:
        yield JoinedMinute(
            str(row[0]), int(row[1]), int(row[2]), float(row[3]), float(row[4]),
        )


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: empty SQLite connection. Output: P6.2 minute, event, summary tables."""
    connection.executescript("""
        CREATE TABLE phase6_2_m0_decay_minute_v1 (
            storm_id TEXT NOT NULL,
            time_us INTEGER NOT NULL,
            block_index INTEGER NOT NULL,
            chunk_id INTEGER NOT NULL,
            observed_a_m REAL NOT NULL,
            rho_m0_kg_m3 REAL NOT NULL,
            cumulative_m0_kernel_kg_m REAL NOT NULL,
            observed_delta_a_m REAL NOT NULL,
            predicted_m0_delta_a_m REAL NOT NULL,
            m0_residual_m REAL NOT NULL,
            b_eff_m2_kg REAL NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id, time_us)
        );
        CREATE TABLE phase6_2_m0_error_event_v1 (
            storm_id TEXT PRIMARY KEY,
            start_time_us INTEGER NOT NULL,
            stop_time_us INTEGER NOT NULL,
            minute_count INTEGER NOT NULL,
            block_count INTEGER NOT NULL,
            observed_covered_delta_a_m REAL NOT NULL,
            predicted_m0_covered_delta_a_m REAL NOT NULL,
            m0_error_m REAL NOT NULL,
            absolute_error_m REAL NOT NULL,
            absolute_percentage_error REAL NOT NULL,
            b_eff_m2_kg REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_2_m0_error_summary_v1 (
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
        CREATE TABLE phase6_2_m0_error_metadata_v1 (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def summarize_errors(event_rows: list[tuple]) -> ErrorSummary:
    """Input: P6.2 event output rows. Output: descriptive endpoint error metrics."""
    errors = [float(row[7]) for row in event_rows]
    percentage_errors = [float(row[9]) for row in event_rows]
    if not errors:
        raise ValueError("P6.2 requires at least one event error.")
    return ErrorSummary(
        event_count=len(errors),
        underestimated_count=sum(error > 0.0 for error in errors),
        overestimated_count=sum(error < 0.0 for error in errors),
        mean_error_m=sum(errors) / len(errors),
        mean_absolute_error_m=sum(map(abs, errors)) / len(errors),
        root_mean_square_error_m=math.sqrt(
            sum(error * error for error in errors) / len(errors),
        ),
        mean_absolute_percentage_error=sum(percentage_errors) / len(percentage_errors),
    )


def store_decay(
    output: sqlite3.Connection,
    minutes,
    b_eff: float,
) -> tuple[int, ErrorSummary]:
    """Input: joined minutes and fixed B_eff. Output: stored rows and error summary."""
    previous = None
    block_start = None
    event_start_time_us = None
    block_index = 0
    cumulative_m0 = 0.0
    minute_batch = []
    event_rows = []
    minute_count = 0
    event_minute_count = 0
    event_block_count = 0
    event_observed_sum = 0.0
    event_m0_sum = 0.0
    observed_delta = 0.0
    predicted_m0 = 0.0
    for current in minutes:
        new_event = previous is None or current.storm_id != previous.storm_id
        gap = not new_event and (
            current.time_us - previous.time_us != MINUTE_US
            or current.chunk_id != previous.chunk_id
        )
        if new_event:
            if previous is not None:
                event_observed_sum += observed_delta
                event_m0_sum += predicted_m0
                event_rows.append(event_output_row(
                    previous,
                    EventAggregate(
                        event_start_time_us,
                        event_minute_count,
                        event_block_count,
                        event_observed_sum,
                        event_m0_sum,
                    ),
                    b_eff,
                ))
            event_minute_count = 0
            event_block_count = 1
            event_start_time_us = current.time_us
            event_observed_sum = 0.0
            event_m0_sum = 0.0
            block_index += 1
            block_start = current
            cumulative_m0 = 0.0
        elif gap:
            event_observed_sum += observed_delta
            event_m0_sum += predicted_m0
            event_block_count += 1
            block_index += 1
            block_start = current
            cumulative_m0 = 0.0
        if block_start is None:
            raise ValueError("P6.2 block start is missing.")
        if not new_event and not gap:
            cumulative_m0 += kernel_increment(
                DensityValue(previous.semi_major_axis_m, previous.m0_density_kg_m3),
                DensityValue(current.semi_major_axis_m, current.m0_density_kg_m3),
            )
        observed_delta = current.semi_major_axis_m - block_start.semi_major_axis_m
        predicted_m0 = -b_eff * cumulative_m0
        residual = predicted_m0 - observed_delta
        event_minute_count += 1
        minute_count += 1
        minute_batch.append((
            current.storm_id,
            current.time_us,
            block_index,
            current.chunk_id,
            current.semi_major_axis_m,
            current.m0_density_kg_m3,
            cumulative_m0,
            observed_delta,
            predicted_m0,
            residual,
            b_eff,
            ALGORITHM_VERSION,
        ))
        if len(minute_batch) == 10_000:
            output.executemany(
                "INSERT INTO phase6_2_m0_decay_minute_v1 VALUES ("
                + ",".join("?" for _ in range(12)) + ")",
                minute_batch,
            )
            minute_batch.clear()
        previous = current
    if previous is not None:
        event_observed_sum += observed_delta
        event_m0_sum += predicted_m0
        event_rows.append(event_output_row(
            previous,
            EventAggregate(
                event_start_time_us,
                event_minute_count,
                event_block_count,
                event_observed_sum,
                event_m0_sum,
            ),
            b_eff,
        ))
    output.executemany(
        "INSERT INTO phase6_2_m0_decay_minute_v1 VALUES ("
        + ",".join("?" for _ in range(12)) + ")",
        minute_batch,
    )
    output.executemany(
        "INSERT INTO phase6_2_m0_error_event_v1 VALUES ("
        + ",".join("?" for _ in range(12)) + ")",
        event_rows,
    )
    summary = summarize_errors(event_rows)
    output.execute(
        "INSERT INTO phase6_2_m0_error_summary_v1 VALUES (?,?,?,?,?,?,?,?,?,?)",
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


def event_output_row(
    last_minute: JoinedMinute,
    aggregate: EventAggregate,
    b_eff: float,
) -> tuple:
    """Input: event endpoint, aggregate, B_eff. Output: one event error row."""
    observed_delta = aggregate.observed_delta_a_m
    predicted_m0 = aggregate.predicted_m0_delta_a_m
    if observed_delta == 0.0:
        raise ValueError(f"P6.2 event has zero observed change: {last_minute.storm_id}")
    error = predicted_m0 - observed_delta
    return (
        last_minute.storm_id,
        aggregate.start_time_us,
        last_minute.time_us,
        aggregate.minute_count,
        aggregate.block_count,
        observed_delta,
        predicted_m0,
        error,
        abs(error),
        abs(error / observed_delta) * 100.0,
        b_eff,
        ALGORITHM_VERSION,
    )


def write_result(paths: M0Paths) -> dict[str, float | int]:
    """Input: Phase 3 M0 snapshot and P6.1 paths. Output: P6.2 error SQLite."""
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
            with closing(read_only(paths.density_snapshot)) as density_snapshot:
                minute_count, summary = store_decay(
                    output,
                    load_joined_minutes(density_snapshot, paths.minute_pairs),
                    b_eff,
                )
            if summary.event_count != 25 or minute_count != 214_907:
                raise ValueError(
                    "P6.2 expected 25 events and 214907 minutes, "
                    f"found {summary.event_count} and {minute_count}.",
                )
            output.executemany(
                "INSERT INTO phase6_2_m0_error_metadata_v1 VALUES (?,?)",
                [
                    ("algorithm_version", ALGORITHM_VERSION),
                    ("density_snapshot_database", str(paths.density_snapshot)),
                    ("minute_pair_database", str(paths.minute_pairs)),
                    ("beff_database", str(paths.beff)),
                    ("beff_policy", "fixed P6.1 B_eff; no M0 refit"),
                    ("density_model", "Phase 3 M0: NRLMSIS 2.0 full density"),
                    ("density_field", "rho_msis_full_phase_kg_m3"),
                    ("error", "predicted M0 change minus observed POD change"),
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


def run(paths: M0Paths = M0Paths()) -> dict[str, float | int]:
    """Input: default Phase 3 M0 and P6.1 sources. Output: P6.2 error summary."""
    return write_result(paths)


def main() -> None:
    """Input: no command-line arguments. Output: P6.2 M0 error summary."""
    if sys.argv[1:]:
        raise SystemExit("Usage: python -m phases.phase6.code.calc_phase6_2_m0_error")
    print(run())


if __name__ == "__main__":
    main()
