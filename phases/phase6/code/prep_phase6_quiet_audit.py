"""Write candidate quiet windows and paired orbit-density records."""

import csv
import os
import sqlite3
import sys
from bisect import bisect_left
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from phases.phase0.code.data.density.load_dnsapod import load_dnsapod


DEFAULT_PHASE1_DATABASE = Path(
    "phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite",
)
DEFAULT_SME_FOLDER = Path("phases/phase0/data/raw/sme")
DEFAULT_DENSITY_FOLDER = Path("phases/phase0/data/raw/swarm_density_pod")
DEFAULT_OUTPUT = Path(
    "phases/phase6/data/sqlite/swarm_a_phase6_quiet_audit_v1.sqlite",
)
PHASE_ORBIT_TABLE = "swarm_a_phase_orbit_mean_v2"
MAXIMUM_AP = 7.0
MAXIMUM_SME_NT = 300.0
MINUTES_PER_DAY = 1_440
WEATHER_SAMPLES_PER_DAY = 8
MAXIMUM_DENSITY_OFFSET_US = 60_000_000
ALGORITHM_VERSION = "phase6_quiet_two_day_audit_v1"


@dataclass(frozen=True)
class QuietDay:
    """Input: one UTC day with complete quiet drivers.
    Output: candidate-day limits and source coverage."""

    day: date
    ap_max: float
    sme_max_nt: float
    density_sample_count: int


@dataclass(frozen=True)
class OrbitRow:
    """Input: one Phase 1 phase-orbit row.
    Output: orbit time, start time, and mean semi-major axis."""

    time_us: int
    orbit_start_time_us: int
    mean_semi_major_axis_m: float


@dataclass(frozen=True)
class DensitySample:
    """Input: one valid DNSAPOD orbit-mean density sample.
    Output: time, density, and immutable source file name."""

    time_us: int
    density_kg_m3: float
    source_file: str


@dataclass(frozen=True)
class AuditPaths:
    """Input: immutable Phase 1, SME, DNSAPOD, and output paths.
    Output: one Phase 6 quiet-audit path record."""

    phase1_database: Path = DEFAULT_PHASE1_DATABASE
    sme_folder: Path = DEFAULT_SME_FOLDER
    density_folder: Path = DEFAULT_DENSITY_FOLDER
    output: Path = DEFAULT_OUTPUT


def day_start_us(day: date) -> int:
    """Input: UTC calendar day.
    Output: UTC midnight in microseconds."""
    return int(datetime.combine(day, time.min, timezone.utc).timestamp() * 1_000_000)


def utc_day(time_us: int) -> date:
    """Input: UTC epoch in microseconds.
    Output: containing UTC calendar day."""
    return datetime.fromtimestamp(time_us / 1_000_000, timezone.utc).date()


def phase_orbit_bounds(connection: sqlite3.Connection) -> tuple[int, int]:
    """Input: Phase 1 SQLite connection.
    Output: first and last available phase-orbit times in microseconds."""
    row = connection.execute(
        f"SELECT MIN(time_us), MAX(time_us) FROM {PHASE_ORBIT_TABLE}",
    ).fetchone()
    if row is None or row[0] is None or row[1] is None:
        raise ValueError("Phase 1 has no phase-orbit rows.")
    return int(row[0]), int(row[1])


def daily_ap_maximums(
    connection: sqlite3.Connection,
    start_us: int,
    stop_us: int,
) -> dict[date, float]:
    """Input: Phase 1 weather rows and inclusive source-time bounds.
    Output: UTC day -> maximum Ap for complete eight-sample days."""
    values_by_day: dict[date, list[float]] = {}
    rows = connection.execute(
        "SELECT time_us, ap_now FROM space_weather "
        "WHERE time_us BETWEEN ? AND ? AND ap_now IS NOT NULL",
        (start_us, stop_us),
    )
    for time_us, ap_now in rows:
        values_by_day.setdefault(utc_day(int(time_us)), []).append(float(ap_now))
    return {
        day: max(values)
        for day, values in values_by_day.items()
        if len(values) == WEATHER_SAMPLES_PER_DAY
    }


def sme_daily_maximum(sme_path: Path, day: date) -> float | None:
    """Input: one UTC-day SME CSV and its expected day.
    Output: maximum SME nT, or None when minute coverage is incomplete."""
    with sme_path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != ["tval", "SME", "SMEnum"]:
            raise ValueError(f"Unexpected SME columns: {sme_path}")
        rows = list(reader)
    if len(rows) != MINUTES_PER_DAY:
        return None
    expected_time_s = int(datetime.combine(day, time.min, timezone.utc).timestamp())
    values = []
    for index, row in enumerate(rows):
        if int(float(row["tval"])) != expected_time_s + index * 60:
            return None
        values.append(float(row["SME"]))
    return max(values)


