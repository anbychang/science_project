"""Measure quiet-window semi-major-axis sensitivity to endpoint fit length."""

import os
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from math import sqrt
from pathlib import Path

from phases.phase6.code.calc_phase6_quiet_closure import (
    OrbitDensityPair,
    load_window_pairs,
)


DEFAULT_AUDIT_DATABASE = Path(
    "phases/phase6/data/sqlite/swarm_a_phase6_quiet_audit_v1.sqlite",
)
DEFAULT_OUTPUT = Path(
    "phases/phase6/data/sqlite/swarm_a_phase6_quiet_endpoint_sensitivity_v1.sqlite",
)
ENDPOINT_ORBIT_COUNTS = (4, 6, 8)
REFERENCE_ENDPOINT_ORBIT_COUNT = 6
ALGORITHM_VERSION = "phase6_quiet_endpoint_sensitivity_v1"


@dataclass(frozen=True)
class SensitivityPaths:
    """Input: quiet-audit SQLite path and new sensitivity SQLite path.
    Output: immutable Phase 6 sensitivity path record."""

    audit_database: Path = DEFAULT_AUDIT_DATABASE
    output: Path = DEFAULT_OUTPUT


@dataclass(frozen=True)
class EndpointEstimate:
    """Input: endpoint-fit semi-major-axis change and OLS uncertainty.
    Output: one fitted change record in m."""

    delta_a_m: float
    ols_sigma_m: float


@dataclass(frozen=True)
class SensitivityMeasure:
    """Input: one candidate window's 4/6/8-orbit endpoint fits.
    Output: reference uncertainty and endpoint-choice span in m."""

    window_id: str
    delta_a_4_m: float
    delta_a_6_m: float
    delta_a_8_m: float
    delta_a_ols_sigma_6_m: float
    delta_a_endpoint_span_m: float


def fitted_value_and_sigma(
    samples: list[OrbitDensityPair],
    target_time_us: int,
) -> tuple[float, float]:
    """Input: at least three orbit samples and a target UTC time.
    Output: fitted semi-major axis and OLS prediction sigma in m."""
    if len(samples) < 3:
        raise ValueError("Endpoint fit needs at least three orbit samples.")
    mean_time_us = sum(sample.time_us for sample in samples) / len(samples)
    mean_a_m = sum(sample.semi_major_axis_m for sample in samples) / len(samples)
    time_variance = sum((sample.time_us - mean_time_us) ** 2 for sample in samples)
    if time_variance == 0.0:
        raise ValueError("Endpoint fit has no time variation.")
    slope_m_per_us = sum(
        (sample.time_us - mean_time_us) * (sample.semi_major_axis_m - mean_a_m)
        for sample in samples
    ) / time_variance
    fitted = [
        mean_a_m + slope_m_per_us * (sample.time_us - mean_time_us)
        for sample in samples
    ]
    residual_sum_squares = sum(
        (sample.semi_major_axis_m - estimate) ** 2
        for sample, estimate in zip(samples, fitted)
    )
    residual_variance = residual_sum_squares / (len(samples) - 2)
    leverage = 1 / len(samples) + (target_time_us - mean_time_us) ** 2 / time_variance
    fitted_value = mean_a_m + slope_m_per_us * (target_time_us - mean_time_us)
    return fitted_value, sqrt(residual_variance * leverage)


def endpoint_estimate(
    samples: list[OrbitDensityPair],
    endpoint_orbit_count: int,
) -> EndpointEstimate:
    """Input: ordered orbit-density samples and one endpoint fit length.
    Output: fitted window semi-major-axis change and OLS sigma in m."""
    if len(samples) < 2 * endpoint_orbit_count:
        raise ValueError(
            f"Need {2 * endpoint_orbit_count} samples for {endpoint_orbit_count}-orbit endpoints.",
        )
    start_a_m, start_sigma_m = fitted_value_and_sigma(
        samples[:endpoint_orbit_count], samples[0].time_us,
    )
    end_a_m, end_sigma_m = fitted_value_and_sigma(
        samples[-endpoint_orbit_count:], samples[-1].time_us,
    )
    return EndpointEstimate(
        delta_a_m=end_a_m - start_a_m,
        ols_sigma_m=sqrt(start_sigma_m ** 2 + end_sigma_m ** 2),
    )


