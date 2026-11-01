"""Apply the fixed Phase 6 B_eff to the configured Phase 7 storm set."""

import math
import os
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from phases.phase6.code.calc_phase6_1_beff import (
    EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
    MINUTE_S,
    MINUTE_US,
)
from phases.phase7.code.load_phase7_two_storms import (
    PHASE1R,
    RUN_LABEL,
    RUN_ROOT,
    STORM_IDS,
    load_fixed_model,
    read_only,
)


DENSITY = RUN_ROOT / "data" / "sqlite" / "swarm_a_phase7_density_v1.sqlite"
OUTPUT = RUN_ROOT / "data" / "sqlite" / "swarm_a_phase7_decay_v1.sqlite"
ALGORITHM_VERSION = f"phase7_{RUN_LABEL}_fixed_beff_decay_v1"
HALF_MINUTE_US = 30_000_000
EXPECTED_POD_SAMPLES = 6


@dataclass(frozen=True)
class JoinedMinute:
    """Input: exact Phase 7 density/POD minute. Output: one integration record."""

    storm_id: str
    time_us: int
    chunk_id: int
    semi_major_axis_m: float
    rho_m0_kg_m3: float
    rho_ridge_kg_m3: float


def load_pod_minutes(
    connection: sqlite3.Connection, start_time_us: int, end_time_us: int
) -> dict[int, tuple[int, float]]:
    """Input: Phase 1R and UTC bounds. Output: {minute_us: (chunk_id, mean a m)}."""
    rows = connection.execute("""
        SELECT ((m.time_us + ?) / ?) * ? AS minute_us,
               q.chunk_id,AVG(m.mean_semi_major_axis_m),COUNT(*)
        FROM swarm_a_mean_orbit_elements_v1 AS m
        JOIN swarm_a_pod_quality AS q ON q.time_us=m.time_us
        WHERE m.time_us>=? AND m.time_us<?
          AND q.is_usable=1 AND m.mean_semi_major_axis_m>0
        GROUP BY minute_us,q.chunk_id
        ORDER BY minute_us,q.chunk_id
    """, (
        HALF_MINUTE_US,
        MINUTE_US,
        MINUTE_US,
        start_time_us - HALF_MINUTE_US,
        end_time_us + HALF_MINUTE_US,
    )).fetchall()
    grouped: dict[int, list[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault(int(row[0]), []).append(row)
    return {
        time_us: (int(group[0][1]), float(group[0][2]))
        for time_us, group in grouped.items()
        if len(group) == 1 and int(group[0][3]) == EXPECTED_POD_SAMPLES
    }


def load_joined_minutes() -> list[JoinedMinute]:
    """Input: Phase 7 density and Phase 1R. Output: exact complete minute joins."""
    with closing(read_only(DENSITY)) as density:
        rows = density.execute("""
            SELECT storm_id,time_us,rho_m0_full_phase_kg_m3,
                   rho_ridge_external_kg_m3
            FROM phase7_density_minute_v1
            WHERE paired_sample_count=2
            ORDER BY storm_id,time_us
        """).fetchall()
    with closing(read_only(PHASE1R)) as phase1:
        pod = load_pod_minutes(phase1, int(rows[0][1]), int(rows[-1][1]) + MINUTE_US)
    joined = [
        JoinedMinute(
            row[0],
            int(row[1]),
            pod[int(row[1])][0],
            pod[int(row[1])][1],
            float(row[2]),
            float(row[3]),
        )
        for row in rows
        if int(row[1]) in pod
    ]
    if not joined or {row.storm_id for row in joined} != {row[0] for row in rows}:
        raise ValueError("Phase 7 density/POD exact join lost an event.")
    return joined


def kernel_increments(previous: JoinedMinute, current: JoinedMinute) -> tuple[float, float]:
    """Input: two consecutive minutes. Output: {M0, Ridge} 60-second kernels kg/m."""
    previous_scale = math.sqrt(
        EARTH_GRAVITATIONAL_PARAMETER_M3_S2 * previous.semi_major_axis_m
    )
    current_scale = math.sqrt(
        EARTH_GRAVITATIONAL_PARAMETER_M3_S2 * current.semi_major_axis_m
    )
    return (
        0.5 * (
            previous.rho_m0_kg_m3 * previous_scale
            + current.rho_m0_kg_m3 * current_scale
        ) * MINUTE_S,
        0.5 * (
            previous.rho_ridge_kg_m3 * previous_scale
            + current.rho_ridge_kg_m3 * current_scale
        ) * MINUTE_S,
    )


def integrated_rows(
    rows: list[JoinedMinute], beff_m2_kg: float
) -> tuple[list[tuple], list[tuple]]:
    """Input: joined minutes and fixed B_eff. Output: minute rows and event summaries."""
    minute_rows = []
    event_rows = []
    previous = None
    current_storm = ""
    block_id = 0
    block_start_axis = 0.0
    m0_kernel = 0.0
    ridge_kernel = 0.0
    observed_offset = 0.0
    m0_offset = 0.0
    ridge_offset = 0.0
    event_start_time = 0
    event_minute_count = 0
    event_block_count = 0

    def finish_event(last_row: JoinedMinute | None) -> None:
        """Input: final minute of one storm. Output: appended event summary row."""
        if last_row is None:
            return
        observed = observed_offset + last_row.semi_major_axis_m - block_start_axis
        predicted_m0 = m0_offset - beff_m2_kg * m0_kernel
        predicted_ridge = ridge_offset - beff_m2_kg * ridge_kernel
        event_rows.append((
            current_storm,
            event_start_time,
            last_row.time_us,
            event_minute_count,
            event_block_count,
            observed,
            predicted_m0,
            predicted_m0 - observed,
            predicted_ridge,
            predicted_ridge - observed,
            "ridge" if abs(predicted_ridge - observed) < abs(predicted_m0 - observed) else "m0",
            beff_m2_kg,
            ALGORITHM_VERSION,
        ))

    for current in rows:
        new_event = current.storm_id != current_storm
        contiguous = (
            previous is not None
            and not new_event
            and current.time_us == previous.time_us + MINUTE_US
            and current.chunk_id == previous.chunk_id
        )
        if new_event:
            finish_event(previous)
            current_storm = current.storm_id
            event_start_time = current.time_us
            event_minute_count = 0
            event_block_count = 0
            observed_offset = 0.0
            m0_offset = 0.0
            ridge_offset = 0.0
        elif not contiguous:
            observed_offset += previous.semi_major_axis_m - block_start_axis
            m0_offset += -beff_m2_kg * m0_kernel
            ridge_offset += -beff_m2_kg * ridge_kernel
        if not contiguous:
            block_id += 1
            event_block_count += 1
            block_start_axis = current.semi_major_axis_m
            m0_kernel = 0.0
            ridge_kernel = 0.0
        else:
            m0_increment, ridge_increment = kernel_increments(previous, current)
            m0_kernel += m0_increment
            ridge_kernel += ridge_increment
        observed_block = current.semi_major_axis_m - block_start_axis
        predicted_m0_block = -beff_m2_kg * m0_kernel
        predicted_ridge_block = -beff_m2_kg * ridge_kernel
        minute_rows.append((
            current.storm_id,
            current.time_us,
            current.chunk_id,
            block_id,
            current.semi_major_axis_m,
            current.rho_m0_kg_m3,
            current.rho_ridge_kg_m3,
            observed_block,
            predicted_m0_block,
            predicted_ridge_block,
            observed_offset + observed_block,
            m0_offset + predicted_m0_block,
            ridge_offset + predicted_ridge_block,
            ALGORITHM_VERSION,
        ))
        event_minute_count += 1
        previous = current
    finish_event(previous)
    return minute_rows, event_rows


def create_tables(database: sqlite3.Connection) -> None:
    """Input: empty SQLite connection. Output: Phase 7 decay tables."""
    database.executescript("""
        CREATE TABLE phase7_decay_minute_v1 (
            storm_id TEXT NOT NULL,
            time_us INTEGER NOT NULL,
            chunk_id INTEGER NOT NULL,
            block_id INTEGER NOT NULL,
            mean_semi_major_axis_m REAL NOT NULL,
            rho_m0_kg_m3 REAL NOT NULL,
            rho_ridge_kg_m3 REAL NOT NULL,
            observed_block_delta_a_m REAL NOT NULL,
            predicted_m0_block_delta_a_m REAL NOT NULL,
            predicted_ridge_block_delta_a_m REAL NOT NULL,
            observed_covered_delta_a_m REAL NOT NULL,
            predicted_m0_covered_delta_a_m REAL NOT NULL,
            predicted_ridge_covered_delta_a_m REAL NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id,time_us)
        );
        CREATE TABLE phase7_decay_event_v1 (
            storm_id TEXT PRIMARY KEY,
            start_time_us INTEGER NOT NULL,
            end_time_us INTEGER NOT NULL,
            paired_minute_count INTEGER NOT NULL,
            block_count INTEGER NOT NULL,
            observed_covered_delta_a_m REAL NOT NULL,
            predicted_m0_covered_delta_a_m REAL NOT NULL,
            m0_error_m REAL NOT NULL,
            predicted_ridge_covered_delta_a_m REAL NOT NULL,
            ridge_error_m REAL NOT NULL,
            closer_model TEXT NOT NULL,
            beff_m2_kg REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase7_decay_metadata_v1 (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def write_decay() -> dict[str, int]:
    """Input: Phase 1R, Phase 7 density, fixed Phase 6 B_eff. Output: decay SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    model = load_fixed_model()
    joined = load_joined_minutes()
    minute_rows, event_rows = integrated_rows(joined, model.beff_m2_kg)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=OUTPUT.stem + ".", suffix=".building", dir=OUTPUT.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            create_tables(database)
            database.executemany(
                "INSERT INTO phase7_decay_minute_v1 VALUES (" + ",".join("?" * 14) + ")",
                minute_rows,
            )
            database.executemany(
                "INSERT INTO phase7_decay_event_v1 VALUES (" + ",".join("?" * 13) + ")",
                event_rows,
            )
            database.executemany("INSERT INTO phase7_decay_metadata_v1 VALUES (?,?)", [
                ("algorithm_version", ALGORITHM_VERSION),
                ("phase1r_source", str(PHASE1R)),
                ("density_source", str(DENSITY)),
                ("beff_m2_kg", repr(model.beff_m2_kg)),
                ("integration", "60 s trapezoid; reset at missing minute or chunk change"),
                ("status", "descriptive external-event closure; not drag propagation"),
            ])
            database.commit()
            if (
                len(event_rows) != len(STORM_IDS)
                or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
            ):
                raise ValueError("Phase 7 decay SQLite audit failed.")
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)
    return {"events": len(event_rows), "paired_minutes": len(minute_rows)}


def main() -> None:
    """Input: no command-line arguments. Output: Phase 7 decay summary."""
    print(write_decay())


if __name__ == "__main__":
    main()
