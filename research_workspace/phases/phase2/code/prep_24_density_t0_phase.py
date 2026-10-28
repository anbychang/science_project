"""Pair DNSAPOD density samples with MSIS in P2.3 t0-phase minute windows."""

import json
import math
import os
import shutil
import sqlite3
import sys
import tempfile
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_workspace.phases.phase0.code.calculation.density.calc_msis_p2_4 import (
    calculate_msis_density,
    load_msis_weather,
    sample_drivers,
)
from research_workspace.phases.phase0.code.data.density.down_swarm_density_pod import SOURCE_NAME, sha256_file
from research_workspace.phases.phase0.code.data.density.load_dnsapod import load_dnsapod


ALGORITHM_VERSION = "storm_density_t0_phase_v5"
SOURCE_VERSION = "storm_minute_t0_phase_v5"
SECOND_30_US = 30_000_000
MINUTE_US = 60_000_000
COVERAGE_REQUIRED = 0.80


@dataclass(frozen=True)
class DensityPaths:
    """Input: P2.3, DNSAPOD manifest, weather files. Output: P2.4 path record."""

    input_db: Path = Path("research_workspace/phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_3_t0_phase_v5.sqlite")
    manifest: Path = Path("research_workspace/phases/phase0/data/raw/swarm_density_pod/manifest_dnsapod_20230701_20260630.json")
    gfz_ap: Path = Path("research_workspace/phases/phase0/data/raw/geomagnetic/gfz_ap_2023-07-01_2026-06-30.json")
    solar: Path = Path("research_workspace/phases/phase0/data/raw/space_weather/SW-All.csv")
    output_db: Path = Path("research_workspace/phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_4_density_t0_phase_v5.sqlite")


@dataclass(frozen=True)
class DensityContext:
    """Input: selected minute keys and MSIS weather. Output: immutable pairing context."""

    storms_by_minute: dict[int, tuple[str, ...]]
    weather: dict


def minute_label(time_us: int) -> int:
    """Input: DNSAPOD sample UTC epoch us. Output: its assumed 1-minute center label."""
    return (time_us + SECOND_30_US) // MINUTE_US * MINUTE_US


def empty_minute() -> dict:
    """Input: none. Output: zeroed native sample counts and density sums."""
    return {
        "l2_count": 0,
        "pair_count": 0,
        "orbitmean_count": 0,
        "l2_sum": 0.0,
        "msis_sum": 0.0,
        "orbitmean_sum": 0.0,
    }


def required_days(database: sqlite3.Connection) -> set[str]:
    """Input: P2.3 event minute bounds. Output: UTC days whose 30-second support is needed."""
    days = set()
    for start_us, end_us in database.execute(
        "SELECT minute_start_time_us,minute_end_time_us FROM storm_event_t0_phase_v5"
    ):
        first = datetime.fromtimestamp((start_us - SECOND_30_US) / 1_000_000, timezone.utc).date()
        last = datetime.fromtimestamp((end_us - SECOND_30_US - 1) / 1_000_000, timezone.utc).date()
        day = first
        while day <= last:
            days.add(day.strftime("%Y%m%d"))
            day += timedelta(days=1)
    return days


def checked_manifest(paths: DensityPaths, days: set[str]) -> list[Path]:
    """Input: DNSAPOD manifest and UTC days. Output: hash-checked native ZIPs."""
    manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
    if manifest.get("collection") != "SW_OPER_DNSAPOD_2_":
        raise ValueError("DNSAPOD manifest has the wrong product collection.")
    records = {}
    for record in manifest["files"]:
        match = SOURCE_NAME.fullmatch(record["name"])
        if match is None or match[1] not in days:
            continue
        if match[2] != "0301" or match[1] in records:
            raise ValueError(f"Unexpected DNSAPOD source version: {record['name']}")
        records[match[1]] = record
    if set(records) != days:
        raise ValueError(f"DNSAPOD manifest lacks {len(days - records.keys())} required days.")
    files = []
    for day in sorted(days):
        record = records[day]
        zip_path = paths.manifest.parent / record["name"]
        if not zip_path.is_file() or sha256_file(zip_path) != record["sha256"]:
            raise ValueError(f"DNSAPOD ZIP missing or changed: {zip_path}")
        files.append(zip_path)
    return files


def minute_targets(database: sqlite3.Connection) -> dict[int, tuple[str, ...]]:
    """Input: P2.3 minute features. Output: UTC minute label -> selected storm IDs."""
    targets = defaultdict(list)
    for storm_id, source_time_us in database.execute(
        "SELECT storm_id,source_time_us FROM storm_minute_feature_v5"
    ):
        targets[source_time_us].append(storm_id)
    return {time_us: tuple(storms) for time_us, storms in targets.items()}


