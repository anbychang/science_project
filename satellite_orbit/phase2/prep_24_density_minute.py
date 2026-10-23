"""Pair native DNSAPOD samples with MSIS and store minute storm densities."""

import json
import math
import os
import shutil
import sqlite3
import sys
import tempfile
from bisect import bisect_right
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from satellite_orbit.calculation.density.calc_msis_p2_4 import (
    calculate_msis_density,
    load_msis_weather,
    sample_drivers,
)
from satellite_orbit.data.density.down_swarm_density_pod import SOURCE_NAME, sha256_file
from satellite_orbit.data.density.load_dnsapod import load_dnsapod


ALGORITHM_VERSION = "storm_density_1min_v3"
SOURCE_VERSION = "storm_minute_feature_v3"
SECOND_30_US = 30_000_000
MINUTE_US = 60_000_000
COVERAGE_PARTS = 5
COVERAGE_REQUIRED_PARTS = 4


@dataclass(frozen=True)
class DensityPaths:
    """Input: existing sources and new destinations. Output: immutable path record."""

    input_db: Path = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_3_full_orbit_v3.sqlite")
    manifest: Path = Path("data/swarm_density_pod/manifest_dnsapod_20230701_20260630.json")
    gfz_ap: Path = Path("data/geomagnetic/gfz_ap_2023-07-01_2026-06-30.json")
    solar: Path = Path("data/space_weather/SW-All.csv")
    output_db: Path = Path("data/sqlite/2023/swarm_a_phase2_sme_p2_4_density_v3.sqlite")


@dataclass(frozen=True)
class DensityContext:
    """Input: frozen orbit/minute keys and weather. Output: day-processing context."""

    orbits: list[sqlite3.Row]
    orbit_starts: list[int]
    minute_keys: set[tuple[str, int]]
    weather: dict


def empty_minute() -> dict:
    """Input: none. Output: named minute counts and sums."""
    return {"l2_count": 0, "pair_count": 0, "orbitmean_count": 0,
            "l2_sum": 0.0, "msis_sum": 0.0, "orbitmean_sum": 0.0}


def required_days(database: sqlite3.Connection) -> set[str]:
    """Input: full-orbit event SQLite. Output: UTC YYYYMMDD days touched by events."""
    days = set()
    for start_us, end_us in database.execute(
        "SELECT window_start_time_us,window_end_time_us FROM storm_event_full_orbit_v3"
    ):
        first = datetime.fromtimestamp(start_us / 1_000_000, timezone.utc).date()
        last = datetime.fromtimestamp((end_us - 1) / 1_000_000, timezone.utc).date()
        day = first
        while day <= last:
            days.add(day.strftime("%Y%m%d"))
            day += timedelta(days=1)
    return days


def checked_manifest(paths: DensityPaths, days: set[str]) -> list[Path]:
    """Input: DNSAPOD manifest and needed days. Output: verified daily ZIP paths."""
    manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
    if manifest.get("collection") != "SW_OPER_DNSAPOD_2_":
        raise ValueError("DNSAPOD manifest has the wrong product collection.")
    records = {}
    for record in manifest["files"]:
        match = SOURCE_NAME.fullmatch(record["name"])
        if match and match[1] in days:
            if match[2] != "0301" or match[1] in records:
                raise ValueError(f"Unexpected DNSAPOD source version: {record['name']}")
            records[match[1]] = record
    if set(records) != days:
        raise ValueError(f"DNSAPOD manifest lacks {len(days - records.keys())} needed days.")
    paths_by_day = []
    for day in sorted(days):
        record = records[day]
        zip_path = paths.manifest.parent / record["name"]
        if not zip_path.is_file() or sha256_file(zip_path) != record["sha256"]:
            raise ValueError(f"DNSAPOD ZIP missing or changed: {zip_path}")
        paths_by_day.append(zip_path)
    return paths_by_day


def selected_orbit(context: DensityContext, time_us: int) -> sqlite3.Row | None:
    """Input: indexed complete orbits and UTC sample. Output: containing orbit or None."""
    index = bisect_right(context.orbit_starts, time_us) - 1
    if index < 0 or time_us >= context.orbits[index]["orbit_end_time_us"]:
        return None
    return context.orbits[index]


