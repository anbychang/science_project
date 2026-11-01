"""Test whether quiet-period density can reproduce candidate semi-major-axis decline."""

import os
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from statistics import median


DEFAULT_AUDIT_DATABASE = Path(
    "phases/phase6/data/sqlite/swarm_a_phase6_quiet_audit_v1.sqlite",
)
DEFAULT_OUTPUT = Path(
    "phases/phase6/data/sqlite/swarm_a_phase6_quiet_closure_v4.sqlite",
)
EARTH_GRAVITATIONAL_PARAMETER_M3_S2 = 3.986004418e14
ENDPOINT_ORBIT_COUNT = 6
MICROSECONDS_PER_SECOND = 1_000_000
MAXIMUM_ORBIT_GAP_S = 6_000.0
ALGORITHM_VERSION = "phase6_quiet_nonoverlap_leave_one_window_out_v4"


@dataclass(frozen=True)
class ClosurePaths:
    """Input: quiet-audit SQLite path and new closure SQLite path.
    Output: immutable Phase 6 closure path record."""

    audit_database: Path = DEFAULT_AUDIT_DATABASE
    output: Path = DEFAULT_OUTPUT


@dataclass(frozen=True)
class OrbitDensityPair:
    """Input: one paired orbit mean and DNSAPOD orbit-mean density.
    Output: integration sample with UTC and SI values."""

    time_us: int
    semi_major_axis_m: float
    density_kg_m3: float


@dataclass(frozen=True)
class WindowMeasure:
    """Input: one candidate window's fitted change and density integral.
    Output: leave-one-window-out closure inputs and result fields."""

    window_id: str
    first_time_us: int
    last_time_us: int
    observed_delta_a_m: float
    density_kernel_kg_m: float
    empirical_scale_m2_kg: float | None
    calibration_window_count: int | None = None
    predicted_delta_a_m: float | None = None
    prediction_error_m: float | None = None
    status: str = "not_evaluated"


def load_window_pairs(connection: sqlite3.Connection) -> dict[str, list[OrbitDensityPair]]:
    """Input: Phase 6 quiet-audit SQLite connection.
    Output: candidate window ID -> ordered paired orbit-density samples."""
    rows = connection.execute("""
        SELECT pair.window_id, pair.time_us, pair.mean_semi_major_axis_m,
               pair.rho_l2_orbitmean_kg_m3
        FROM phase6_quiet_orbit_pair_v1 AS pair
        JOIN phase6_quiet_window_v1 AS window ON window.window_id = pair.window_id
        WHERE window.selection_status = 'candidate'
        ORDER BY pair.window_id, pair.time_us
    """)
    pairs_by_window: dict[str, list[OrbitDensityPair]] = {}
    for window_id, time_us, semi_major_axis_m, density_kg_m3 in rows:
        pairs_by_window.setdefault(str(window_id), []).append(
            OrbitDensityPair(int(time_us), float(semi_major_axis_m), float(density_kg_m3)),
        )
    if not pairs_by_window:
        raise ValueError("Quiet audit has no candidate orbit-density pairs.")
    return pairs_by_window


def linear_fitted_value(samples: list[OrbitDensityPair], target_time_us: int) -> float:
    """Input: at least two orbit samples and a target UTC time.
    Output: least-squares semi-major-axis value at the target in m."""
    if len(samples) < 2:
        raise ValueError("Endpoint fit needs at least two orbit samples.")
    mean_time_us = sum(sample.time_us for sample in samples) / len(samples)
    mean_a_m = sum(sample.semi_major_axis_m for sample in samples) / len(samples)
    time_variance = sum((sample.time_us - mean_time_us) ** 2 for sample in samples)
    if time_variance == 0.0:
        raise ValueError("Endpoint fit has no time variation.")
    covariance = sum(
        (sample.time_us - mean_time_us) * (sample.semi_major_axis_m - mean_a_m)
        for sample in samples
    )
    slope_m_per_us = covariance / time_variance
    return mean_a_m + slope_m_per_us * (target_time_us - mean_time_us)


def density_integration_kernel(samples: list[OrbitDensityPair]) -> float:
    """Input: ordered orbit-density samples within one candidate window.
    Output: positive density integral in kg/m before empirical-scale multiplication."""
    if len(samples) < 2:
        raise ValueError("Density integration needs at least two orbit samples.")
    kernel = 0.0
    for left, right in zip(samples, samples[1:]):
        interval_s = (right.time_us - left.time_us) / MICROSECONDS_PER_SECOND
        if not 0.0 < interval_s <= MAXIMUM_ORBIT_GAP_S:
            raise ValueError(f"Orbit interval outside closure limit: {interval_s} s.")
        kernel += (
            left.density_kg_m3
            * sqrt(EARTH_GRAVITATIONAL_PARAMETER_M3_S2 * left.semi_major_axis_m)
            * interval_s
        )
    if kernel <= 0.0:
        raise ValueError("Density integration kernel is not positive.")
    return kernel


def measure_window(window_id: str, samples: list[OrbitDensityPair]) -> WindowMeasure:
    """Input: one window ID and ordered paired orbit-density samples.
    Output: fitted observed change, density kernel, and an empirical scale when descending."""
    if len(samples) < 2 * ENDPOINT_ORBIT_COUNT:
        raise ValueError(f"{window_id} has fewer than {2 * ENDPOINT_ORBIT_COUNT} orbit samples.")
    first_time_us = samples[0].time_us
    last_time_us = samples[-1].time_us
    fitted_start_a_m = linear_fitted_value(samples[:ENDPOINT_ORBIT_COUNT], first_time_us)
    fitted_end_a_m = linear_fitted_value(samples[-ENDPOINT_ORBIT_COUNT:], last_time_us)
    observed_delta_a_m = fitted_end_a_m - fitted_start_a_m
    kernel = density_integration_kernel(samples)
    scale = -observed_delta_a_m / kernel if observed_delta_a_m < 0.0 else None
    return WindowMeasure(
        window_id=window_id,
        first_time_us=first_time_us,
        last_time_us=last_time_us,
        observed_delta_a_m=observed_delta_a_m,
        density_kernel_kg_m=kernel,
        empirical_scale_m2_kg=scale,
    )


