"""Pair the full three-year DNSAPOD orbit-mean density with Phase 1 orbit means."""

import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from phases.phase0.code.data.density.down_swarm_density_pod import sha256_file
from phases.phase0.code.data.density.load_dnsapod import load_dnsapod
from phases.phase6.code.calc_phase6_l2_density_decay import read_only
from phases.phase6.code.prep_phase6_quiet_audit import (
    DensitySample,
    OrbitRow,
    nearest_density_sample,
)


FIRST_DAY = date(2023, 7, 1)
LAST_DAY = date(2026, 6, 30)
EXPECTED_DAY_COUNT = (LAST_DAY - FIRST_DAY).days + 1
SOURCE_DAY_PATTERN = re.compile(r"__(\d{8})T")
ALGORITHM_VERSION = "phase6_l2_three_year_nearest_orbitmean_v1"


@dataclass(frozen=True)
class PairPaths:
    """Input: Phase 1, DNSAPOD manifest/folder, and output paths.
    Output: immutable three-year pairing paths."""

    phase1: Path = Path(
        "phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite",
    )
    density_folder: Path = Path("phases/phase0/data/raw/swarm_density_pod")
    manifest: Path = Path(
        "phases/phase0/data/raw/swarm_density_pod/manifest_dnsapod_20230701_20260630.json",
    )
    output: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_l2_three_year_pairs_v1.sqlite",
    )


@dataclass(frozen=True)
class SourceFile:
    """Input: one verified manifest record. Output: UTC day and local DNSAPOD path."""

    day: date
    path: Path
    sha256: str


@dataclass(frozen=True)
class OrbitPair:
    """Input: one Phase 1 orbit and nearest L2 orbit-mean sample.
    Output: source-keyed three-year orbit-density pair."""

    orbit: OrbitRow
    chunk_id: int
    density: DensitySample


def source_day(name: str) -> date:
    """Input: DNSAPOD ZIP name. Output: source UTC day."""
    match = SOURCE_DAY_PATTERN.search(name)
    if match is None:
        raise ValueError(f"Invalid DNSAPOD source name: {name}")
    return datetime.strptime(match.group(1), "%Y%m%d").date()


def load_manifest(paths: PairPaths) -> list[SourceFile]:
    """Input: fixed three-year manifest and density folder. Output: verified daily sources."""
    manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
    if (manifest.get("collection") != "SW_OPER_DNSAPOD_2_"
            or manifest.get("first_day_utc") != FIRST_DAY.isoformat()
            or manifest.get("last_day_utc") != LAST_DAY.isoformat()):
        raise ValueError("DNSAPOD manifest has the wrong collection or UTC range.")
    records = manifest.get("files")
    if not isinstance(records, list) or len(records) != EXPECTED_DAY_COUNT:
        raise ValueError("DNSAPOD manifest does not contain every three-year UTC day.")
    sources = []
    for record in records:
        path = paths.density_folder / str(record["name"])
        if not path.exists():
            raise FileNotFoundError(path)
        expected_hash = str(record["sha256"])
        if sha256_file(path) != expected_hash:
            raise ValueError(f"DNSAPOD source hash changed: {path}")
        sources.append(SourceFile(source_day(path.name), path, expected_hash))
    if ([source.day for source in sources] != sorted(source.day for source in sources)
            or len({source.day for source in sources}) != EXPECTED_DAY_COUNT):
        raise ValueError("DNSAPOD manifest days are duplicated or out of order.")
    return sources


def phase1_orbits(connection: sqlite3.Connection) -> dict[date, list[tuple[OrbitRow, int]]]:
    """Input: Phase 1 checkpoint. Output: UTC day -> ordered complete phase orbits."""
    rows = connection.execute("""
        SELECT time_us,orbit_start_time_us,phase_weighted_mean_semi_major_axis_m,chunk_id
        FROM swarm_a_phase_orbit_mean_v2
        ORDER BY time_us
    """)
    by_day: dict[date, list[tuple[OrbitRow, int]]] = defaultdict(list)
    for time_us, orbit_start_time_us, mean_a_m, chunk_id in rows:
        day = datetime.fromtimestamp(int(time_us) / 1_000_000, timezone.utc).date()
        by_day[day].append((
            OrbitRow(int(time_us), int(orbit_start_time_us), float(mean_a_m)),
            int(chunk_id),
        ))
    if not by_day:
        raise ValueError("Phase 1 has no complete phase-orbit means.")
    return dict(by_day)


def density_samples(source: SourceFile) -> tuple[int, list[DensitySample]]:
    """Input: one verified DNSAPOD ZIP. Output: raw count and valid orbit-mean samples."""
    loaded = load_dnsapod(source.path)
    samples = [
        DensitySample(
            int(sample["time_us"]),
            float(sample["rho_l2_orbitmean_kg_m3"]),
            str(sample["source_file"]),
        )
        for sample in loaded["samples"]
        if sample["rho_l2_orbitmean_kg_m3"] is not None
    ]
    return int(loaded["raw_count"]), samples