def paired_day(zip_path: Path, context: DensityContext) -> dict:
    """Input: one raw ZIP and source context. Output: daily minute/orbit sums."""
    loaded = load_dnsapod(zip_path)
    minutes = {}
    orbits = {}
    candidates = []
    drivers = []
    missing_weather = 0
    for sample in loaded["samples"]:
        orbit = selected_orbit(context, sample["time_us"])
        if orbit is None:
            continue
        orbit_key = (orbit["storm_id"], orbit["orbit_id"])
        orbit_counts = orbits.setdefault(orbit_key, {"l2_count": 0, "pair_count": 0})
        minute_us = (sample["time_us"] + SECOND_30_US) // MINUTE_US * MINUTE_US
        minute_key = (orbit["storm_id"], minute_us)
        minute = minutes.setdefault(minute_key, empty_minute()) \
            if minute_key in context.minute_keys else None
        orbitmean = sample["rho_l2_orbitmean_kg_m3"]
        if orbitmean is not None and minute is not None:
            minute["orbitmean_count"] += 1
            minute["orbitmean_sum"] += orbitmean
        density = sample["rho_l2_kg_m3"]
        if density is None:
            continue
        orbit_counts["l2_count"] += 1
        if minute is not None:
            minute["l2_count"] += 1
        driver = sample_drivers(sample["time_us"], context.weather)
        if driver is None:
            missing_weather += 1
            continue
        candidates.append((sample, orbit_key, minute_key))
        drivers.append(driver)
    model_densities = calculate_msis_density([row[0] for row in candidates], drivers)
    missing_model = 0
    for (sample, orbit_key, minute_key), model_density in zip(
        candidates, model_densities, strict=True
    ):
        if model_density is None:
            missing_model += 1
            continue
        orbits[orbit_key]["pair_count"] += 1
        minute = minutes.get(minute_key)
        if minute is not None:
            minute["pair_count"] += 1
            minute["l2_sum"] += sample["rho_l2_kg_m3"]
            minute["msis_sum"] += model_density
    return {"minutes": minutes, "orbits": orbits,
            "raw_count": loaded["raw_count"], "missing_weather": missing_weather,
            "missing_model": missing_model}


def create_tables(database: sqlite3.Connection) -> None:
    """Input: copied full-orbit SQLite. Output: empty density and quality tables."""
    database.executescript("""
        CREATE TABLE storm_density_1min_v3 (
            storm_id TEXT NOT NULL,
            source_time_us INTEGER NOT NULL,
            orbit_id INTEGER NOT NULL,
            l2_valid_sample_count INTEGER NOT NULL,
            paired_sample_count INTEGER NOT NULL,
            orbitmean_valid_sample_count INTEGER NOT NULL,
            rho_l2_kg_m3 REAL,
            rho_msis_kg_m3 REAL,
            rho_l2_orbitmean_kg_m3 REAL,
            log_ratio_obs REAL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id, source_time_us),
            FOREIGN KEY (storm_id, source_time_us)
                REFERENCES storm_minute_feature_v3(storm_id, source_time_us)
        );
        CREATE TABLE storm_orbit_coverage_v3 (
            storm_id TEXT NOT NULL,
            orbit_id INTEGER NOT NULL,
            expected_30s_sample_count INTEGER NOT NULL,
            l2_valid_sample_count INTEGER NOT NULL,
            paired_sample_count INTEGER NOT NULL,
            l2_coverage REAL NOT NULL,
            paired_coverage REAL NOT NULL,
            is_valid INTEGER NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id, orbit_id),
            FOREIGN KEY (storm_id, orbit_id)
                REFERENCES storm_event_orbit_v3(storm_id, orbit_id)
        );
        CREATE TABLE storm_catalog_v3 (
            storm_id TEXT PRIMARY KEY REFERENCES storm_event_full_orbit_v3(storm_id),
            t0_time_us INTEGER NOT NULL,
            symh_min_nt INTEGER NOT NULL,
            compound INTEGER NOT NULL,
            n_orbits INTEGER NOT NULL,
            n_valid_orbits INTEGER NOT NULL,
            orbit_coverage REAL NOT NULL,
            status TEXT NOT NULL,
            algorithm_version TEXT NOT NULL
        );
    """)