def measure_window_sensitivity(
    window_id: str,
    samples: list[OrbitDensityPair],
) -> SensitivityMeasure:
    """Input: one window ID and ordered orbit-density samples.
    Output: 4/6/8-orbit changes, 6-orbit OLS sigma, and endpoint-choice span."""
    estimates = {
        orbit_count: endpoint_estimate(samples, orbit_count)
        for orbit_count in ENDPOINT_ORBIT_COUNTS
    }
    deltas = [estimate.delta_a_m for estimate in estimates.values()]
    return SensitivityMeasure(
        window_id=window_id,
        delta_a_4_m=estimates[4].delta_a_m,
        delta_a_6_m=estimates[6].delta_a_m,
        delta_a_8_m=estimates[8].delta_a_m,
        delta_a_ols_sigma_6_m=estimates[REFERENCE_ENDPOINT_ORBIT_COUNT].ols_sigma_m,
        delta_a_endpoint_span_m=max(deltas) - min(deltas),
    )


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: empty Phase 6 sensitivity SQLite connection.
    Output: versioned endpoint-sensitivity and metadata tables."""
    connection.executescript("""
        CREATE TABLE phase6_quiet_endpoint_sensitivity_v1 (
            window_id TEXT PRIMARY KEY,
            delta_a_4_m REAL NOT NULL,
            delta_a_6_m REAL NOT NULL,
            delta_a_8_m REAL NOT NULL,
            delta_a_ols_sigma_6_m REAL NOT NULL,
            delta_a_endpoint_span_m REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_quiet_endpoint_sensitivity_metadata_v1 (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def write_sensitivity(paths: SensitivityPaths, measures: list[SensitivityMeasure]) -> None:
    """Input: Phase 6 paths and sensitivity measures.
    Output: a new SQLite sensitivity result without modifying quiet-audit records."""
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
                "INSERT INTO phase6_quiet_endpoint_sensitivity_v1 VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        measure.window_id, measure.delta_a_4_m, measure.delta_a_6_m,
                        measure.delta_a_8_m, measure.delta_a_ols_sigma_6_m,
                        measure.delta_a_endpoint_span_m, ALGORITHM_VERSION,
                    )
                    for measure in measures
                ],
            )
            output.executemany(
                "INSERT INTO phase6_quiet_endpoint_sensitivity_metadata_v1 VALUES (?, ?)",
                [
                    ("algorithm_version", ALGORITHM_VERSION),
                    ("quiet_audit_database", str(paths.audit_database)),
                    ("endpoint_orbit_counts", ",".join(map(str, ENDPOINT_ORBIT_COUNTS))),
                    ("reference_endpoint_orbit_count", str(REFERENCE_ENDPOINT_ORBIT_COUNT)),
                    ("limitation", "OLS sigma excludes shared systematic POD and maneuver uncertainty"),
                ],
            )
            output.commit()
        os.replace(temporary_path, paths.output)
    finally:
        temporary_path.unlink(missing_ok=True)


def run() -> dict[str, int]:
    """Input: default Phase 6 quiet-audit SQLite.
    Output: a new endpoint-sensitivity SQLite and candidate-window count."""
    paths = SensitivityPaths()
    with closing(sqlite3.connect(paths.audit_database)) as audit:
        pairs_by_window = load_window_pairs(audit)
    measures = [
        measure_window_sensitivity(window_id, samples)
        for window_id, samples in pairs_by_window.items()
    ]
    write_sensitivity(paths, measures)
    return {"window_count": len(measures)}


def main() -> None:
    """Input: no command-line arguments.
    Output: one new Phase 6 sensitivity SQLite or an actionable failure."""
    if sys.argv[1:]:
        raise SystemExit("Usage: python -m phases.phase6.code.calc_phase6_quiet_endpoint_sensitivity")
    print(run())


if __name__ == "__main__":
    main()
