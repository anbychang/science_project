"""Audit the observed SME, density-ratio, and SYM-H peak order."""

import math
import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

from satellite_orbit.data.density.down_swarm_density_pod import sha256_file


DENSITY_DB = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_4_density_v3.sqlite")
GEOMAG_DB = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_5_geomag_orbit_v1.sqlite")
OUTPUT_DB = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_6_peak_order_v1.sqlite")
ALGORITHM_VERSION = "storm_peak_order_v1"
HOUR_US = 3_600_000_000
PEAK_WINDOW_HOURS = 24


def observed_orbit_ratios(database: sqlite3.Connection) -> dict:
    """Input: P2.4 paired density minutes. Output: orbit log ratios keyed by IDs."""
    rows = database.execute("""
        SELECT storm_id,orbit_id,
               SUM(rho_l2_kg_m3 * paired_sample_count),
               SUM(rho_msis_kg_m3 * paired_sample_count)
        FROM storm_density_1min_v3
        WHERE paired_sample_count > 0
        GROUP BY storm_id,orbit_id
    """)
    return {(storm_id, orbit_id): math.log(l2_total / msis_total)
            for storm_id, orbit_id, l2_total, msis_total in rows
            if l2_total > 0 and msis_total > 0}


def check_peak_order(database: sqlite3.Connection, geomag: sqlite3.Connection) -> list[tuple]:
    """Input: P2.4 events and P2.5 Q. Output: 24 h main-pulse peak audit rows."""
    ratios = observed_orbit_ratios(database)
    orbits_by_storm = {}
    for storm_id, orbit_id, midpoint_us, q_nt, valid in geomag.execute("""
        SELECT storm_id,orbit_id,t_mid_time_us,q_sme_nt,is_valid
        FROM storm_geomag_orbit_v1 ORDER BY storm_id,t_mid_time_us
    """):
        if valid and q_nt is not None and (storm_id, orbit_id) in ratios:
            orbits_by_storm.setdefault(storm_id, []).append(
                (midpoint_us, q_nt, ratios[storm_id, orbit_id])
            )
    audit = []
    for storm_id, t0_us in database.execute("""
        SELECT storm_id,t0_time_us FROM storm_catalog_v3
        WHERE status='used' ORDER BY t0_time_us
    """):
        pulse = [orbit for orbit in orbits_by_storm.get(storm_id, ())
                 if abs(orbit[0] - t0_us) <= PEAK_WINDOW_HOURS * HOUR_US]
        if not pulse:
            raise ValueError(f"No paired orbit within the main-pulse window: {storm_id}")
        sme_peak = max(pulse, key=lambda orbit: orbit[1])
        density_peak = max(pulse, key=lambda orbit: orbit[2])
        sme_hour = (sme_peak[0] - t0_us) / HOUR_US
        density_hour = (density_peak[0] - t0_us) / HOUR_US
        audit.append((storm_id, t0_us, sme_peak[0], density_peak[0],
                      sme_hour, density_hour, density_hour - sme_hour,
                      int(sme_peak[0] < density_peak[0] < t0_us),
                      ALGORITHM_VERSION))
    return audit


def write_peak_order(
    density_path: Path = DENSITY_DB,
    geomag_path: Path = GEOMAG_DB,
    output_path: Path = OUTPUT_DB,
) -> dict:
    """Input: checked P2.4/P2.5 paths. Output: new descriptive peak-order SQLite."""
    for source_path in (density_path, geomag_path):
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
    if output_path.exists():
        raise FileExistsError(output_path)
    density_hash = sha256_file(density_path)
    geomag_hash = sha256_file(geomag_path)
    with closing(sqlite3.connect(
        f"file:{density_path.resolve().as_posix()}?mode=ro", uri=True
    )) as density, closing(sqlite3.connect(
        f"file:{geomag_path.resolve().as_posix()}?mode=ro", uri=True
    )) as geomag:
        source_record = geomag.execute(
            "SELECT value FROM phase2_metadata WHERE name='p2_5_source_sha256'"
        ).fetchone()
        if source_record is None or source_record[0] != density_hash:
            raise ValueError("P2.5 orbit features do not match the P2.4 source.")
        audit = check_peak_order(density, geomag)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=output_path.stem + ".", suffix=".building", dir=output_path.parent
    )
    os.close(handle)
    temporary_path = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary_path)) as output:
            with output:
                output.executescript("""
                    CREATE TABLE storm_peak_order_v1 (
                        storm_id TEXT PRIMARY KEY,
                        t0_time_us INTEGER NOT NULL,
                        sme_peak_time_us INTEGER NOT NULL,
                        density_peak_time_us INTEGER NOT NULL,
                        sme_peak_t_rel_h REAL NOT NULL,
                        density_peak_t_rel_h REAL NOT NULL,
                        sme_to_density_lag_h REAL NOT NULL,
                        expected_order INTEGER NOT NULL CHECK (expected_order IN (0, 1)),
                        algorithm_version TEXT NOT NULL
                    );
                    CREATE TABLE phase2_metadata (
                        name TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );
                """)
                output.executemany(
                    "INSERT INTO storm_peak_order_v1 VALUES (?,?,?,?,?,?,?,?,?)", audit
                )
                output.executemany("INSERT INTO phase2_metadata VALUES (?,?)", (
                    ("p2_6_algorithm_version", ALGORITHM_VERSION),
                    ("p2_6_density_source_sha256", density_hash),
                    ("p2_6_geomag_source_sha256", geomag_hash),
                    ("p2_6_storm_rows", str(len(audit))),
                ))
            if output.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("P2.6 SQLite integrity check failed.")
            if output.execute("SELECT COUNT(*) FROM storm_peak_order_v1").fetchone()[0] != len(audit):
                raise ValueError("P2.6 event count differs from source audit.")
        if (sha256_file(density_path) != density_hash
                or sha256_file(geomag_path) != geomag_hash or output_path.exists()):
            raise ValueError("P2.4/P2.5 changed or P2.6 output appeared during build.")
        os.rename(temporary_path, output_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return {"storms": len(audit), "expected_order": sum(row[-2] for row in audit)}


def main() -> None:
    """Input: optional P2_4_DB P2_5_DB OUTPUT_DB. Output: peak-order counts."""
    arguments = sys.argv[1:]
    if len(arguments) not in (0, 3):
        raise SystemExit("Usage: python -m satellite_orbit.phase2.prep_26_peak_order "
                         "[P2_4_DB P2_5_DB OUTPUT_DB]")
    paths = tuple(map(Path, arguments)) if arguments else (DENSITY_DB, GEOMAG_DB, OUTPUT_DB)
    print(write_peak_order(*paths))


if __name__ == "__main__":
    main()