def minute_rows(database: sqlite3.Connection, totals: dict):
    """Input: P2.3 minute keys and paired sums. Output: every minute density row."""
    source = database.execute(
        "SELECT storm_id,source_time_us,orbit_id FROM storm_minute_feature_v3 "
        "ORDER BY storm_id,source_time_us"
    )
    for storm_id, minute_us, orbit_id in source:
        counts = totals.get((storm_id, minute_us), empty_minute())
        paired = counts["pair_count"]
        l2_mean = counts["l2_sum"] / paired if paired else None
        msis_mean = counts["msis_sum"] / paired if paired else None
        orbitmean_count = counts["orbitmean_count"]
        orbitmean = counts["orbitmean_sum"] / orbitmean_count if orbitmean_count else None
        yield (storm_id, minute_us, orbit_id, counts["l2_count"], paired,
               orbitmean_count, l2_mean, msis_mean, orbitmean,
               math.log(l2_mean / msis_mean) if paired else None, ALGORITHM_VERSION)


def store_coverage(database: sqlite3.Connection, totals: dict) -> None:
    """Input: complete orbit table and native counts. Output: coverage and catalog rows."""
    rows = []
    for storm_id, orbit_id, start_us, end_us in database.execute(
        "SELECT storm_id,orbit_id,orbit_start_time_us,orbit_end_time_us "
        "FROM storm_event_orbit_v3 ORDER BY orbit_start_time_us"
    ):
        expected = ((end_us + SECOND_30_US - 1) // SECOND_30_US
                    - (start_us + SECOND_30_US - 1) // SECOND_30_US)
        if expected <= 0:
            raise ValueError(f"Orbit has no expected DNSAPOD slots: {orbit_id}")
        counts = totals.get((storm_id, orbit_id), {"l2_count": 0, "pair_count": 0})
        l2_count, pair_count = counts["l2_count"], counts["pair_count"]
        if pair_count > l2_count or l2_count > expected:
            raise ValueError(f"Invalid DNSAPOD orbit counts: {orbit_id}")
        valid = int(l2_count * COVERAGE_PARTS >= expected * COVERAGE_REQUIRED_PARTS
                    and pair_count * COVERAGE_PARTS >= expected * COVERAGE_REQUIRED_PARTS)
        rows.append((storm_id, orbit_id, expected, l2_count, pair_count,
                     l2_count / expected, pair_count / expected, valid, ALGORITHM_VERSION))
    database.executemany("INSERT INTO storm_orbit_coverage_v3 VALUES (?,?,?,?,?,?,?,?,?)", rows)
    database.execute("""
        INSERT INTO storm_catalog_v3
        SELECT event.storm_id,event.t0_time_us,event.symh_min_nt,event.compound,
               event.n_orbits,SUM(quality.is_valid),
               CAST(SUM(quality.is_valid) AS REAL) / event.n_orbits,
        CASE WHEN SUM(quality.is_valid) * ? >= event.n_orbits * ?
                    THEN 'used' ELSE 'excluded_coverage' END, ?
        FROM storm_event_full_orbit_v3 AS event
        JOIN storm_orbit_coverage_v3 AS quality ON quality.storm_id=event.storm_id
        GROUP BY event.storm_id
    """, (COVERAGE_PARTS, COVERAGE_REQUIRED_PARTS, ALGORITHM_VERSION))


def verify_output(database: sqlite3.Connection) -> dict:
    """Input: populated P2.4 SQLite. Output: checked minute/event counts."""
    minutes = database.execute("SELECT count(*) FROM storm_density_1min_v3").fetchone()[0]
    expected = database.execute("SELECT count(*) FROM storm_minute_feature_v3").fetchone()[0]
    orbits = database.execute("SELECT count(*) FROM storm_orbit_coverage_v3").fetchone()[0]
    expected_orbits = database.execute("SELECT count(*) FROM storm_event_orbit_v3").fetchone()[0]
    storms, used = database.execute(
        "SELECT count(*),sum(status='used') FROM storm_catalog_v3"
    ).fetchone()
    if minutes != expected or orbits != expected_orbits:
        raise ValueError("P2.4 minute or orbit coverage is incomplete.")
    if database.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("P2.4 foreign-key check failed.")
    if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("P2.4 SQLite integrity check failed.")
    return {"minute_rows": minutes, "orbit_rows": orbits, "storms": storms, "used": used}


def write_density_minutes(paths: DensityPaths = DensityPaths()) -> dict:
    """Input: frozen P2.3, DNSAPOD, and weather. Output: new P2.4 SQLite."""
    if paths.output_db.exists():
        raise FileExistsError("P2.4 output already exists.")
    sources = {name: getattr(paths, name) for name in ("input_db", "manifest", "gfz_ap", "solar")}
    for source_path in sources.values():
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
    hashes = {name: sha256_file(path) for name, path in sources.items()}
    paths.output_db.parent.mkdir(parents=True, exist_ok=True)
    db_handle, db_name = tempfile.mkstemp(
        prefix=paths.output_db.stem + ".", suffix=".building", dir=paths.output_db.parent
    )
    os.close(db_handle)
    temporary_db = Path(db_name)
    try:
        shutil.copyfile(paths.input_db, temporary_db)
        if sha256_file(temporary_db) != hashes["input_db"]:
            raise ValueError("P2.3 changed during copy.")
        with closing(sqlite3.connect(temporary_db)) as database:
            database.row_factory = sqlite3.Row
            database.execute("PRAGMA foreign_keys=ON")
            version = database.execute(
                "SELECT value FROM phase2_metadata WHERE name='p2_3_full_orbit_version'"
            ).fetchone()
            if version is None or version[0] != SOURCE_VERSION:
                raise ValueError("Input is not the full-orbit P2.3 checkpoint.")
            zip_paths = checked_manifest(paths, required_days(database))
            weather = load_msis_weather(paths.gfz_ap, paths.solar)
            orbits = database.execute(
                "SELECT storm_id,orbit_id,orbit_start_time_us,orbit_end_time_us "
                "FROM storm_event_orbit_v3 ORDER BY orbit_start_time_us"
            ).fetchall()
            minute_keys = {
                (storm_id, source_time_us) for storm_id, source_time_us in database.execute(
                    "SELECT storm_id,source_time_us FROM storm_minute_feature_v3"
                )
            }
            context = DensityContext(orbits, [row["orbit_start_time_us"] for row in orbits],
                                     minute_keys, weather)
            minute_totals = {}
            orbit_totals = {}
            stats = {"raw_count": 0, "missing_weather": 0, "missing_model": 0}
            for index, zip_path in enumerate(zip_paths, start=1):
                daily = paired_day(zip_path, context)
                for key, values in daily["minutes"].items():
                    total = minute_totals.setdefault(key, empty_minute())
                    for name, value in values.items():
                        total[name] += value
                for key, values in daily["orbits"].items():
                    total = orbit_totals.setdefault(key, {"l2_count": 0, "pair_count": 0})
                    for name, value in values.items():
                        total[name] += value
                for name in stats:
                    stats[name] += daily[name]
                if index % 10 == 0 or index == len(zip_paths):
                    print(f"[{index}/{len(zip_paths)}] DNSAPOD days paired", flush=True)
            with database:
                create_tables(database)
                database.executemany(
                    "INSERT INTO storm_density_1min_v3 VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    minute_rows(database, minute_totals),
                )
                store_coverage(database, orbit_totals)
                database.executemany(
                    "INSERT INTO phase2_metadata VALUES (?,?)",
                    (("p2_4_algorithm_version", ALGORITHM_VERSION),
                     ("p2_4_p2_3_sha256", hashes["input_db"]),
                     ("p2_4_manifest_sha256", hashes["manifest"]),
                     ("p2_4_gfz_sha256", hashes["gfz_ap"]),
                     ("p2_4_solar_sha256", hashes["solar"]),
                     ("p2_4_source_days", str(len(zip_paths))),
                     ("p2_4_raw_samples", str(stats["raw_count"])),
                     ("p2_4_missing_weather", str(stats["missing_weather"])),
                     ("p2_4_missing_model", str(stats["missing_model"]))),
                )
            result = verify_output(database)
        if any(sha256_file(path) != hashes[name] for name, path in sources.items()):
            raise ValueError("P2.4 source changed during build.")
        if paths.output_db.exists():
            raise FileExistsError("P2.4 output appeared during build.")
        os.rename(temporary_db, paths.output_db)
    except BaseException:
        temporary_db.unlink(missing_ok=True)
        raise
    return {**result, "source_days": len(zip_paths), **stats}


def main() -> None:
    """Input: optional P2_3_DB MANIFEST GFZ_JSON SOLAR_CSV OUT_DB. Output: counts."""
    arguments = sys.argv[1:]
    if len(arguments) not in (0, 5):
        raise SystemExit("Usage: python -m satellite_orbit.phase2.prep_24_density_minute "
                         "[P2_3_DB MANIFEST GFZ_JSON SOLAR_CSV OUT_DB]")
    paths = DensityPaths(*map(Path, arguments)) if arguments else DensityPaths()
    print(write_density_minutes(paths))


if __name__ == "__main__":
    main()
