"""Merge P6.2 and P6.3 into one density-to-decay comparison database."""

import os
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path


ALGORITHM_VERSION = "phase6_4_decay_comparison_v1"
EXPECTED_EVENT_COUNT = 25
EXPECTED_MINUTE_COUNT = 214_907
INSERT_BATCH_SIZE = 10_000


@dataclass(frozen=True)
class ComparisonPaths:
    """Input: {P6.2, P6.3, output}. Output: P6.4 paths."""

    m0_decay: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_2_m0_error_v1.sqlite",
    )
    ridge_decay: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_3_ridge_decay_v1.sqlite",
    )
    output: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_4_decay_comparison_v1.sqlite",
    )


@dataclass(frozen=True)
class ComparisonMinute:
    """Input: one exact P6.2/P6.3 key. Output: one joined minute."""

    storm_id: str
    time_us: int
    block_index: int
    chunk_id: int
    observed_a_m: float
    observed_block_delta_a_m: float
    rho_m0_kg_m3: float
    rho_ridge_kg_m3: float
    predicted_m0_block_delta_a_m: float
    predicted_ridge_block_delta_a_m: float
    b_eff_m2_kg: float


def database_uri(path: Path) -> str:
    """Input: SQLite path. Output: read-only SQLite URI."""
    return f"file:{path.resolve().as_posix()}?mode=ro"


