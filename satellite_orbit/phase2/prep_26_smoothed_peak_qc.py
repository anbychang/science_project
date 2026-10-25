"""Build the final P2.6 smoothed peak checks inside the fixed candidate window."""

import math
import os
import shutil
import sqlite3
import sys
import tempfile
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from satellite_orbit.data.density.down_swarm_density_pod import sha256_file
from satellite_orbit.phase2.calc_centered_mean import centered_mean


ALGORITHM_VERSION = "storm_minute_peak_qc_v4"
SOURCE_VERSION = "storm_minute_analysis_v2"
SME_HALF_WINDOW_US = 450_000_000
DENSITY_HALF_WINDOW_RAD = math.pi
START_H = -12.0
END_H = 24.0


@dataclass(frozen=True)
class SmoothedPeakPaths:
    """Input: P2.5 minute analysis. Output: final P2.6 checkpoint path record."""

    source: Path = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_5_minute_analysis_v2.sqlite")
    output: Path = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_6_final.sqlite")


def smoothed_event_rows(database: sqlite3.Connection, storm_id: str) -> list[tuple]:
    """Input: analysis connection and storm ID. Output: candidate minutes with smooth values."""
    rows = database.execute("""
        SELECT source_time_us,t_rel_h,u_rel_rad,sme_nt,log_ratio_obs
        FROM storm_minute_analysis_v2 WHERE storm_id=? ORDER BY source_time_us
    """, (storm_id,)).fetchall()
    if not rows:
        raise ValueError(f"Missing event minutes: {storm_id}")
    sme_smooth = centered_mean(
        [row[0] for row in rows], [row[3] for row in rows], SME_HALF_WINDOW_US
    )
    density_smooth = centered_mean(
        [row[2] for row in rows], [row[4] for row in rows], DENSITY_HALF_WINDOW_RAD
    )
    return [
        (storm_id, row[0], row[1], row[3], row[4],
         sme if math.isfinite(sme) else None,
         density if math.isfinite(density) else None, ALGORITHM_VERSION)
        for row, sme, density in zip(rows, sme_smooth, density_smooth, strict=True)
        if START_H <= row[1] <= END_H
    ]


def create_tables(database: sqlite3.Connection) -> None:
    """Input: copied P2.5 connection. Output: empty final series and QC tables."""
    database.executescript("""
        CREATE TABLE storm_minute_smooth_v4 (
            storm_id TEXT NOT NULL,
            source_time_us INTEGER NOT NULL,
            t_rel_h REAL NOT NULL,
            sme_raw_nt REAL,
            log_ratio_raw REAL,
            sme_smooth_nt REAL,
            log_ratio_smooth REAL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id,source_time_us),
            FOREIGN KEY (storm_id) REFERENCES storm_event_t0_phase_v5(storm_id)
        );
        CREATE TABLE storm_minute_peak_qc_v4 (
            storm_id TEXT PRIMARY KEY,
            candidate_start_t_rel_h REAL NOT NULL,
            candidate_end_t_rel_h REAL NOT NULL,
            candidate_minute_count INTEGER NOT NULL,
            sme_smooth_minute_count INTEGER NOT NULL,
            density_smooth_minute_count INTEGER NOT NULL,
            sme_peak_time_us INTEGER NOT NULL,
            sme_peak_t_rel_h REAL NOT NULL,
            sme_peak_nt REAL NOT NULL,
            density_peak_time_us INTEGER NOT NULL,
            density_peak_t_rel_h REAL NOT NULL,
            density_peak_log_ratio REAL NOT NULL,
            sme_to_density_lag_h REAL NOT NULL,
            sme_precedes_density INTEGER NOT NULL CHECK (sme_precedes_density IN (0,1)),
            algorithm_version TEXT NOT NULL,
            FOREIGN KEY (storm_id) REFERENCES storm_event_t0_phase_v5(storm_id)
        );
    """)


