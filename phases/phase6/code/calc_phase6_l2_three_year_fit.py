"""Fit one global beta_eff between three-year L2 integral and POD semi-major axis."""

import math
import os
import sqlite3
import sys
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass, replace
from pathlib import Path

from phases.phase6.code.calc_phase6_l2_density_decay import (
    EARTH_GRAVITATIONAL_PARAMETER_M3_S2,
    MICROSECONDS_PER_SECOND,
    read_only,
)


MAXIMUM_ORBIT_GAP_S = 6_000.0
ALGORITHM_VERSION = "phase6_l2_three_year_global_cumulative_fit_v1"


@dataclass(frozen=True)
class FitPaths:
    """Input: three-year pair and output paths. Output: immutable global-fit paths."""

    pairs: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_l2_three_year_pairs_v1.sqlite",
    )
    output: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_l2_three_year_fit_v1.sqlite",
    )


@dataclass(frozen=True)
class PairedOrbit:
    """Input: one paired Phase 1 orbit and L2 orbit-mean density.
    Output: ordered SI values for integration."""

    time_us: int
    semi_major_axis_m: float
    chunk_id: int
    density_time_us: int
    density_kg_m3: float


@dataclass(frozen=True)
class IntegralPoint:
    """Input: one valid orbit interval. Output: cumulative L2 kernel and POD change."""

    time_us: int
    interval_start_time_us: int
    block_index: int
    chunk_id: int
    block_start_time_us: int
    block_start_a_m: float
    observed_a_m: float
    density_time_us: int
    density_kg_m3: float
    interval_s: float
    kernel_increment_kg_m: float
    cumulative_kernel_kg_m: float
    observed_cumulative_delta_a_m: float
    beta_eff_m2_kg: float = 0.0
    predicted_cumulative_delta_a_m: float = 0.0
    predicted_a_m: float = 0.0
    residual_m: float = 0.0


@dataclass(frozen=True)
class GlobalFit:
    """Input: all valid cumulative points. Output: one global beta_eff and fit metrics."""

    beta_eff_m2_kg: float
    point_count: int
    block_count: int
    mean_absolute_error_m: float
    root_mean_square_error_m: float
    mean_error_m: float


@dataclass(frozen=True)
class BlockSummary:
    """Input: one continuous cumulative block. Output: endpoint fit summary."""

    block_index: int
    chunk_id: int
    start_time_us: int
    stop_time_us: int
    point_count: int
    cumulative_kernel_kg_m: float
    observed_delta_a_m: float
    predicted_delta_a_m: float
    prediction_error_m: float


def load_pairs(connection: sqlite3.Connection) -> list[PairedOrbit]:
    """Input: three-year pair SQLite. Output: ordered paired orbit-density rows."""
    rows = connection.execute("""
        SELECT time_us,mean_semi_major_axis_m,chunk_id,density_time_us,
               rho_l2_orbitmean_kg_m3
        FROM phase6_l2_three_year_pair_v1
        ORDER BY time_us
    """).fetchall()
    pairs = [
        PairedOrbit(int(time_us), float(a_m), int(chunk_id), int(density_time_us), float(rho))
        for time_us, a_m, chunk_id, density_time_us, rho in rows
    ]
    if len(pairs) < 2:
        raise ValueError("Three-year L2 fitting needs at least two paired orbits.")
    return pairs


def build_integral_points(pairs: list[PairedOrbit]) -> list[IntegralPoint]:
    """Input: ordered three-year pairs. Output: gap-safe cumulative integration points."""
    points = []
    block_index = 0
    block_start: PairedOrbit | None = None
    cumulative_kernel = 0.0
    previous: PairedOrbit | None = None
    for current in pairs:
        interval_s = None if previous is None else (
            current.time_us - previous.time_us
        ) / MICROSECONDS_PER_SECOND
        new_block = previous is None or (
            current.chunk_id != previous.chunk_id
            or interval_s is None
            or not 0.0 < interval_s <= MAXIMUM_ORBIT_GAP_S
        )
        if new_block:
            block_index += 1
            block_start = current
            cumulative_kernel = 0.0
            previous = current
            continue
        kernel_increment = (
            previous.density_kg_m3
            * math.sqrt(
                EARTH_GRAVITATIONAL_PARAMETER_M3_S2 * previous.semi_major_axis_m,
            )
            * interval_s
        )
        if kernel_increment <= 0.0 or block_start is None:
            raise ValueError(f"Invalid density kernel at orbit {current.time_us}.")
        cumulative_kernel += kernel_increment
        points.append(IntegralPoint(
            time_us=current.time_us,
            interval_start_time_us=previous.time_us,
            block_index=block_index,
            chunk_id=current.chunk_id,
            block_start_time_us=block_start.time_us,
            block_start_a_m=block_start.semi_major_axis_m,
            observed_a_m=current.semi_major_axis_m,
            density_time_us=previous.density_time_us,
            density_kg_m3=previous.density_kg_m3,
            interval_s=interval_s,
            kernel_increment_kg_m=kernel_increment,
            cumulative_kernel_kg_m=cumulative_kernel,
            observed_cumulative_delta_a_m=(
                current.semi_major_axis_m - block_start.semi_major_axis_m
            ),
        ))
        previous = current
    if not points:
        raise ValueError("Three-year pairs contain no valid consecutive orbit intervals.")
    return points