def windows_overlap(left: WindowMeasure, right: WindowMeasure) -> bool:
    """Input: two candidate window time ranges.
    Output: whether their fitted first-to-last orbit intervals overlap."""
    return left.first_time_us < right.last_time_us and right.first_time_us < left.last_time_us


def leave_one_window_out(measures: list[WindowMeasure]) -> list[WindowMeasure]:
    """Input: all candidate window measures.
    Output: each descending window predicted from non-overlapping windows' median scale."""
    evaluated = []
    for target in measures:
        calibration_scales = [
            source.empirical_scale_m2_kg
            for source in measures
            if (
                source.window_id != target.window_id
                and source.empirical_scale_m2_kg is not None
                and not windows_overlap(source, target)
            )
        ]
        if target.empirical_scale_m2_kg is None:
            evaluated.append(
                WindowMeasure(**{**target.__dict__, "status": "not_descending"}),
            )
            continue
        if not calibration_scales:
            evaluated.append(
                WindowMeasure(**{**target.__dict__, "status": "no_nonoverlapping_calibration_windows"}),
            )
            continue
        calibration_scale = median(calibration_scales)
        predicted_delta_a_m = -calibration_scale * target.density_kernel_kg_m
        evaluated.append(WindowMeasure(
            **{
                **target.__dict__,
                "calibration_window_count": len(calibration_scales),
                "predicted_delta_a_m": predicted_delta_a_m,
                "prediction_error_m": predicted_delta_a_m - target.observed_delta_a_m,
                "status": "evaluated",
            },
        ))
    return evaluated


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: empty Phase 6 closure SQLite connection.
    Output: versioned closure and metadata tables."""
    connection.executescript("""
        CREATE TABLE phase6_quiet_closure_window_v4 (
            window_id TEXT PRIMARY KEY,
            first_time_us INTEGER NOT NULL,
            last_time_us INTEGER NOT NULL,
            observed_delta_a_m REAL NOT NULL,
            density_kernel_kg_m REAL NOT NULL,
            empirical_scale_m2_kg REAL,
            calibration_window_count INTEGER,
            predicted_delta_a_m REAL,
            prediction_error_m REAL,
            status TEXT NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_quiet_closure_metadata_v4 (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def write_closure(paths: ClosurePaths, measures: list[WindowMeasure]) -> None:
    """Input: Phase 6 paths and evaluated closure measures.
    Output: a new SQLite closure result without modifying quiet-audit records."""
    if paths.output.exists():
        raise FileExistsError(f"Refusing to overwrite existing Phase 6 output: {paths.output}")
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = paths.output.with_suffix(".part")
    if temporary_path.exists():
        temporary_path.unlink()
    try:
        with closing(sqlite3.connect(temporary_path)) as output:
            create_tables(output)
            output.executemany(
                "INSERT INTO phase6_quiet_closure_window_v4 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        measure.window_id, measure.first_time_us, measure.last_time_us,
                        measure.observed_delta_a_m, measure.density_kernel_kg_m,
                        measure.empirical_scale_m2_kg, measure.calibration_window_count,
                        measure.predicted_delta_a_m, measure.prediction_error_m,
                        measure.status, ALGORITHM_VERSION,
                    )
                    for measure in measures
                ],
            )
            output.executemany(
                "INSERT INTO phase6_quiet_closure_metadata_v4 VALUES (?, ?)",
                [
                    ("algorithm_version", ALGORITHM_VERSION),
                    ("quiet_audit_database", str(paths.audit_database)),
                    ("endpoint_orbit_count", str(ENDPOINT_ORBIT_COUNT)),
                    ("maximum_orbit_gap_s", str(MAXIMUM_ORBIT_GAP_S)),
                    ("evaluation", "leave-one-non-overlapping-window-out median empirical scale"),
                    ("limitation", "descriptive candidate semi-major-axis closure, not physical drag calibration"),
                ],
            )
            output.commit()
        os.replace(temporary_path, paths.output)
    finally:
        temporary_path.unlink(missing_ok=True)


def run() -> dict[str, int]:
    """Input: default Phase 6 quiet-audit SQLite.
    Output: a new closure SQLite and counts by evaluation status."""
    paths = ClosurePaths()
    with closing(sqlite3.connect(paths.audit_database)) as audit:
        pairs_by_window = load_window_pairs(audit)
    measures = leave_one_window_out([
        measure_window(window_id, samples)
        for window_id, samples in pairs_by_window.items()
    ])
    write_closure(paths, measures)
    return {
        "window_count": len(measures),
        "evaluated_window_count": sum(measure.status == "evaluated" for measure in measures),
        "descending_window_count": sum(measure.observed_delta_a_m < 0.0 for measure in measures),
    }


def main() -> None:
    """Input: no command-line arguments.
    Output: one new Phase 6 quiet-closure SQLite or an actionable failure."""
    if sys.argv[1:]:
        raise SystemExit("Usage: python -m phases.phase6.code.calc_phase6_quiet_closure")
    print(run())


if __name__ == "__main__":
    main()