def pair_day(zip_path: Path, context: DensityContext) -> dict:
    """Input: one DNSAPOD ZIP and P2.3 context. Output: minute totals plus audit counts."""
    loaded = load_dnsapod(zip_path)
    totals = {}
    candidates = []
    drivers = []
    missing_weather = 0
    for sample in loaded["samples"]:
        storm_ids = context.storms_by_minute.get(minute_label(sample["time_us"]))
        if storm_ids is None:
            continue
        minute_us = minute_label(sample["time_us"])
        for storm_id in storm_ids:
            counts = totals.setdefault((storm_id, minute_us), empty_minute())
            orbitmean = sample["rho_l2_orbitmean_kg_m3"]
            if orbitmean is not None:
                counts["orbitmean_count"] += 1
                counts["orbitmean_sum"] += orbitmean
        if sample["rho_l2_kg_m3"] is None:
            continue
        driver = sample_drivers(sample["time_us"], context.weather)
        for storm_id in storm_ids:
            totals[(storm_id, minute_us)]["l2_count"] += 1
        if driver is None:
            missing_weather += 1
            continue
        candidates.append((sample, storm_ids, minute_us))
        drivers.append(driver)
    model_densities = calculate_msis_density([row[0] for row in candidates], drivers)
    missing_model = 0
    for (sample, storm_ids, minute_us), msis_density in zip(candidates, model_densities, strict=True):
        if msis_density is None:
            missing_model += 1
            continue
        for storm_id in storm_ids:
            counts = totals[(storm_id, minute_us)]
            counts["pair_count"] += 1
            counts["l2_sum"] += sample["rho_l2_kg_m3"]
            counts["msis_sum"] += msis_density
    return {
        "totals": totals,
        "raw_count": loaded["raw_count"],
        "missing_weather": missing_weather,
        "missing_model": missing_model,
    }


def merge_totals(target: dict, incoming: dict) -> None:
    """Input: accumulated and daily minute totals. Output: accumulated totals updated in place."""
    for key, counts in incoming.items():
        total = target.setdefault(key, empty_minute())
        for name, value in counts.items():
            total[name] += value


def create_tables(database: sqlite3.Connection) -> None:
    """Input: copied P2.3 SQLite. Output: empty P2.4 minute-density and event-coverage tables."""
    database.executescript("""
        CREATE TABLE storm_density_1min_v5 (
            storm_id TEXT NOT NULL,
            source_time_us INTEGER NOT NULL,
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
                REFERENCES storm_minute_feature_v5(storm_id, source_time_us)
        );
        CREATE TABLE storm_event_coverage_v5 (
            storm_id TEXT PRIMARY KEY REFERENCES storm_event_t0_phase_v5(storm_id),
            expected_30s_sample_count INTEGER NOT NULL,
            l2_valid_sample_count INTEGER NOT NULL,
            paired_sample_count INTEGER NOT NULL,
            l2_coverage REAL NOT NULL,
            paired_coverage REAL NOT NULL,
            is_valid_80pct INTEGER NOT NULL,
            status TEXT NOT NULL,
            algorithm_version TEXT NOT NULL
        );
    """)


def density_rows(database: sqlite3.Connection, totals: dict):
    """Input: P2.3 minute rows and paired totals. Output: one P2.4 density row per minute."""
    for storm_id, minute_us in database.execute(
        "SELECT storm_id,source_time_us FROM storm_minute_feature_v5 ORDER BY storm_id,source_time_us"
    ):
        counts = totals.get((storm_id, minute_us), empty_minute())
        paired = counts["pair_count"]
        l2_density = counts["l2_sum"] / paired if paired else None
        msis_density = counts["msis_sum"] / paired if paired else None
        orbitmean_count = counts["orbitmean_count"]
        orbitmean_density = counts["orbitmean_sum"] / orbitmean_count if orbitmean_count else None
        log_ratio = math.log(l2_density / msis_density) if paired else None
        yield (
            storm_id,
            minute_us,
            counts["l2_count"],
            paired,
            orbitmean_count,
            l2_density,
            msis_density,
            orbitmean_density,
            log_ratio,
            ALGORITHM_VERSION,
        )


def coverage_status(expected: int, l2_count: int, paired_count: int) -> tuple[int, str]:
    """Input: event expected and observed native counts. Output: 80-percent decision and status."""
    if expected <= 0 or paired_count > l2_count or l2_count > expected:
        raise ValueError("Invalid DNSAPOD event coverage counts.")
    is_valid = int(l2_count / expected >= COVERAGE_REQUIRED
                   and paired_count / expected >= COVERAGE_REQUIRED)
    return is_valid, "used" if is_valid else "excluded_coverage"