def density_samples_for_day(density_folder: Path, day: date) -> list[DensitySample]:
    """Input: DNSAPOD folder and UTC day.
    Output: valid DNSAPOD orbit-mean density samples for exactly one source ZIP."""
    paths = list(density_folder.glob(f"SW_OPER_DNSAPOD_2__{day:%Y%m%d}T*.ZIP"))
    if len(paths) != 1:
        raise ValueError(f"Expected one DNSAPOD ZIP for {day}, found {len(paths)}.")
    loaded = load_dnsapod(paths[0])
    return [
        DensitySample(
            time_us=int(sample["time_us"]),
            density_kg_m3=float(sample["rho_l2_orbitmean_kg_m3"]),
            source_file=str(sample["source_file"]),
        )
        for sample in loaded["samples"]
        if sample["rho_l2_orbitmean_kg_m3"] is not None
    ]


def candidate_quiet_days(
    ap_maximums: dict[date, float],
    paths: AuditPaths,
) -> list[QuietDay]:
    """Input: complete daily Ap maxima and Phase 6 source paths.
    Output: days passing quiet thresholds with available orbit-mean density."""
    candidates = []
    for day, ap_max in sorted(ap_maximums.items()):
        if ap_max > MAXIMUM_AP:
            continue
        sme_path = paths.sme_folder / f"SME_{day:%Y%m%d}.csv"
        if not sme_path.exists():
            continue
        sme_max = sme_daily_maximum(sme_path, day)
        if sme_max is None or sme_max >= MAXIMUM_SME_NT:
            continue
        samples = density_samples_for_day(paths.density_folder, day)
        if samples:
            candidates.append(QuietDay(day, ap_max, sme_max, len(samples)))
    return candidates


def quiet_windows(days: list[QuietDay]) -> list[tuple[QuietDay, QuietDay]]:
    """Input: UTC-ordered candidate quiet days.
    Output: pairs of consecutive days for two-day closure candidates."""
    return [
        (left, right)
        for left, right in zip(days, days[1:])
        if right.day - left.day == timedelta(days=1)
    ]


def phase_orbits_for_window(
    connection: sqlite3.Connection,
    start_day: date,
    stop_day: date,
) -> list[OrbitRow]:
    """Input: Phase 1 connection and inclusive UTC-day window.
    Output: ordered phase-orbit rows inside the window."""
    start_us = day_start_us(start_day)
    stop_us = day_start_us(stop_day + timedelta(days=1))
    rows = connection.execute(
        f"SELECT time_us, orbit_start_time_us, phase_weighted_mean_semi_major_axis_m "
        f"FROM {PHASE_ORBIT_TABLE} WHERE time_us >= ? AND time_us < ? ORDER BY time_us",
        (start_us, stop_us),
    )
    return [OrbitRow(int(time_us), int(orbit_start_us), float(mean_a_m))
            for time_us, orbit_start_us, mean_a_m in rows]


