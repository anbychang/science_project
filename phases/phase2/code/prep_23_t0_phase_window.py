"""Build a t0-phase-aligned 1-minute checkpoint for every P2.2 storm."""

import math
import os
import shutil
import sqlite3
import sys
import tempfile
from bisect import bisect_left
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from phases.phase0.code.calculation.density.calc_msis_p2_4 import (
    load_msis_weather,
    sample_drivers,
)
from phases.phase0.code.data.geomagnetic.down_supermag_sme import sha256_file


ALGORITHM_VERSION = "storm_minute_t0_phase_v5"
MINUTE_US = 60_000_000
SECOND_10_US = 10_000_000
HOUR_US = 3_600_000_000
TWO_PI = math.tau
PHASE_ORBITS_BEFORE = 31
PHASE_ORBITS_AFTER = 62
FETCH_BEFORE_US = 60 * HOUR_US
FETCH_AFTER_US = 110 * HOUR_US


@dataclass(frozen=True)
class PhaseWindowPaths:
    """Input: P2.2, Phase 1, weather files. Output: P2.3 v5 path record."""

    storms: Path = Path("phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_2_v2.sqlite")
    phase1: Path = Path("phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite")
    gfz_ap: Path = Path("phases/phase0/data/raw/geomagnetic/gfz_ap_2023-07-01_2026-06-30.json")
    solar: Path = Path("phases/phase0/data/raw/space_weather/SW-All.csv")
    output: Path = Path("phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_3_t0_phase_v5.sqlite")


@dataclass(frozen=True)
class PhaseWindow:
    """Input: one P2.2 event and unwrapped phase. Output: exact phase-aligned bounds."""

    storm_id: str
    t0_us: int
    symh_min_nt: int
    compound: int
    n_minima: int
    t0_phase_rad: float
    start_phase_rad: float
    end_phase_rad: float
    start_us: int
    end_us: int
    minute_start_us: int
    minute_end_us: int


@dataclass(frozen=True)
class PhaseSeries:
    """Input: contiguous Phase 1 rows. Output: cached UTC and unwrapped-phase indexes."""

    rows: list[sqlite3.Row]
    times_us: list[int]
    phases_rad: list[float]


def wrapped_phase(row: sqlite3.Row) -> float:
    """Input: Phase 1 mean-element row. Output: wrapped argument plus anomaly rad."""
    return (row["mean_argument_of_perigee_rad"] + row["mean_anomaly_rad"]) % TWO_PI


def unwrap_phase(rows: list[sqlite3.Row]) -> list[float]:
    """Input: contiguous 10-second Phase 1 rows. Output: strictly increasing phase rad."""
    if not rows:
        raise ValueError("No Phase 1 rows available.")
    values = [wrapped_phase(rows[0])]
    for previous, current in zip(rows, rows[1:]):
        if (current["time_us"] - previous["time_us"] != SECOND_10_US
                or current["chunk_id"] != previous["chunk_id"]):
            raise ValueError("Phase rows are not contiguous within one chunk.")
        step = (wrapped_phase(current) - wrapped_phase(previous) + math.pi) % TWO_PI - math.pi
        if not 0 < step < math.pi:
            raise ValueError("Phase is not strictly increasing.")
        values.append(values[-1] + step)
    return values


def phase_series(rows: list[sqlite3.Row]) -> PhaseSeries:
    """Input: contiguous Phase 1 rows. Output: cached UTC and phase indexes."""
    return PhaseSeries(rows, [row["time_us"] for row in rows], unwrap_phase(rows))


def phase_value_at_time(series: PhaseSeries, time_us: int) -> float:
    """Input: cached phase series and UTC epoch. Output: interpolated phase rad."""
    index = bisect_left(series.times_us, time_us)
    if index == len(series.rows) or (index == 0 and series.times_us[0] != time_us):
        raise ValueError(f"Phase source does not bracket {time_us}.")
    if series.times_us[index] == time_us:
        return series.phases_rad[index]
    left = index - 1
    right = index
    if series.times_us[right] - series.times_us[left] != SECOND_10_US:
        raise ValueError("Phase interpolation crosses a source gap.")
    fraction = (time_us - series.times_us[left]) / (series.times_us[right] - series.times_us[left])
    return series.phases_rad[left] + fraction * (
        series.phases_rad[right] - series.phases_rad[left]
    )


