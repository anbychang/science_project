"""Fit the single P6.1 B_eff from one-minute L2 and POD pairs."""

import math
import os
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

EARTH_GRAVITATIONAL_PARAMETER_M3_S2 = 3.986004418e14
MINUTE_US = 60_000_000
MINUTE_S = 60.0
ALGORITHM_VERSION = "phase6_1_global_minute_beff_v1"


@dataclass(frozen=True)
class FitPaths:
    """Input: P6.1 minute pairs and output path. Output: immutable fit paths."""

    pairs: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_1_l2_minute_pairs_v1.sqlite",
    )
    output: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_1_beff_v1.sqlite",
    )


@dataclass(frozen=True)
class MinutePair:
    """Input: one complete minute pair. Output: SI inputs for P6.1 integration."""

    time_us: int
    chunk_id: int
    semi_major_axis_m: float
    density_kg_m3: float


def read_only(path: Path) -> sqlite3.Connection:
    """Input: existing SQLite path. Output: read-only SQLite connection."""
    return sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: empty SQLite connection. Output: P6.1 integral and fit tables."""
    connection.executescript("""
        CREATE TABLE phase6_1_l2_integral_minute_v1 (
            time_us INTEGER PRIMARY KEY,
            interval_start_time_us INTEGER NOT NULL,
            block_index INTEGER NOT NULL,
            chunk_id INTEGER NOT NULL,
            block_start_time_us INTEGER NOT NULL,
            block_start_a_m REAL NOT NULL,
            observed_a_m REAL NOT NULL,
            rho_l2_kg_m3 REAL NOT NULL,
            kernel_increment_kg_m REAL NOT NULL,
            cumulative_kernel_kg_m REAL NOT NULL,
            observed_cumulative_delta_a_m REAL NOT NULL,
            predicted_cumulative_delta_a_m REAL,
            predicted_a_m REAL,
            residual_m REAL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_1_beff_fit_v1 (
            fit_id TEXT PRIMARY KEY,
            beta_eff_m2_kg REAL NOT NULL,
            paired_minute_count INTEGER NOT NULL,
            integral_point_count INTEGER NOT NULL,
            block_count INTEGER NOT NULL,
            mean_absolute_error_m REAL NOT NULL,
            root_mean_square_error_m REAL NOT NULL,
            mean_error_m REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_1_beff_metadata_v1 (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def load_pairs(connection: sqlite3.Connection):
    """Input: P6.1 pair SQLite. Output: ordered complete minute-pair iterator."""
    rows = connection.execute("""
        SELECT time_us,chunk_id,mean_semi_major_axis_m,rho_l2_kg_m3
        FROM phase6_1_l2_pod_minute_pair_v1
        ORDER BY time_us
    """)
    for time_us, chunk_id, semi_major_axis_m, density_kg_m3 in rows:
        yield MinutePair(
            int(time_us), int(chunk_id), float(semi_major_axis_m), float(density_kg_m3),
        )


def kernel_increment(previous: MinutePair, current: MinutePair) -> float:
    """Input: two consecutive minute pairs. Output: trapezoid density kernel kg/m."""
    previous_value = previous.density_kg_m3 * math.sqrt(
        EARTH_GRAVITATIONAL_PARAMETER_M3_S2 * previous.semi_major_axis_m,
    )
    current_value = current.density_kg_m3 * math.sqrt(
        EARTH_GRAVITATIONAL_PARAMETER_M3_S2 * current.semi_major_axis_m,
    )
    return 0.5 * (previous_value + current_value) * MINUTE_S


def store_integral(
    output: sqlite3.Connection,
    pairs,
) -> tuple[int, int, int, float, float]:
    """Input: ordered minute pairs. Output: stored integral and fit sufficient statistics."""
    previous = None
    block_start = None
    block_index = 0
    cumulative_kernel = 0.0
    numerator = 0.0
    denominator = 0.0
    pair_count = 0
    point_count = 0
    batch = []
    for current in pairs:
        pair_count += 1
        is_new_block = (
            previous is None
            or current.chunk_id != previous.chunk_id
            or current.time_us - previous.time_us != MINUTE_US
        )
        if is_new_block:
            block_index += 1
            block_start = current
            cumulative_kernel = 0.0
            previous = current
            continue
        increment = kernel_increment(previous, current)
        if increment <= 0.0 or block_start is None:
            raise ValueError(f"Invalid P6.1 density kernel at {current.time_us}.")
        cumulative_kernel += increment
        observed_delta = current.semi_major_axis_m - block_start.semi_major_axis_m
        numerator += cumulative_kernel * -observed_delta
        denominator += cumulative_kernel * cumulative_kernel
        batch.append((
            current.time_us,
            previous.time_us,
            block_index,
            current.chunk_id,
            block_start.time_us,
            block_start.semi_major_axis_m,
            current.semi_major_axis_m,
            current.density_kg_m3,
            increment,
            cumulative_kernel,
            observed_delta,
            None,
            None,
            None,
            ALGORITHM_VERSION,
        ))
        point_count += 1
        if len(batch) == 10_000:
            output.executemany(
                "INSERT INTO phase6_1_l2_integral_minute_v1 VALUES ("
                + ",".join("?" for _ in range(15)) + ")",
                batch,
            )
            batch.clear()
        previous = current
    output.executemany(
        "INSERT INTO phase6_1_l2_integral_minute_v1 VALUES ("
        + ",".join("?" for _ in range(15)) + ")",
        batch,
    )
    if point_count == 0 or denominator <= 0.0:
        raise ValueError("P6.1 has no valid consecutive minute intervals.")
    return pair_count, point_count, block_index, numerator, denominator


def finish_fit(
    output: sqlite3.Connection,
    beta_eff: float,
) -> tuple[float, float, float]:
    """Input: stored integral and positive B_eff. Output: fitted curve and three error metrics."""
    output.execute("""
        UPDATE phase6_1_l2_integral_minute_v1
        SET predicted_cumulative_delta_a_m = -? * cumulative_kernel_kg_m,
            predicted_a_m = block_start_a_m - ? * cumulative_kernel_kg_m,
            residual_m = -? * cumulative_kernel_kg_m - observed_cumulative_delta_a_m
    """, (beta_eff, beta_eff, beta_eff))
    count, absolute_sum, squared_sum, error_sum = output.execute("""
        SELECT COUNT(*),SUM(ABS(residual_m)),SUM(residual_m * residual_m),SUM(residual_m)
        FROM phase6_1_l2_integral_minute_v1
    """).fetchone()
    return (
        float(absolute_sum) / count,
        math.sqrt(float(squared_sum) / count),
        float(error_sum) / count,
    )


def write_fit(paths: FitPaths) -> dict[str, float | int]:
    """Input: P6.1 minute-pair SQLite. Output: new B_eff fit SQLite and summary."""
    if paths.output.exists():
        raise FileExistsError(f"Refusing to overwrite existing Phase 6 output: {paths.output}")
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = paths.output.with_suffix(".part")
    temporary.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(temporary)) as output:
            create_tables(output)
            with closing(read_only(paths.pairs)) as pairs_database:
                statistics = store_integral(output, load_pairs(pairs_database))
            pair_count, point_count, block_count, numerator, denominator = statistics
            beta_eff = numerator / denominator
            if beta_eff <= 0.0 or not math.isfinite(beta_eff):
                raise ValueError(f"P6.1 B_eff is not positive and finite: {beta_eff}")
            mae_m, rmse_m, mean_error_m = finish_fit(output, beta_eff)
            output.execute(
                "INSERT INTO phase6_1_beff_fit_v1 VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    "all_three_year_minute_points",
                    beta_eff,
                    pair_count,
                    point_count,
                    block_count,
                    mae_m,
                    rmse_m,
                    mean_error_m,
                    ALGORITHM_VERSION,
                ),
            )
            output.executemany(
                "INSERT INTO phase6_1_beff_metadata_v1 VALUES (?,?)",
                [
                    ("algorithm_version", ALGORITHM_VERSION),
                    ("pair_database", str(paths.pairs)),
                    ("fit", "one zero-intercept global B_eff over cumulative minute points"),
                    ("integration", "60 s trapezoid rule; reset at missing minute or chunk change"),
                    ("objective", "estimate B_eff only"),
                    ("limitation", "descriptive in-sample POD-dependent closure"),
                ],
            )
            output.commit()
        os.replace(temporary, paths.output)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "beta_eff_m2_kg": beta_eff,
        "paired_minute_count": pair_count,
        "integral_point_count": point_count,
        "block_count": block_count,
        "mae_m": mae_m,
        "rmse_m": rmse_m,
    }


def run(paths: FitPaths = FitPaths()) -> dict[str, float | int]:
    """Input: default P6.1 pair SQLite. Output: one global minute B_eff fit."""
    return write_fit(paths)


def main() -> None:
    """Input: no command-line arguments. Output: P6.1 B_eff summary."""
    if sys.argv[1:]:
        raise SystemExit("Usage: python -m phases.phase6.code.calc_phase6_1_beff")
    print(run())


if __name__ == "__main__":
    main()