def nearest_density_sample(
    density_samples: list[DensitySample],
    orbit_time_us: int,
) -> DensitySample | None:
    """Input: time-ordered density samples and one orbit time.
    Output: nearest sample within the fixed 60-second matching limit, or None."""
    times_us = [sample.time_us for sample in density_samples]
    index = bisect_left(times_us, orbit_time_us)
    candidates = density_samples[max(0, index - 1):index + 1]
    if not candidates:
        return None
    closest = min(candidates, key=lambda sample: abs(sample.time_us - orbit_time_us))
    if abs(closest.time_us - orbit_time_us) > MAXIMUM_DENSITY_OFFSET_US:
        return None
    return closest


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: empty Phase 6 SQLite connection.
    Output: versioned quiet-day, quiet-window, pair, and metadata tables."""
    connection.executescript("""
        CREATE TABLE phase6_quiet_day_v1 (
            day_start_time_us INTEGER PRIMARY KEY,
            ap_max REAL NOT NULL,
            sme_max_nt REAL NOT NULL,
            density_orbitmean_sample_count INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_quiet_window_v1 (
            window_id TEXT PRIMARY KEY,
            start_time_us INTEGER NOT NULL,
            stop_time_us INTEGER NOT NULL,
            ap_max REAL NOT NULL,
            sme_max_nt REAL NOT NULL,
            orbit_count INTEGER NOT NULL,
            paired_orbit_count INTEGER NOT NULL,
            selection_status TEXT NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_quiet_orbit_pair_v1 (
            window_id TEXT NOT NULL REFERENCES phase6_quiet_window_v1(window_id),
            time_us INTEGER NOT NULL,
            orbit_start_time_us INTEGER NOT NULL,
            mean_semi_major_axis_m REAL NOT NULL,
            density_time_us INTEGER NOT NULL,
            rho_l2_orbitmean_kg_m3 REAL NOT NULL,
            density_offset_s REAL NOT NULL,
            density_source_file TEXT NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (window_id, time_us)
        );
        CREATE TABLE phase6_quiet_metadata_v1 (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def write_quiet_audit(
    paths: AuditPaths,
    quiet_days: list[QuietDay],
    windows: list[tuple[QuietDay, QuietDay]],
) -> dict[str, int]:
    """Input: Phase 6 paths, quiet days, and two-day windows.
    Output: counts after writing a new SQLite audit without modifying source records."""
    if paths.output.exists():
        raise FileExistsError(f"Refusing to overwrite existing Phase 6 output: {paths.output}")
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = paths.output.with_suffix(".part")
    if temporary_path.exists():
        temporary_path.unlink()
    try:
        with (
            closing(sqlite3.connect(paths.phase1_database)) as phase1,
            closing(sqlite3.connect(temporary_path)) as output,
        ):
            create_tables(output)
            output.executemany(
                "INSERT INTO phase6_quiet_day_v1 VALUES (?, ?, ?, ?, ?)",
                [
                    (day_start_us(day.day), day.ap_max, day.sme_max_nt,
                     day.density_sample_count, ALGORITHM_VERSION)
                    for day in quiet_days
                ],
            )
            pair_count = 0
            accepted_window_count = 0
            for first_day, second_day in windows:
                window_id = f"Q{first_day.day:%Y%m%d}"
                orbits = phase_orbits_for_window(phase1, first_day.day, second_day.day)
                density_samples = sorted(
                    density_samples_for_day(paths.density_folder, first_day.day)
                    + density_samples_for_day(paths.density_folder, second_day.day),
                    key=lambda sample: sample.time_us,
                )
                pairs = [
                    (orbit, nearest_density_sample(density_samples, orbit.time_us))
                    for orbit in orbits
                ]
                paired = [(orbit, sample) for orbit, sample in pairs if sample is not None]
                status = "candidate" if paired and len(paired) == len(orbits) else "incomplete_pairing"
                output.execute(
                    "INSERT INTO phase6_quiet_window_v1 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        window_id, day_start_us(first_day.day),
                        day_start_us(second_day.day + timedelta(days=1)),
                        max(first_day.ap_max, second_day.ap_max),
                        max(first_day.sme_max_nt, second_day.sme_max_nt),
                        len(orbits), len(paired), status, ALGORITHM_VERSION,
                    ),
                )
                output.executemany(
                    "INSERT INTO phase6_quiet_orbit_pair_v1 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            window_id, orbit.time_us, orbit.orbit_start_time_us,
                            orbit.mean_semi_major_axis_m, sample.time_us,
                            sample.density_kg_m3,
                            (sample.time_us - orbit.time_us) / 1_000_000,
                            sample.source_file, ALGORITHM_VERSION,
                        )
                        for orbit, sample in paired
                    ],
                )
                pair_count += len(paired)
                accepted_window_count += int(status == "candidate")
            output.executemany(
                "INSERT INTO phase6_quiet_metadata_v1 VALUES (?, ?)",
                [
                    ("algorithm_version", ALGORITHM_VERSION),
                    ("phase1_database", str(paths.phase1_database)),
                    ("maximum_ap", str(MAXIMUM_AP)),
                    ("maximum_sme_nt", str(MAXIMUM_SME_NT)),
                    ("density_match_limit_s", str(MAXIMUM_DENSITY_OFFSET_US / 1_000_000)),
                    ("selection_limit", "candidate windows are not maneuver-complete clean data"),
                ],
            )
            output.commit()
        os.replace(temporary_path, paths.output)
    finally:
        temporary_path.unlink(missing_ok=True)
    return {
        "quiet_day_count": len(quiet_days),
        "window_count": len(windows),
        "candidate_window_count": accepted_window_count,
        "paired_orbit_count": pair_count,
    }


def run() -> dict[str, int]:
    """Input: default Phase 1 SQLite and raw SME/DNSAPOD folders.
    Output: a new Phase 6 quiet-audit SQLite and its row counts."""
    paths = AuditPaths()
    with sqlite3.connect(paths.phase1_database) as connection:
        start_us, stop_us = phase_orbit_bounds(connection)
        ap_maximums = daily_ap_maximums(connection, start_us, stop_us)
    days = candidate_quiet_days(ap_maximums, paths)
    return write_quiet_audit(paths, days, quiet_windows(days))


def main() -> None:
    """Input: no command-line arguments.
    Output: one new Phase 6 quiet-audit SQLite or an actionable failure."""
    if sys.argv[1:]:
        raise SystemExit("Usage: python -m phases.phase6.code.prep_phase6_quiet_audit")
    print(run())


if __name__ == "__main__":
    main()