def fit_global_beta(points: list[IntegralPoint]) -> float:
    """Input: all cumulative L2 kernels and POD changes. Output: one zero-intercept beta_eff."""
    denominator = sum(point.cumulative_kernel_kg_m ** 2 for point in points)
    if denominator <= 0.0:
        raise ValueError("Global beta_eff fit has no positive cumulative kernel.")
    numerator = sum(
        point.cumulative_kernel_kg_m * (-point.observed_cumulative_delta_a_m)
        for point in points
    )
    beta_eff = numerator / denominator
    if beta_eff <= 0.0 or not math.isfinite(beta_eff):
        raise ValueError(f"Global beta_eff is not positive and finite: {beta_eff}")
    return beta_eff


def apply_global_beta(points: list[IntegralPoint], beta_eff: float) -> list[IntegralPoint]:
    """Input: cumulative integration points and beta_eff. Output: predicted POD-scale curve."""
    fitted = []
    for point in points:
        predicted_delta = -beta_eff * point.cumulative_kernel_kg_m
        fitted.append(replace(
            point,
            beta_eff_m2_kg=beta_eff,
            predicted_cumulative_delta_a_m=predicted_delta,
            predicted_a_m=point.block_start_a_m + predicted_delta,
            residual_m=predicted_delta - point.observed_cumulative_delta_a_m,
        ))
    return fitted


def fit_metrics(points: list[IntegralPoint]) -> GlobalFit:
    """Input: fitted cumulative points. Output: one descriptive global fit record."""
    errors = [point.residual_m for point in points]
    return GlobalFit(
        beta_eff_m2_kg=points[0].beta_eff_m2_kg,
        point_count=len(points),
        block_count=len({point.block_index for point in points}),
        mean_absolute_error_m=sum(map(abs, errors)) / len(errors),
        root_mean_square_error_m=math.sqrt(sum(error * error for error in errors) / len(errors)),
        mean_error_m=sum(errors) / len(errors),
    )


