"""Calibrate one quiet-density decay scale in 2024 and check it in 2026."""

import os
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from math import sqrt
from pathlib import Path
from statistics import fmean

from phases.phase0.code.calculation.density.calc_msis_p2_4 import (
    calculate_msis_density,
)
from phases.phase0.code.data.density.load_dnsapod import load_dnsapod


DEFAULT_PHASE1_DATABASE = Path(
    "phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite",
)
DEFAULT_DENSITY_FOLDER = Path("phases/phase0/data/raw/swarm_density_pod")
DEFAULT_OUTPUT = Path(
    "phases/phase6/data/sqlite/swarm_a_phase6_paper_msis_scale_check_v1.sqlite",
)
CALIBRATION_DAY = date(2024, 5, 4)
VALIDATION_DAY = date(2026, 1, 31)
PUBLISHED_2024_RATE_M_DAY = 19.91
PUBLISHED_2026_RATE_M_DAY = 79.43
QUIET_AP = 4.0
DAY_SECONDS = 86_400.0
EARTH_MU_M3_S2 = 3.986004418e14
ALGORITHM_VERSION = "phase6_paper_msis_scale_check_v1"


@dataclass(frozen=True)
class ScaleCheckPaths:
    """Input: Phase 1, DNSAPOD, and output paths.
    Output: immutable paths for the two-date scale check."""

    phase1_database: Path = DEFAULT_PHASE1_DATABASE
    density_folder: Path = DEFAULT_DENSITY_FOLDER
    output: Path = DEFAULT_OUTPUT


@dataclass(frozen=True)
class DailyQuietModel:
    """Input: one paper anchor day and local model inputs.
    Output: daily quiet-density and orbit summary."""

    day: date
    day_start_time_us: int
    source_file: str
    density_sample_count: int
    orbit_count: int
    f107_sfu: float
    f107a_sfu: float
    mean_altitude_m: float
    mean_semi_major_axis_m: float
    mean_quiet_density_kg_m3: float
    density_orbit_factor: float
    published_rate_m_day: float


def day_bounds_us(day: date) -> tuple[int, int]:
    """Input: UTC calendar day.
    Output: [start, stop) UTC microseconds."""
    start = datetime.combine(day, time.min, timezone.utc)
    return (
        int(start.timestamp() * 1_000_000),
        int((start + timedelta(days=1)).timestamp() * 1_000_000),
    )


def load_daily_solar(
    connection: sqlite3.Connection,
    day: date,
) -> tuple[float, float]:
    """Input: Phase 1 weather rows and UTC day.
    Output: unique prior-day F10.7 and centered F10.7A values."""
    start_us, stop_us = day_bounds_us(day)
    rows = connection.execute(
        "SELECT f107_sfu, f107a_sfu FROM space_weather "
        "WHERE time_us >= ? AND time_us < ?",
        (start_us, stop_us),
    ).fetchall()
    values = {(float(f107), float(f107a)) for f107, f107a in rows}
    if len(rows) != 8 or len(values) != 1:
        raise ValueError(f"Expected eight consistent weather rows for {day}: {values}")
    return values.pop()


def load_daily_mean_a(
    connection: sqlite3.Connection,
    day: date,
) -> tuple[int, float]:
    """Input: Phase 1 phase-orbit rows and UTC day.
    Output: orbit count and daily mean semi-major axis in meters."""
    start_us, stop_us = day_bounds_us(day)
    row = connection.execute(
        "SELECT COUNT(*), AVG(phase_weighted_mean_semi_major_axis_m) "
        "FROM swarm_a_phase_orbit_mean_v2 WHERE time_us >= ? AND time_us < ?",
        (start_us, stop_us),
    ).fetchone()
    if row is None or int(row[0]) == 0 or row[1] is None:
        raise ValueError(f"No phase-orbit rows for {day}")
    return int(row[0]), float(row[1])


def density_source_path(folder: Path, day: date) -> Path:
    """Input: DNSAPOD folder and UTC day.
    Output: unique matching daily source ZIP path."""
    matches = list(folder.glob(f"SW_OPER_DNSAPOD_2__{day:%Y%m%d}T*.ZIP"))
    if len(matches) != 1:
        raise ValueError(f"Expected one DNSAPOD ZIP for {day}, found {len(matches)}")
    return matches[0]