def store_event_coverage(database: sqlite3.Connection) -> None:
    """Input: complete P2.3/P2.4 minute tables. Output: one coverage decision per storm."""
    rows = database.execute("""
        SELECT event.storm_id,
               count(density.source_time_us) * 2,
               sum(density.l2_valid_sample_count),
               sum(density.paired_sample_count)
        FROM storm_event_t0_phase_v5 AS event
        JOIN storm_density_1min_v5 AS density ON density.storm_id=event.storm_id
        GROUP BY event.storm_id
        ORDER BY event.t0_time_us
    """).fetchall()
    output_rows = []
    for storm_id, expected, l2_count, paired_count in rows:
        is_valid, status = coverage_status(expected, l2_count, paired_count)
        output_rows.append((
            storm_id,
            expected,
            l2_count,
            paired_count,
            l2_count / expected,
            paired_count / expected,
            is_valid,
            status,
            ALGORITHM_VERSION,
        ))
    database.executemany("INSERT INTO storm_event_coverage_v5 VALUES (?,?,?,?,?,?,?,?,?)", output_rows)


def verify_output(database: sqlite3.Connection) -> dict:
    """Input: populated P2.4 SQLite. Output: validated counts and selected-event count."""
    minutes = database.execute("SELECT count(*) FROM storm_density_1min_v5").fetchone()[0]
    expected_minutes = database.execute("SELECT count(*) FROM storm_minute_feature_v5").fetchone()[0]
    storms, used = database.execute(
        "SELECT count(*),sum(status='used') FROM storm_event_coverage_v5"
    ).fetchone()
    expected_storms = database.execute("SELECT count(*) FROM storm_event_t0_phase_v5").fetchone()[0]
    if minutes != expected_minutes or storms != expected_storms:
        raise ValueError("P2.4 minute or event coverage rows are incomplete.")
    if database.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("P2.4 foreign-key check failed.")
    if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("P2.4 SQLite integrity check failed.")
    return {"minute_rows": minutes, "storms": storms, "used": used}


def write_density_minutes(paths: DensityPaths = DensityPaths()) -> dict:
    """Input: frozen P2.3, native DNSAPOD, offline MSIS drivers. Output: checked P2.4 SQLite."""
    if paths.output_db.exists():
        raise FileExistsError("P2.4 output already exists.")
    sources = {
        "input_db": paths.input_db,
        "manifest": paths.manifest,
        "gfz_ap": paths.gfz_ap,
        "solar": paths.solar,
    }
    for path in sources.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    hashes = {name: sha256_file(path) for name, path in sources.items()}
    paths.output_db.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=paths.output_db.stem + ".", suffix=".building", dir=paths.output_db.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        shutil.copyfile(paths.input_db, temporary)
        if sha256_file(temporary) != hashes["input_db"]:
            raise ValueError("P2.3 changed during copy.")
        with closing(sqlite3.connect(temporary)) as database:
            database.row_factory = sqlite3.Row
            database.execute("PRAGMA foreign_keys=ON")
            version = database.execute(
                "SELECT value FROM phase2_metadata WHERE name='p2_3_t0_phase_version'"
            ).fetchone()
            if version is None or version[0] != SOURCE_VERSION:
                raise ValueError("Input is not the t0-phase P2.3 checkpoint.")
            zip_paths = checked_manifest(paths, required_days(database))
            context = DensityContext(minute_targets(database), load_msis_weather(paths.gfz_ap, paths.solar))
            totals = {}
            stats = {"raw_count": 0, "missing_weather": 0, "missing_model": 0}
            for index, zip_path in enumerate(zip_paths, start=1):
                daily = pair_day(zip_path, context)
                merge_totals(totals, daily["totals"])
                for name in stats:
                    stats[name] += daily[name]
                if index % 10 == 0 or index == len(zip_paths):
                    print(f"[{index}/{len(zip_paths)}] DNSAPOD days paired", flush=True)
            with database:
                create_tables(database)
                database.executemany(
                    "INSERT INTO storm_density_1min_v5 VALUES (?,?,?,?,?,?,?,?,?,?)",
                    density_rows(database, totals),
                )
                store_event_coverage(database)
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
        os.rename(temporary, paths.output_db)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return {**result, "source_days": len(zip_paths), **stats}


def main() -> None:
    """Input: optional P2.3, manifest, weather, output paths. Output: P2.4 counts."""
    arguments = sys.argv[1:]
    if len(arguments) not in (0, 5):
        raise SystemExit("Usage: python -m research_workspace.phases.phase2.code.prep_24_density_t0_phase "
                         "[P2_3_DB MANIFEST GFZ_JSON SOLAR_CSV OUTPUT_DB]")
    paths = DensityPaths(*map(Path, arguments)) if arguments else DensityPaths()
    print(write_density_minutes(paths))


if __name__ == "__main__":
    main()