def time_at_phase(series: PhaseSeries, target_phase_rad: float) -> int:
    """Input: cached phase series and target phase rad. Output: interpolated UTC us."""
    index = bisect_left(series.phases_rad, target_phase_rad)
    if (index == len(series.phases_rad)
            or (index == 0 and series.phases_rad[0] != target_phase_rad)):
        raise ValueError("Phase source does not bracket requested window boundary.")
    if series.phases_rad[index] == target_phase_rad:
        return series.rows[index]["time_us"]
    left = index - 1
    right = index
    fraction = (target_phase_rad - series.phases_rad[left]) / (
        series.phases_rad[right] - series.phases_rad[left]
    )
    return round(series.rows[left]["time_us"] + fraction * (
        series.rows[right]["time_us"] - series.rows[left]["time_us"]
    ))


def first_minute_at_or_after(time_us: int) -> int:
    """Input: UTC epoch us. Output: first whole-minute label at or after epoch."""
    return (time_us + MINUTE_US - 1) // MINUTE_US * MINUTE_US


def phase_window(event: sqlite3.Row, series: PhaseSeries) -> PhaseWindow:
    """Input: P2.2 event and cached Phase 1 series. Output: t0-aligned phase window."""
    t0_phase = phase_value_at_time(series, event["t0_time_us"])
    start_phase = t0_phase - PHASE_ORBITS_BEFORE * TWO_PI
    end_phase = t0_phase + PHASE_ORBITS_AFTER * TWO_PI
    start_us = time_at_phase(series, start_phase)
    end_us = time_at_phase(series, end_phase)
    minute_start = first_minute_at_or_after(start_us)
    minute_end = first_minute_at_or_after(end_us)
    if minute_start >= minute_end:
        raise ValueError(f"Empty minute window for {event['storm_id']}.")
    return PhaseWindow(
        event["storm_id"], event["t0_time_us"], event["symh_min_nt"], event["compound"],
        event["n_minima"], t0_phase, start_phase, end_phase, start_us, end_us,
        minute_start, minute_end,
    )


def phase_source_rows(connection: sqlite3.Connection, t0_us: int) -> list[sqlite3.Row]:
    """Input: Phase 1 connection and storm t0. Output: usable source rows near t0."""
    return connection.execute(
        """
        SELECT mean.time_us, quality.chunk_id, mean.mean_semi_major_axis_m,
               mean.mean_argument_of_perigee_rad, mean.mean_anomaly_rad,
               raw.orbit_3_decay_rate_m_s AS raw_3_rate,
               raw.orbit_3_decay_rate_1sigma_m_s AS raw_3_sigma,
               raw.orbit_3_sample_count AS raw_3_count,
               raw.orbit_3_reject_reason AS raw_3_reject,
               raw.orbit_5_decay_rate_m_s AS raw_5_rate,
               raw.orbit_5_decay_rate_1sigma_m_s AS raw_5_sigma,
               raw.orbit_5_sample_count AS raw_5_count,
               raw.orbit_5_reject_reason AS raw_5_reject,
               joint.orbit_3_decay_rate_m_s AS joint_3_rate,
               joint.orbit_3_decay_rate_1sigma_m_s AS joint_3_sigma,
               joint.orbit_3_sample_count AS joint_3_count,
               joint.orbit_3_reject_reason AS joint_3_reject,
               joint.orbit_5_decay_rate_m_s AS joint_5_rate,
               joint.orbit_5_decay_rate_1sigma_m_s AS joint_5_sigma,
               joint.orbit_5_sample_count AS joint_5_count,
               joint.orbit_5_reject_reason AS joint_5_reject
        FROM swarm_a_mean_orbit_elements_v1 AS mean
        JOIN swarm_a_pod_quality AS quality ON quality.time_us=mean.time_us
        LEFT JOIN swarm_a_phase_harmonic_decay_raw_b_l_sets_v2 AS raw ON raw.time_us=mean.time_us
        LEFT JOIN swarm_a_phase_harmonic_decay_joint_h2_h3_sets_v2 AS joint ON joint.time_us=mean.time_us
        WHERE mean.time_us BETWEEN ? AND ?
          AND quality.is_usable=1
          AND quality.chunk_id IS NOT NULL
          AND mean.mean_semi_major_axis_m IS NOT NULL
          AND mean.mean_argument_of_perigee_rad IS NOT NULL
          AND mean.mean_anomaly_rad IS NOT NULL
        ORDER BY mean.time_us
        """,
        (t0_us - FETCH_BEFORE_US, t0_us + FETCH_AFTER_US),
    ).fetchall()