def attach_sources(connection: sqlite3.Connection, paths: ComparisonPaths) -> None:
    """Input: {output connection, source paths}. Output: attached read-only sources."""
    connection.execute("ATTACH DATABASE ? AS m0", (database_uri(paths.m0_decay),))
    connection.execute("ATTACH DATABASE ? AS ridge", (database_uri(paths.ridge_decay),))


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: empty SQLite. Output: P6.4 minute, event, summary, metadata tables."""
    connection.executescript("""
        CREATE TABLE phase6_4_decay_comparison_minute_v1 (
            storm_id TEXT NOT NULL,
            time_us INTEGER NOT NULL,
            block_index INTEGER NOT NULL,
            chunk_id INTEGER NOT NULL,
            observed_a_m REAL NOT NULL,
            observed_block_delta_a_m REAL NOT NULL,
            observed_covered_delta_a_m REAL NOT NULL,
            rho_m0_kg_m3 REAL NOT NULL,
            rho_ridge_kg_m3 REAL NOT NULL,
            predicted_m0_block_delta_a_m REAL NOT NULL,
            predicted_m0_covered_delta_a_m REAL NOT NULL,
            predicted_ridge_block_delta_a_m REAL NOT NULL,
            predicted_ridge_covered_delta_a_m REAL NOT NULL,
            m0_covered_error_m REAL NOT NULL,
            ridge_covered_error_m REAL NOT NULL,
            b_eff_m2_kg REAL NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id, time_us)
        );
        CREATE TABLE phase6_4_decay_comparison_event_v1 (
            storm_id TEXT PRIMARY KEY,
            start_time_us INTEGER NOT NULL,
            stop_time_us INTEGER NOT NULL,
            minute_count INTEGER NOT NULL,
            block_count INTEGER NOT NULL,
            observed_covered_delta_a_m REAL NOT NULL,
            predicted_m0_covered_delta_a_m REAL NOT NULL,
            m0_error_m REAL NOT NULL,
            m0_absolute_percentage_error REAL NOT NULL,
            predicted_ridge_covered_delta_a_m REAL NOT NULL,
            ridge_error_m REAL NOT NULL,
            ridge_absolute_percentage_error REAL NOT NULL,
            b_eff_m2_kg REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_4_decay_comparison_summary_v1 (
            model_id TEXT PRIMARY KEY,
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
        CREATE TABLE phase6_4_decay_comparison_metadata_v1 (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def validate_sources(connection: sqlite3.Connection) -> None:
    """Input: attached P6.2/P6.3. Output: validated exact minute and event joins."""
    minute_counts = connection.execute("""
        SELECT
          (SELECT COUNT(*) FROM m0.phase6_2_m0_decay_minute_v1),
          (SELECT COUNT(*) FROM ridge.phase6_3_ridge_decay_minute_v1),
          COUNT(*)
        FROM m0.phase6_2_m0_decay_minute_v1 AS m
        JOIN ridge.phase6_3_ridge_decay_minute_v1 AS r
          USING (storm_id,time_us)
    """).fetchone()
    if minute_counts != (
        EXPECTED_MINUTE_COUNT,
        EXPECTED_MINUTE_COUNT,
        EXPECTED_MINUTE_COUNT,
    ):
        raise ValueError(f"P6.4 minute join mismatch: {minute_counts}")
    minute_mismatches = connection.execute("""
        SELECT COUNT(*)
        FROM m0.phase6_2_m0_decay_minute_v1 AS m
        JOIN ridge.phase6_3_ridge_decay_minute_v1 AS r
          USING (storm_id,time_us)
        WHERE m.block_index != r.block_index
           OR m.chunk_id != r.chunk_id
           OR m.observed_a_m != r.observed_a_m
           OR m.observed_delta_a_m != r.observed_delta_a_m
           OR m.b_eff_m2_kg != r.b_eff_m2_kg
    """).fetchone()[0]
    if minute_mismatches:
        raise ValueError(f"P6.4 found {minute_mismatches} inconsistent minute rows.")
    event_counts = connection.execute("""
        SELECT
          (SELECT COUNT(*) FROM m0.phase6_2_m0_error_event_v1),
          (SELECT COUNT(*) FROM ridge.phase6_3_ridge_decay_event_v1),
          COUNT(*)
        FROM m0.phase6_2_m0_error_event_v1 AS m
        JOIN ridge.phase6_3_ridge_decay_event_v1 AS r USING (storm_id)
    """).fetchone()
    if event_counts != (EXPECTED_EVENT_COUNT,) * 3:
        raise ValueError(f"P6.4 event join mismatch: {event_counts}")


def load_joined_minutes(connection: sqlite3.Connection):
    """Input: attached P6.2/P6.3. Output: exact joined minute iterator."""
    rows = connection.execute("""
        SELECT m.storm_id,m.time_us,m.block_index,m.chunk_id,m.observed_a_m,
               m.observed_delta_a_m,m.rho_m0_kg_m3,r.rho_ridge_kg_m3,
               m.predicted_m0_delta_a_m,r.predicted_ridge_delta_a_m,
               m.b_eff_m2_kg
        FROM m0.phase6_2_m0_decay_minute_v1 AS m
        JOIN ridge.phase6_3_ridge_decay_minute_v1 AS r
          USING (storm_id,time_us)
        ORDER BY m.storm_id,m.time_us
    """)
    for row in rows:
        yield ComparisonMinute(
            str(row[0]),
            int(row[1]),
            int(row[2]),
            int(row[3]),
            float(row[4]),
            float(row[5]),
            float(row[6]),
            float(row[7]),
            float(row[8]),
            float(row[9]),
            float(row[10]),
        )


def insert_minute_batch(connection: sqlite3.Connection, rows: list[tuple]) -> None:
    """Input: {P6.4 SQLite, minute rows}. Output: inserted comparison rows."""
    connection.executemany(
        "INSERT INTO phase6_4_decay_comparison_minute_v1 VALUES ("
        + ",".join("?" for _ in range(17)) + ")",
        rows,
    )


def store_comparison_minutes(
    connection: sqlite3.Connection,
    minutes,
) -> tuple[int, int, int]:
    """Input: joined block-local minutes. Output: minute, event, block counts."""
    previous = None
    observed_offset = 0.0
    m0_offset = 0.0
    ridge_offset = 0.0
    minute_count = 0
    event_count = 0
    block_count = 0
    batch = []
    for current in minutes:
        new_event = previous is None or current.storm_id != previous.storm_id
        new_block = not new_event and current.block_index != previous.block_index
        if new_event:
            observed_offset = 0.0
            m0_offset = 0.0
            ridge_offset = 0.0
            event_count += 1
            block_count += 1
        elif new_block:
            observed_offset += previous.observed_block_delta_a_m
            m0_offset += previous.predicted_m0_block_delta_a_m
            ridge_offset += previous.predicted_ridge_block_delta_a_m
            block_count += 1
        observed_covered = observed_offset + current.observed_block_delta_a_m
        predicted_m0_covered = m0_offset + current.predicted_m0_block_delta_a_m
        predicted_ridge_covered = (
            ridge_offset + current.predicted_ridge_block_delta_a_m
        )
        batch.append((
            current.storm_id,
            current.time_us,
            current.block_index,
            current.chunk_id,
            current.observed_a_m,
            current.observed_block_delta_a_m,
            observed_covered,
            current.rho_m0_kg_m3,
            current.rho_ridge_kg_m3,
            current.predicted_m0_block_delta_a_m,
            predicted_m0_covered,
            current.predicted_ridge_block_delta_a_m,
            predicted_ridge_covered,
            predicted_m0_covered - observed_covered,
            predicted_ridge_covered - observed_covered,
            current.b_eff_m2_kg,
            ALGORITHM_VERSION,
        ))
        if len(batch) == INSERT_BATCH_SIZE:
            insert_minute_batch(connection, batch)
            batch.clear()
        previous = current
        minute_count += 1
    insert_minute_batch(connection, batch)
    return minute_count, event_count, block_count


def store_event_and_summary(connection: sqlite3.Connection) -> None:
    """Input: attached P6.2/P6.3. Output: normalized event and summary tables."""
    connection.execute("""
        INSERT INTO phase6_4_decay_comparison_event_v1
        SELECT m.storm_id,m.start_time_us,m.stop_time_us,m.minute_count,
               m.block_count,m.observed_covered_delta_a_m,
               m.predicted_m0_covered_delta_a_m,m.m0_error_m,
               m.absolute_percentage_error,
               r.predicted_ridge_covered_delta_a_m,r.ridge_error_m,
               r.absolute_percentage_error,m.b_eff_m2_kg,?
        FROM m0.phase6_2_m0_error_event_v1 AS m
        JOIN ridge.phase6_3_ridge_decay_event_v1 AS r USING (storm_id)
        ORDER BY m.storm_id
    """, (ALGORITHM_VERSION,))
    connection.execute("""
        INSERT INTO phase6_4_decay_comparison_summary_v1
        SELECT 'M0',event_count,underestimated_count,overestimated_count,
               mean_error_m,mean_absolute_error_m,root_mean_square_error_m,
               mean_absolute_percentage_error,b_eff_m2_kg,?
        FROM m0.phase6_2_m0_error_summary_v1
        UNION ALL
        SELECT 'P5V2_RIDGE',event_count,underestimated_count,overestimated_count,
               mean_error_m,mean_absolute_error_m,root_mean_square_error_m,
               mean_absolute_percentage_error,b_eff_m2_kg,?
        FROM ridge.phase6_3_ridge_decay_summary_v1
    """, (ALGORITHM_VERSION, ALGORITHM_VERSION))


def validate_output(connection: sqlite3.Connection) -> None:
    """Input: populated P6.4 SQLite. Output: verified counts and event endpoints."""
    counts = connection.execute("""
        SELECT COUNT(*),COUNT(DISTINCT storm_id),COUNT(DISTINCT block_index)
        FROM phase6_4_decay_comparison_minute_v1
    """).fetchone()
    if counts != (EXPECTED_MINUTE_COUNT, EXPECTED_EVENT_COUNT, 31):
        raise ValueError(f"P6.4 output count mismatch: {counts}")
    endpoint_mismatches = connection.execute("""
        SELECT COUNT(*)
        FROM phase6_4_decay_comparison_event_v1 AS event
        JOIN phase6_4_decay_comparison_minute_v1 AS minute
          ON minute.storm_id = event.storm_id
         AND minute.time_us = event.stop_time_us
        WHERE minute.observed_covered_delta_a_m != event.observed_covered_delta_a_m
           OR minute.predicted_m0_covered_delta_a_m
              != event.predicted_m0_covered_delta_a_m
           OR minute.predicted_ridge_covered_delta_a_m
              != event.predicted_ridge_covered_delta_a_m
    """).fetchone()[0]
    if endpoint_mismatches:
        raise ValueError(f"P6.4 found {endpoint_mismatches} endpoint mismatches.")


def write_result(paths: ComparisonPaths) -> dict[str, int]:
    """Input: P6.2/P6.3 paths. Output: new P6.4 comparison SQLite."""
    if paths.output.exists():
        raise FileExistsError(f"Refusing to overwrite existing Phase 6 output: {paths.output}")
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = paths.output.with_suffix(".part")
    temporary.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(temporary, uri=True)) as output:
            create_tables(output)
            attach_sources(output, paths)
            validate_sources(output)
            counts = store_comparison_minutes(output, load_joined_minutes(output))
            store_event_and_summary(output)
            validate_output(output)
            output.executemany(
                "INSERT INTO phase6_4_decay_comparison_metadata_v1 VALUES (?,?)",
                [
                    ("algorithm_version", ALGORITHM_VERSION),
                    ("m0_decay_database", str(paths.m0_decay)),
                    ("ridge_decay_database", str(paths.ridge_decay)),
                    ("join_key", "storm_id,time_us"),
                    ("gap_policy", "preserve blocks; never connect missing minutes"),
                    ("comparison_scope", "descriptive P6.2 M0 versus P6.3 Ridge"),
                ],
            )
            output.commit()
        os.replace(temporary, paths.output)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "minute_count": counts[0],
        "event_count": counts[1],
        "block_count": counts[2],
    }


def run(paths: ComparisonPaths = ComparisonPaths()) -> dict[str, int]:
    """Input: default P6.2/P6.3 paths. Output: P6.4 row counts."""
    return write_result(paths)


def main() -> None:
    """Input: no arguments. Output: P6.4 comparison counts."""
    if sys.argv[1:]:
        raise SystemExit("Usage: python -m phases.phase6.code.prep_phase6_4_decay_comparison")
    print(run())


if __name__ == "__main__":
    main()