def calculate_daily_quiet_model(
    connection: sqlite3.Connection,
    paths: ScaleCheckPaths,
    anchor: tuple[date, float],
) -> DailyQuietModel:
    """Input: Phase 1 connection, paths, and {day, published_rate_m_day}.
    Output: one daily NRLMSIS quiet-density summary."""
    day, published_rate_m_day = anchor
    source_path = density_source_path(paths.density_folder, day)
    samples = load_dnsapod(source_path)["samples"]
    if not samples:
        raise ValueError(f"No valid DNSAPOD samples for {day}")
    f107_sfu, f107a_sfu = load_daily_solar(connection, day)
    drivers = [
        {
            "f107_sfu": f107_sfu,
            "f107a_sfu": f107a_sfu,
            "ap_values": [QUIET_AP] * 7,
        }
        for _ in samples
    ]
    densities = calculate_msis_density(samples, drivers)
    if any(density is None for density in densities):
        raise ValueError(f"NRLMSIS returned invalid density for {day}")
    orbit_count, mean_a_m = load_daily_mean_a(connection, day)
    mean_density = fmean(float(density) for density in densities)
    return DailyQuietModel(
        day=day,
        day_start_time_us=day_bounds_us(day)[0],
        source_file=source_path.name,
        density_sample_count=len(densities),
        orbit_count=orbit_count,
        f107_sfu=f107_sfu,
        f107a_sfu=f107a_sfu,
        mean_altitude_m=fmean(float(sample["altitude_m"]) for sample in samples),
        mean_semi_major_axis_m=mean_a_m,
        mean_quiet_density_kg_m3=mean_density,
        density_orbit_factor=mean_density * sqrt(EARTH_MU_M3_S2 * mean_a_m),
        published_rate_m_day=published_rate_m_day,
    )


def conversion_scale_m2_kg(calibration: DailyQuietModel) -> float:
    """Input: 2024 daily model summary and published rate.
    Output: model-specific density-to-decay scale in m^2/kg."""
    rate_m_s = calibration.published_rate_m_day / DAY_SECONDS
    return rate_m_s / calibration.density_orbit_factor