def phase_row_at_time(series: PhaseSeries, time_us: int) -> tuple[sqlite3.Row, sqlite3.Row, float]:
    """Input: cached phase series and UTC minute. Output: bracketing rows and phase rad."""
    index = bisect_left(series.times_us, time_us)
    if index == len(series.rows) or (index == 0 and series.times_us[0] != time_us):
        raise ValueError(f"Phase source does not bracket minute {time_us}.")
    if series.times_us[index] == time_us:
        return series.rows[index], series.rows[index], series.phases_rad[index]
    left = series.rows[index - 1]
    right = series.rows[index]
    if right["time_us"] - left["time_us"] != SECOND_10_US:
        raise ValueError("Minute phase interpolation crosses a source gap.")
    fraction = (time_us - left["time_us"]) / (right["time_us"] - left["time_us"])
    return left, right, series.phases_rad[index - 1] + fraction * (
        series.phases_rad[index] - series.phases_rad[index - 1]
    )


def create_tables(destination: sqlite3.Connection) -> None:
    """Input: copied P2.2 SQLite. Output: empty t0-phase event and minute tables."""
    destination.executescript("""
        CREATE TABLE storm_event_t0_phase_v5 (
            storm_id TEXT PRIMARY KEY,
            t0_time_us INTEGER NOT NULL,
            symh_min_nt INTEGER NOT NULL,
            phase_t0_rad REAL NOT NULL,
            phase_start_rad REAL NOT NULL,
            phase_end_rad REAL NOT NULL,
            phase_start_time_us INTEGER NOT NULL,
            phase_end_time_us INTEGER NOT NULL,
            minute_start_time_us INTEGER NOT NULL,
            minute_end_time_us INTEGER NOT NULL,
            phase_orbits_before INTEGER NOT NULL,
            phase_orbits_after INTEGER NOT NULL,
            compound INTEGER NOT NULL,
            n_minima INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE storm_minute_feature_v5 (
            storm_id TEXT NOT NULL REFERENCES storm_event_t0_phase_v5(storm_id),
            source_time_us INTEGER NOT NULL,
            assumed_support_start_time_us INTEGER NOT NULL,
            assumed_support_end_time_us INTEGER NOT NULL,
            t_rel_h REAL NOT NULL,
            u_rad REAL NOT NULL,
            u_rel_rad REAL NOT NULL,
            mean_semi_major_axis_m REAL NOT NULL,
            phase_left_time_us INTEGER NOT NULL,
            phase_right_time_us INTEGER NOT NULL,
            chunk_id INTEGER NOT NULL,
            phase_status TEXT NOT NULL,
            raw_3_rate_m_s REAL,
            raw_3_sigma_m_s REAL,
            raw_3_sample_count INTEGER,
            raw_3_reject_reason TEXT,
            raw_5_rate_m_s REAL,
            raw_5_sigma_m_s REAL,
            raw_5_sample_count INTEGER,
            raw_5_reject_reason TEXT,
            joint_3_rate_m_s REAL,
            joint_3_sigma_m_s REAL,
            joint_3_sample_count INTEGER,
            joint_3_reject_reason TEXT,
            joint_5_rate_m_s REAL,
            joint_5_sigma_m_s REAL,
            joint_5_sample_count INTEGER,
            joint_5_reject_reason TEXT,
            sme_nt REAL,
            symh_nt REAL,
            sme_station_count INTEGER,
            sme_not_before_time_us INTEGER NOT NULL,
            kyoto_not_before_time_us INTEGER NOT NULL,
            ap_step REAL,
            ap_source_end_time_us INTEGER,
            f107_sfu REAL,
            f107a_sfu REAL,
            core_ready_time_us INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id, source_time_us),
            CHECK (assumed_support_start_time_us=source_time_us-30000000),
            CHECK (assumed_support_end_time_us=source_time_us+30000000),
            CHECK (phase_left_time_us<=source_time_us),
            CHECK (source_time_us<=phase_right_time_us)
        );
    """)