def pair_day(
    orbit_rows: list[tuple[OrbitRow, int]],
    samples: list[DensitySample],
) -> list[OrbitPair]:
    """Input: one UTC day's Phase 1 orbits and L2 samples. Output: nearest valid pairs."""
    pairs = []
    for orbit, chunk_id in orbit_rows:
        sample = nearest_density_sample(samples, orbit.time_us)
        if sample is not None:
            pairs.append(OrbitPair(orbit, chunk_id, sample))
    return pairs


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: empty Phase 6 SQLite connection. Output: three-year pair and audit tables."""
    connection.executescript("""
        CREATE TABLE phase6_l2_three_year_pair_v1 (
            time_us INTEGER PRIMARY KEY,
            orbit_start_time_us INTEGER NOT NULL,
            mean_semi_major_axis_m REAL NOT NULL CHECK (mean_semi_major_axis_m > 0),
            chunk_id INTEGER NOT NULL,
            density_time_us INTEGER NOT NULL,
            rho_l2_orbitmean_kg_m3 REAL NOT NULL CHECK (rho_l2_orbitmean_kg_m3 > 0),
            density_offset_s REAL NOT NULL,
            density_source_file TEXT NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_l2_three_year_day_audit_v1 (
            day_start_time_us INTEGER PRIMARY KEY,
            density_source_file TEXT NOT NULL,
            raw_density_sample_count INTEGER NOT NULL,
            valid_orbitmean_sample_count INTEGER NOT NULL,
            phase1_orbit_count INTEGER NOT NULL,
            paired_orbit_count INTEGER NOT NULL,
            status TEXT NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_l2_three_year_pair_metadata_v1 (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def day_start_us(day: date) -> int:
    """Input: UTC date. Output: UTC midnight in microseconds."""
    return int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp() * 1_000_000)


def write_pairs(
    paths: PairPaths,
    sources: list[SourceFile],
    orbits_by_day: dict[date, list[tuple[OrbitRow, int]]],
) -> dict[str, int]:
    """Input: sources, Phase 1 orbits, and paths. Output: new pair SQLite and counts."""
    if paths.output.exists():
        raise FileExistsError(f"Refusing to overwrite existing Phase 6 output: {paths.output}")
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = paths.output.with_suffix(".part")
    if temporary.exists():
        temporary.unlink()
    paired_count = 0
    incomplete_day_count = 0
    try:
        with closing(sqlite3.connect(temporary)) as output:
            create_tables(output)
            for index, source in enumerate(sources, start=1):
                raw_count, samples = density_samples(source)
                orbit_rows = orbits_by_day.get(source.day, [])
                pairs = pair_day(orbit_rows, samples)
                status = "complete" if len(pairs) == len(orbit_rows) else "incomplete_pairing"
                incomplete_day_count += int(status != "complete")
                paired_count += len(pairs)
                output.executemany(
                    "INSERT INTO phase6_l2_three_year_pair_v1 VALUES (?,?,?,?,?,?,?,?,?)",
                    [(
                        pair.orbit.time_us,
                        pair.orbit.orbit_start_time_us,
                        pair.orbit.mean_semi_major_axis_m,
                        pair.chunk_id,
                        pair.density.time_us,
                        pair.density.density_kg_m3,
                        (pair.density.time_us - pair.orbit.time_us) / 1_000_000,
                        pair.density.source_file,
                        ALGORITHM_VERSION,
                    ) for pair in pairs],
                )
                output.execute(
                    "INSERT INTO phase6_l2_three_year_day_audit_v1 VALUES (?,?,?,?,?,?,?,?)",
                    (
                        day_start_us(source.day), source.path.name, raw_count, len(samples),
                        len(orbit_rows), len(pairs), status, ALGORITHM_VERSION,
                    ),
                )
                if index % 50 == 0 or index == len(sources):
                    print(f"[{index}/{len(sources)}] DNSAPOD days paired", flush=True)
            output.executemany(
                "INSERT INTO phase6_l2_three_year_pair_metadata_v1 VALUES (?,?)",
                [
                    ("algorithm_version", ALGORITHM_VERSION),
                    ("phase1_database", str(paths.phase1)),
                    ("dnsapod_manifest", str(paths.manifest)),
                    ("first_day_utc", FIRST_DAY.isoformat()),
                    ("last_day_utc", LAST_DAY.isoformat()),
                    ("density_field", "DNSAPOD density_orbitmean"),
                    ("density_match_limit_s", "60"),
                ],
            )
            output.commit()
        os.replace(temporary, paths.output)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "source_day_count": len(sources),
        "paired_orbit_count": paired_count,
        "incomplete_day_count": incomplete_day_count,
    }


def run(paths: PairPaths = PairPaths()) -> dict[str, int]:
    """Input: default three-year sources. Output: one new pair SQLite and row counts."""
    sources = load_manifest(paths)
    with closing(read_only(paths.phase1)) as phase1:
        orbits_by_day = phase1_orbits(phase1)
    return write_pairs(paths, sources, orbits_by_day)


def main() -> None:
    """Input: no command-line arguments. Output: three-year L2 pair SQLite summary."""
    if sys.argv[1:]:
        raise SystemExit("Usage: python -m phases.phase6.code.prep_phase6_l2_three_year_pairs")
    print(run())


if __name__ == "__main__":
    main()