def insert_event(database: sqlite3.Connection, storm_id: str) -> None:
    """Input: copied P2.5 connection and storm ID. Output: series and one QC row."""
    rows = smoothed_event_rows(database, storm_id)
    database.executemany("""
        INSERT INTO storm_minute_smooth_v4 VALUES (?,?,?,?,?,?,?,?)
    """, rows)
    sme_candidates = [row for row in rows if row[5] is not None]
    density_candidates = [row for row in rows if row[6] is not None]
    if not sme_candidates or not density_candidates:
        raise ValueError(f"No smoothed peak candidates: {storm_id}")
    sme = max(sme_candidates, key=lambda row: (row[5], -row[1]))
    density = max(density_candidates, key=lambda row: (row[6], -row[1]))
    database.execute("""
        INSERT INTO storm_minute_peak_qc_v4 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (storm_id, START_H, END_H, len(rows), len(sme_candidates),
          len(density_candidates), sme[1], sme[2], sme[5], density[1],
          density[2], density[6], density[2] - sme[2],
          int(sme[1] < density[1]), ALGORITHM_VERSION))


def verify_output(database: sqlite3.Connection) -> dict:
    """Input: populated P2.6 connection. Output: checked event and minute counts."""
    storms, candidate_minutes, sme_first = database.execute("""
        SELECT count(*),sum(candidate_minute_count),sum(sme_precedes_density)
        FROM storm_minute_peak_qc_v4
    """).fetchone()
    expected_storms = database.execute(
        "SELECT count(DISTINCT storm_id) FROM storm_minute_analysis_v2 WHERE storm_status='used'"
    ).fetchone()[0]
    series_minutes = database.execute(
        "SELECT count(*) FROM storm_minute_smooth_v4"
    ).fetchone()[0]
    if expected_storms == 0 or storms != expected_storms or candidate_minutes != series_minutes:
        raise ValueError("Final P2.6 smoothed QC is incomplete.")
    if database.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("Final P2.6 foreign-key check failed.")
    if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("Final P2.6 SQLite integrity check failed.")
    return {"storms": storms, "candidate_minutes": series_minutes,
            "sme_precedes_density_rows": sme_first}


def write_smoothed_peak_qc(paths: SmoothedPeakPaths = SmoothedPeakPaths()) -> dict:
    """Input: frozen P2.5 checkpoint. Output: checked final P2.6 SQLite."""
    if not paths.source.is_file():
        raise FileNotFoundError(paths.source)
    if paths.output.exists():
        raise FileExistsError(paths.output)
    source_hash = sha256_file(paths.source)
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=paths.output.stem + ".", suffix=".building", dir=paths.output.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        shutil.copyfile(paths.source, temporary)
        if sha256_file(temporary) != source_hash:
            raise ValueError("P2.5 changed during copy.")
        with closing(sqlite3.connect(temporary)) as database:
            database.execute("PRAGMA foreign_keys=ON")
            version = database.execute("""
                SELECT value FROM phase2_metadata WHERE name='p2_5_algorithm_version'
            """).fetchone()
            if version is None or version[0] != SOURCE_VERSION:
                raise ValueError("Input is not the P2.5 v2 checkpoint.")
            storm_ids = [row[0] for row in database.execute(
                "SELECT storm_id FROM storm_minute_analysis_v2 "
                "WHERE storm_status='used' GROUP BY storm_id,t0_time_us ORDER BY t0_time_us"
            )]
            with database:
                create_tables(database)
                for storm_id in storm_ids:
                    insert_event(database, storm_id)
                result = verify_output(database)
                database.executemany("INSERT INTO phase2_metadata VALUES (?,?)", (
                    ("p2_6_final_algorithm_version", ALGORITHM_VERSION),
                    ("p2_6_final_source_sha256", source_hash),
                    ("p2_6_final_sme_smoothing", "15min_centered_mean"),
                    ("p2_6_final_density_smoothing", "u_rel_rad_plus_minus_pi_centered_mean"),
                    ("p2_6_final_minimum_valid_fraction", "0.80"),
                    ("p2_6_final_candidate_window_h", "[-12,24]"),
                ))
        if sha256_file(paths.source) != source_hash:
            raise ValueError("P2.5 source changed during build.")
        if paths.output.exists():
            raise FileExistsError("Final P2.6 output appeared during build.")
        os.rename(temporary, paths.output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return result


def main() -> None:
    """Input: optional P2.5 and final paths. Output: final QC summary."""
    arguments = sys.argv[1:]
    if len(arguments) not in (0, 2):
        raise SystemExit("Usage: python -m satellite_orbit.phase2.prep_26_smoothed_peak_qc "
                         "[P2_5_DB OUTPUT_DB]")
    paths = SmoothedPeakPaths(*map(Path, arguments)) if arguments else SmoothedPeakPaths()
    print(write_smoothed_peak_qc(paths))


if __name__ == "__main__":
    main()