def insert_event(destination: sqlite3.Connection, window: PhaseWindow) -> None:
    """Input: destination SQLite and one phase window. Output: persisted event row."""
    destination.execute(
        "INSERT INTO storm_event_t0_phase_v5 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (window.storm_id, window.t0_us, window.symh_min_nt, window.t0_phase_rad,
         window.start_phase_rad, window.end_phase_rad, window.start_us, window.end_us,
         window.minute_start_us, window.minute_end_us, PHASE_ORBITS_BEFORE,
         PHASE_ORBITS_AFTER, window.compound, window.n_minima, ALGORITHM_VERSION),
    )


def minute_rows(window: PhaseWindow, series: PhaseSeries, destination: sqlite3.Connection,
                weather: dict):
    """Input: phase window, cached Phase 1 series, copied P2.2, weather. Output: minute rows."""
    geomag_rows = destination.execute(
        """SELECT time_us,sme_nt,symh_nt,sme_station_count,sme_not_before_time_us,
                  kyoto_not_before_time_us
           FROM geomag_1min_v2 WHERE time_us>=? AND time_us<? ORDER BY time_us""",
        (window.minute_start_us, window.minute_end_us),
    ).fetchall()
    geomag = {row["time_us"]: row for row in geomag_rows}
    for source_time_us in range(window.minute_start_us, window.minute_end_us, MINUTE_US):
        minute = geomag.get(source_time_us)
        if minute is None:
            raise ValueError(f"Missing geomagnetic minute: {window.storm_id}:{source_time_us}")
        left, right, phase = phase_row_at_time(series, source_time_us)
        drivers = sample_drivers(source_time_us, weather)
        core_ready = max(minute["sme_not_before_time_us"], minute["kyoto_not_before_time_us"],
                         right["time_us"])
        yield (
            window.storm_id, source_time_us, source_time_us - MINUTE_US // 2,
            source_time_us + MINUTE_US // 2, (source_time_us - window.t0_us) / HOUR_US,
            phase % TWO_PI, phase - window.t0_phase_rad, left["mean_semi_major_axis_m"],
            left["time_us"], right["time_us"], left["chunk_id"],
            "exact" if left["time_us"] == right["time_us"] else "interpolated",
            left["raw_3_rate"], left["raw_3_sigma"], left["raw_3_count"], left["raw_3_reject"],
            left["raw_5_rate"], left["raw_5_sigma"], left["raw_5_count"], left["raw_5_reject"],
            left["joint_3_rate"], left["joint_3_sigma"], left["joint_3_count"], left["joint_3_reject"],
            left["joint_5_rate"], left["joint_5_sigma"], left["joint_5_count"], left["joint_5_reject"],
            minute["sme_nt"], minute["symh_nt"], minute["sme_station_count"],
            minute["sme_not_before_time_us"], minute["kyoto_not_before_time_us"],
            drivers["ap_values"][1] if drivers else None,
            drivers["ap_last_slot_end_time_us"] if drivers else None,
            drivers["f107_sfu"] if drivers else None,
            drivers["f107a_sfu"] if drivers else None,
            core_ready, ALGORITHM_VERSION,
        )


def verify_output(destination: sqlite3.Connection) -> dict:
    """Input: populated P2.3 SQLite. Output: checked event and minute counts."""
    events, minutes = destination.execute(
        "SELECT count(*),(SELECT count(*) FROM storm_minute_feature_v5) FROM storm_event_t0_phase_v5"
    ).fetchone()
    expected = destination.execute(
        "SELECT sum((minute_end_time_us-minute_start_time_us)/?) FROM storm_event_t0_phase_v5",
        (MINUTE_US,),
    ).fetchone()[0]
    if events == 0 or minutes != expected:
        raise ValueError("P2.3 t0-phase minute count is incomplete.")
    invalid = destination.execute(
        "SELECT count(*) FROM storm_minute_feature_v5 WHERE u_rel_rad < ? OR u_rel_rad >= ?",
        (-PHASE_ORBITS_BEFORE * TWO_PI - TWO_PI, PHASE_ORBITS_AFTER * TWO_PI + TWO_PI),
    ).fetchone()[0]
    if invalid:
        raise ValueError("P2.3 minute phase is outside the selected t0 window.")
    if destination.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("P2.3 t0-phase foreign-key check failed.")
    if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("P2.3 t0-phase SQLite integrity check failed.")
    return {"storms": events, "minute_rows": minutes}