def block_summaries(points: list[IntegralPoint]) -> list[BlockSummary]:
    """Input: fitted cumulative points. Output: one endpoint summary per continuous block."""
    grouped: dict[int, list[IntegralPoint]] = defaultdict(list)
    for point in points:
        grouped[point.block_index].append(point)
    summaries = []
    for block_index, block in sorted(grouped.items()):
        last = block[-1]
        summaries.append(BlockSummary(
            block_index=block_index,
            chunk_id=last.chunk_id,
            start_time_us=last.block_start_time_us,
            stop_time_us=last.time_us,
            point_count=len(block),
            cumulative_kernel_kg_m=last.cumulative_kernel_kg_m,
            observed_delta_a_m=last.observed_cumulative_delta_a_m,
            predicted_delta_a_m=last.predicted_cumulative_delta_a_m,
            prediction_error_m=last.residual_m,
        ))
    return summaries


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: empty Phase 6 SQLite connection. Output: global integral-fit tables."""
    connection.executescript("""
        CREATE TABLE phase6_l2_three_year_integral_v1 (
            time_us INTEGER PRIMARY KEY,
            interval_start_time_us INTEGER NOT NULL,
            block_index INTEGER NOT NULL,
            chunk_id INTEGER NOT NULL,
            block_start_time_us INTEGER NOT NULL,
            block_start_a_m REAL NOT NULL,
            observed_a_m REAL NOT NULL,
            density_time_us INTEGER NOT NULL,
            rho_l2_orbitmean_kg_m3 REAL NOT NULL,
            interval_s REAL NOT NULL,
            kernel_increment_kg_m REAL NOT NULL,
            cumulative_kernel_kg_m REAL NOT NULL,
            observed_cumulative_delta_a_m REAL NOT NULL,
            beta_eff_m2_kg REAL NOT NULL,
            predicted_cumulative_delta_a_m REAL NOT NULL,
            predicted_a_m REAL NOT NULL,
            residual_m REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_l2_three_year_block_v1 (
            block_index INTEGER PRIMARY KEY,
            chunk_id INTEGER NOT NULL,
            start_time_us INTEGER NOT NULL,
            stop_time_us INTEGER NOT NULL,
            point_count INTEGER NOT NULL,
            cumulative_kernel_kg_m REAL NOT NULL,
            observed_delta_a_m REAL NOT NULL,
            predicted_delta_a_m REAL NOT NULL,
            prediction_error_m REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_l2_three_year_fit_v1 (
            fit_id TEXT PRIMARY KEY,
            beta_eff_m2_kg REAL NOT NULL,
            point_count INTEGER NOT NULL,
            block_count INTEGER NOT NULL,
            mean_absolute_error_m REAL NOT NULL,
            root_mean_square_error_m REAL NOT NULL,
            mean_error_m REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_l2_three_year_fit_metadata_v1 (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def write_fit(
    paths: FitPaths,
    points: list[IntegralPoint],
    metrics: GlobalFit,
) -> None:
    """Input: fitted points, metrics, and output path. Output: new immutable fit SQLite."""
    if paths.output.exists():
        raise FileExistsError(f"Refusing to overwrite existing Phase 6 output: {paths.output}")
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = paths.output.with_suffix(".part")
    if temporary.exists():
        temporary.unlink()
    summaries = block_summaries(points)
    try:
        with closing(sqlite3.connect(temporary)) as output:
            create_tables(output)
            output.executemany(
                "INSERT INTO phase6_l2_three_year_integral_v1 VALUES ("
                + ",".join("?" for _ in range(18)) + ")",
                [(
                    point.time_us,
                    point.interval_start_time_us,
                    point.block_index,
                    point.chunk_id,
                    point.block_start_time_us,
                    point.block_start_a_m,
                    point.observed_a_m,
                    point.density_time_us,
                    point.density_kg_m3,
                    point.interval_s,
                    point.kernel_increment_kg_m,
                    point.cumulative_kernel_kg_m,
                    point.observed_cumulative_delta_a_m,
                    point.beta_eff_m2_kg,
                    point.predicted_cumulative_delta_a_m,
                    point.predicted_a_m,
                    point.residual_m,
                    ALGORITHM_VERSION,
                ) for point in points],
            )
            output.executemany(
                "INSERT INTO phase6_l2_three_year_block_v1 VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(
                    block.block_index,
                    block.chunk_id,
                    block.start_time_us,
                    block.stop_time_us,
                    block.point_count,
                    block.cumulative_kernel_kg_m,
                    block.observed_delta_a_m,
                    block.predicted_delta_a_m,
                    block.prediction_error_m,
                    ALGORITHM_VERSION,
                ) for block in summaries],
            )
            output.execute(
                "INSERT INTO phase6_l2_three_year_fit_v1 VALUES (?,?,?,?,?,?,?,?)",
                (
                    "all_three_year_cumulative_points",
                    metrics.beta_eff_m2_kg,
                    metrics.point_count,
                    metrics.block_count,
                    metrics.mean_absolute_error_m,
                    metrics.root_mean_square_error_m,
                    metrics.mean_error_m,
                    ALGORITHM_VERSION,
                ),
            )
            output.executemany(
                "INSERT INTO phase6_l2_three_year_fit_metadata_v1 VALUES (?,?)",
                [
                    ("algorithm_version", ALGORITHM_VERSION),
                    ("pair_database", str(paths.pairs)),
                    ("fit", "one zero-intercept beta_eff over all cumulative three-year points"),
                    ("gap_rule", "reset at chunk change or orbit interval outside (0,6000] s"),
                    ("limitation", "descriptive in-sample fit; L2 and semi-major axis both use POD"),
                ],
            )
            output.commit()
        os.replace(temporary, paths.output)
    finally:
        temporary.unlink(missing_ok=True)


def run(paths: FitPaths = FitPaths()) -> dict[str, float | int]:
    """Input: default three-year pair SQLite. Output: new global-fit SQLite and summary."""
    with closing(read_only(paths.pairs)) as pairs_database:
        pairs = load_pairs(pairs_database)
    points = build_integral_points(pairs)
    fitted = apply_global_beta(points, fit_global_beta(points))
    metrics = fit_metrics(fitted)
    write_fit(paths, fitted, metrics)
    return {
        "beta_eff_m2_kg": metrics.beta_eff_m2_kg,
        "pair_count": len(pairs),
        "integral_point_count": metrics.point_count,
        "block_count": metrics.block_count,
        "rmse_m": metrics.root_mean_square_error_m,
    }


def main() -> None:
    """Input: no command-line arguments. Output: three-year global-fit SQLite summary."""
    if sys.argv[1:]:
        raise SystemExit("Usage: python -m phases.phase6.code.calc_phase6_l2_three_year_fit")
    print(run())


if __name__ == "__main__":
    main()