def predicted_rate_m_day(scale_m2_kg: float, target: DailyQuietModel) -> float:
    """Input: fixed 2024 scale and target daily model summary.
    Output: target predicted quiet decay rate in m/day."""
    return scale_m2_kg * target.density_orbit_factor * DAY_SECONDS


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: empty Phase 6 SQLite connection.
    Output: daily-anchor, scale-check, and metadata tables."""
    connection.executescript("""
        CREATE TABLE phase6_paper_msis_daily_anchor_v1 (
            day_utc TEXT PRIMARY KEY,
            day_start_time_us INTEGER NOT NULL,
            source_file TEXT NOT NULL,
            density_sample_count INTEGER NOT NULL,
            orbit_count INTEGER NOT NULL,
            f107_sfu REAL NOT NULL,
            f107a_sfu REAL NOT NULL,
            quiet_ap REAL NOT NULL,
            mean_altitude_m REAL NOT NULL,
            mean_semi_major_axis_m REAL NOT NULL,
            mean_quiet_density_kg_m3 REAL NOT NULL,
            density_orbit_factor REAL NOT NULL,
            published_rate_m_day REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_paper_msis_scale_check_v1 (
            calibration_day_utc TEXT PRIMARY KEY,
            validation_day_utc TEXT NOT NULL,
            conversion_scale_m2_kg REAL NOT NULL,
            predicted_validation_rate_m_day REAL NOT NULL,
            published_validation_rate_m_day REAL NOT NULL,
            signed_error_m_day REAL NOT NULL,
            absolute_error_m_day REAL NOT NULL,
            relative_error_percent REAL NOT NULL,
            modeled_density_ratio REAL NOT NULL,
            published_rate_ratio REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_paper_msis_scale_metadata_v1 (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def write_output(
    paths: ScaleCheckPaths,
    calibration: DailyQuietModel,
    validation: DailyQuietModel,
) -> dict[str, float]:
    """Input: output paths and two daily summaries.
    Output: new SQLite plus scale-check metrics."""
    if paths.output.exists():
        raise FileExistsError(f"Refusing to overwrite Phase 6 output: {paths.output}")
    scale = conversion_scale_m2_kg(calibration)
    predicted_rate = predicted_rate_m_day(scale, validation)
    signed_error = predicted_rate - validation.published_rate_m_day
    relative_error = signed_error / validation.published_rate_m_day * 100.0
    density_ratio = (
        validation.mean_quiet_density_kg_m3
        / calibration.mean_quiet_density_kg_m3
    )
    published_ratio = (
        validation.published_rate_m_day / calibration.published_rate_m_day
    )
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = paths.output.with_suffix(".part")
    temporary_path.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(temporary_path)) as output:
            create_tables(output)
            output.executemany(
                "INSERT INTO phase6_paper_msis_daily_anchor_v1 VALUES "
                f"({', '.join('?' for _ in range(14))})",
                [
                    (
                        item.day.isoformat(), item.day_start_time_us,
                        item.source_file, item.density_sample_count,
                        item.orbit_count, item.f107_sfu, item.f107a_sfu,
                        QUIET_AP, item.mean_altitude_m,
                        item.mean_semi_major_axis_m,
                        item.mean_quiet_density_kg_m3,
                        item.density_orbit_factor, item.published_rate_m_day,
                        ALGORITHM_VERSION,
                    )
                    for item in (calibration, validation)
                ],
            )
            output.execute(
                "INSERT INTO phase6_paper_msis_scale_check_v1 VALUES "
                f"({', '.join('?' for _ in range(11))})",
                (
                    calibration.day.isoformat(), validation.day.isoformat(),
                    scale, predicted_rate, validation.published_rate_m_day,
                    signed_error, abs(signed_error), relative_error,
                    density_ratio, published_ratio, ALGORITHM_VERSION,
                ),
            )
            output.executemany(
                "INSERT INTO phase6_paper_msis_scale_metadata_v1 VALUES (?, ?)",
                [
                    ("algorithm_version", ALGORITHM_VERSION),
                    ("density_model", "NRLMSIS 2.0 via pymsis 0.12.0"),
                    ("quiet_ap", str(QUIET_AP)),
                    ("paper_doi", "10.1029/2026GL125768"),
                    ("calibration_rule", "2024 paper rate / daily mean quiet density-orbit factor"),
                    ("validation_rule", "fixed 2024 scale applied to 2026 daily mean quiet density-orbit factor"),
                    ("limitation", "model-specific empirical scale; not a calibrated physical ballistic coefficient"),
                ],
            )
            output.commit()
        os.replace(temporary_path, paths.output)
    finally:
        temporary_path.unlink(missing_ok=True)
    return {
        "conversion_scale_m2_kg": scale,
        "predicted_validation_rate_m_day": predicted_rate,
        "signed_error_m_day": signed_error,
        "relative_error_percent": relative_error,
    }


def run() -> dict[str, float]:
    """Input: default Phase 1, DNSAPOD, and output paths.
    Output: 2024 calibration and 2026 validation SQLite."""
    paths = ScaleCheckPaths()
    with closing(sqlite3.connect(paths.phase1_database)) as phase1:
        calibration = calculate_daily_quiet_model(
            phase1, paths, (CALIBRATION_DAY, PUBLISHED_2024_RATE_M_DAY),
        )
        validation = calculate_daily_quiet_model(
            phase1, paths, (VALIDATION_DAY, PUBLISHED_2026_RATE_M_DAY),
        )
    return write_output(paths, calibration, validation)


def main() -> None:
    """Input: no command-line arguments.
    Output: one new SQLite or an actionable failure."""
    if sys.argv[1:]:
        raise SystemExit(
            "Usage: python -m phases.phase6.code.calc_phase6_paper_msis_scale_check",
        )
    print(run())


if __name__ == "__main__":
    main()