def write_t0_phase_minutes(paths: PhaseWindowPaths = PhaseWindowPaths()) -> dict:
    """Input: frozen P2.2, Phase 1, weather. Output: new checked P2.3 v5 SQLite."""
    if paths.output.exists():
        raise FileExistsError(paths.output)
    source_paths = {
        "storms": paths.storms,
        "phase1": paths.phase1,
        "gfz_ap": paths.gfz_ap,
        "solar": paths.solar,
    }
    for path in source_paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    hashes = {name: sha256_file(path) for name, path in source_paths.items()}
    weather = load_msis_weather(paths.gfz_ap, paths.solar)
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=paths.output.stem + ".", suffix=".building", dir=paths.output.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        shutil.copyfile(paths.storms, temporary)
        if sha256_file(temporary) != hashes["storms"]:
            raise ValueError("P2.2 changed during copy.")
        with closing(sqlite3.connect(temporary)) as destination, closing(
            sqlite3.connect(f"file:{paths.phase1.resolve().as_posix()}?mode=ro", uri=True)
        ) as phase1:
            destination.row_factory = sqlite3.Row
            phase1.row_factory = sqlite3.Row
            destination.execute("PRAGMA foreign_keys=ON")
            events = destination.execute(
                "SELECT storm_id,t0_time_us,symh_min_nt,compound,n_minima "
                "FROM storm_event_v2 ORDER BY t0_time_us"
            ).fetchall()
            if not events:
                raise ValueError("P2.2 has no storm events.")
            with destination:
                create_tables(destination)
                minute_columns = len(destination.execute(
                    "PRAGMA table_info(storm_minute_feature_v5)"
                ).fetchall())
                statement = "INSERT INTO storm_minute_feature_v5 VALUES (" + ",".join(
                    "?" * minute_columns
                ) + ")"
                for event in events:
                    rows = phase_source_rows(phase1, event["t0_time_us"])
                    series = phase_series(rows)
                    window = phase_window(event, series)
                    insert_event(destination, window)
                    destination.executemany(statement, minute_rows(window, series, destination, weather))
                destination.executemany(
                    "INSERT INTO phase2_metadata VALUES (?,?)",
                    (("p2_3_t0_phase_version", ALGORITHM_VERSION),
                     ("p2_3_t0_phase_before", str(PHASE_ORBITS_BEFORE)),
                     ("p2_3_t0_phase_after", str(PHASE_ORBITS_AFTER)),
                     ("p2_3_t0_phase_p2_2_sha256", hashes["storms"]),
                     ("p2_3_t0_phase_phase1_sha256", hashes["phase1"]),
                     ("p2_3_t0_phase_gfz_sha256", hashes["gfz_ap"]),
                     ("p2_3_t0_phase_solar_sha256", hashes["solar"])),
                )
            result = verify_output(destination)
        if any(sha256_file(path) != hashes[name] for name, path in source_paths.items()):
            raise ValueError("P2.3 source changed during build.")
        if paths.output.exists():
            raise FileExistsError(paths.output)
        os.rename(temporary, paths.output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return result


def main() -> None:
    """Input: optional P2.2 Phase 1 weather and output paths. Output: P2.3 counts."""
    arguments = sys.argv[1:]
    if len(arguments) not in (0, 5):
        raise SystemExit("Usage: python -m phases.phase2.code.prep_23_t0_phase_window "
                         "[P2_2_DB PHASE1_DB GFZ_JSON SOLAR_CSV OUTPUT_DB]")
    paths = PhaseWindowPaths(*map(Path, arguments)) if arguments else PhaseWindowPaths()
    print(write_t0_phase_minutes(paths))


if __name__ == "__main__":
    main()
