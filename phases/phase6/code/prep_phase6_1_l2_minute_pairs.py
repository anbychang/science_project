"""Build complete one-minute L2 density and POD semi-major-axis pairs."""

import json
import os
import re
import sqlite3
import sys
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from phases.phase0.code.data.density.down_swarm_density_pod import sha256_file
from phases.phase0.code.data.density.load_dnsapod import load_dnsapod
from phases.phase6.code.calc_phase6_1_beff import read_only


FIRST_DAY = date(2023, 7, 1)
LAST_DAY = date(2026, 6, 30)
EXPECTED_DAY_COUNT = (LAST_DAY - FIRST_DAY).days + 1
SOURCE_DAY_PATTERN = re.compile(r"__(\d{8})T")
HALF_MINUTE_US = 30_000_000
MINUTE_US = 60_000_000
EXPECTED_DENSITY_SAMPLES = 2
EXPECTED_POD_SAMPLES = 6
ALGORITHM_VERSION = "phase6_1_l2_pod_minute_pair_v1"


@dataclass(frozen=True)
class MinutePairPaths:
    """Input: Phase 1, DNSAPOD, and output paths. Output: immutable P6.1 paths."""

    phase1: Path = Path(
        "phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite",
    )
    density_folder: Path = Path("phases/phase0/data/raw/swarm_density_pod")
    manifest: Path = Path(
        "phases/phase0/data/raw/swarm_density_pod/manifest_dnsapod_20230701_20260630.json",
    )
    output: Path = Path(
        "phases/phase6/data/sqlite/swarm_a_phase6_1_l2_minute_pairs_v1.sqlite",
    )


@dataclass(frozen=True)
class SourceFile:
    """Input: one verified manifest record. Output: UTC day and local DNSAPOD path."""

    day: date
    path: Path
    sha256: str


def source_day(name: str) -> date:
    """Input: DNSAPOD ZIP name. Output: source UTC day."""
    match = SOURCE_DAY_PATTERN.search(name)
    if match is None:
        raise ValueError(f"Invalid DNSAPOD source name: {name}")
    return datetime.strptime(match.group(1), "%Y%m%d").date()


def load_manifest(paths: MinutePairPaths) -> list[SourceFile]:
    """Input: fixed three-year manifest and folder. Output: verified daily sources."""
    manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
    if (
        manifest.get("collection") != "SW_OPER_DNSAPOD_2_"
        or manifest.get("first_day_utc") != FIRST_DAY.isoformat()
        or manifest.get("last_day_utc") != LAST_DAY.isoformat()
    ):
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
    if (
        [source.day for source in sources] != sorted(source.day for source in sources)
        or len({source.day for source in sources}) != EXPECTED_DAY_COUNT
    ):
        raise ValueError("DNSAPOD manifest days are duplicated or out of order.")
    return sources


def minute_label(time_us: int) -> int:
    """Input: UTC epoch us. Output: nearest whole-minute UTC label us."""
    return (time_us + HALF_MINUTE_US) // MINUTE_US * MINUTE_US


def create_tables(connection: sqlite3.Connection) -> None:
    """Input: empty SQLite connection. Output: P6.1 staging and pair tables."""
    connection.executescript("""
        CREATE TABLE density_minute_stage (
            time_us INTEGER PRIMARY KEY,
            density_sum_kg_m3 REAL NOT NULL,
            sample_count INTEGER NOT NULL,
            first_source_file TEXT NOT NULL,
            last_source_file TEXT NOT NULL
        );
        CREATE TABLE pod_minute_stage (
            time_us INTEGER NOT NULL,
            chunk_id INTEGER NOT NULL,
            semi_major_axis_sum_m REAL NOT NULL,
            sample_count INTEGER NOT NULL,
            PRIMARY KEY (time_us, chunk_id)
        );
        CREATE TABLE phase6_1_l2_pod_minute_pair_v1 (
            time_us INTEGER PRIMARY KEY,
            chunk_id INTEGER NOT NULL,
            mean_semi_major_axis_m REAL NOT NULL CHECK (mean_semi_major_axis_m > 0),
            pod_sample_count INTEGER NOT NULL,
            rho_l2_kg_m3 REAL NOT NULL CHECK (rho_l2_kg_m3 > 0),
            density_sample_count INTEGER NOT NULL,
            first_density_source_file TEXT NOT NULL,
            last_density_source_file TEXT NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE phase6_1_l2_pod_minute_metadata_v1 (
            name TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)


def store_density_minutes(
    connection: sqlite3.Connection,
    sources: list[SourceFile],
) -> int:
    """Input: verified daily DNSAPOD files. Output: native density rows aggregated by minute."""
    valid_sample_count = 0
    for index, source in enumerate(sources, start=1):
        minute_totals: dict[int, tuple[float, int]] = {}
        loaded = load_dnsapod(source.path)
        for sample in loaded["samples"]:
            density = sample["rho_l2_kg_m3"]
            if density is None:
                continue
            time_us = minute_label(int(sample["time_us"]))
            density_sum, count = minute_totals.get(time_us, (0.0, 0))
            minute_totals[time_us] = (density_sum + float(density), count + 1)
            valid_sample_count += 1
        connection.executemany(
            """
            INSERT INTO density_minute_stage VALUES (?,?,?,?,?)
            ON CONFLICT(time_us) DO UPDATE SET
                density_sum_kg_m3=density_sum_kg_m3+excluded.density_sum_kg_m3,
                sample_count=sample_count+excluded.sample_count,
                last_source_file=excluded.last_source_file
            """,
            [
                (time_us, density_sum, count, source.path.name, source.path.name)
                for time_us, (density_sum, count) in minute_totals.items()
            ],
        )
        if index % 100 == 0 or index == len(sources):
            print(f"[{index}/{len(sources)}] DNSAPOD days aggregated", flush=True)
    return valid_sample_count


def store_pod_minutes(
    output: sqlite3.Connection,
    phase1: sqlite3.Connection,
) -> int:
    """Input: usable 10-second Phase 1 mean elements. Output: POD rows aggregated by minute."""
    rows = phase1.execute("""
        SELECT ((m.time_us + ?) / ?) * ? AS minute_us,
               q.chunk_id,
               SUM(m.mean_semi_major_axis_m),
               COUNT(*)
        FROM swarm_a_mean_orbit_elements_v1 AS m
        JOIN swarm_a_pod_quality AS q ON q.time_us = m.time_us
        WHERE q.is_usable = 1 AND m.mean_semi_major_axis_m > 0
        GROUP BY minute_us, q.chunk_id
        ORDER BY minute_us, q.chunk_id
    """, (HALF_MINUTE_US, MINUTE_US, MINUTE_US))
    row_count = 0
    batch = []
    for row in rows:
        batch.append((int(row[0]), int(row[1]), float(row[2]), int(row[3])))
        row_count += int(row[3])
        if len(batch) == 10_000:
            output.executemany("INSERT INTO pod_minute_stage VALUES (?,?,?,?)", batch)
            batch.clear()
    output.executemany("INSERT INTO pod_minute_stage VALUES (?,?,?,?)", batch)
    return row_count


def store_complete_pairs(connection: sqlite3.Connection) -> int:
    """Input: minute staging tables. Output: complete single-chunk minute pairs."""
    connection.execute("""
        INSERT INTO phase6_1_l2_pod_minute_pair_v1
        SELECT p.time_us,
               p.chunk_id,
               p.semi_major_axis_sum_m / p.sample_count,
               p.sample_count,
               d.density_sum_kg_m3 / d.sample_count,
               d.sample_count,
               d.first_source_file,
               d.last_source_file,
               ?
        FROM pod_minute_stage AS p
        JOIN density_minute_stage AS d ON d.time_us = p.time_us
        JOIN (
            SELECT time_us
            FROM pod_minute_stage
            GROUP BY time_us
            HAVING COUNT(*) = 1
        ) AS one_chunk ON one_chunk.time_us = p.time_us
        WHERE p.sample_count = ? AND d.sample_count = ?
        ORDER BY p.time_us
    """, (ALGORITHM_VERSION, EXPECTED_POD_SAMPLES, EXPECTED_DENSITY_SAMPLES))
    return int(connection.execute(
        "SELECT COUNT(*) FROM phase6_1_l2_pod_minute_pair_v1",
    ).fetchone()[0])


def write_pairs(paths: MinutePairPaths, sources: list[SourceFile]) -> dict[str, int]:
    """Input: P6.1 paths and verified sources. Output: new minute-pair SQLite and counts."""
    if paths.output.exists():
        raise FileExistsError(f"Refusing to overwrite existing Phase 6 output: {paths.output}")
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = paths.output.with_suffix(".part")
    temporary.unlink(missing_ok=True)
    try:
        with closing(sqlite3.connect(temporary)) as output:
            create_tables(output)
            density_count = store_density_minutes(output, sources)
            with closing(read_only(paths.phase1)) as phase1:
                pod_count = store_pod_minutes(output, phase1)
            pair_count = store_complete_pairs(output)
            output.executemany(
                "INSERT INTO phase6_1_l2_pod_minute_metadata_v1 VALUES (?,?)",
                [
                    ("algorithm_version", ALGORITHM_VERSION),
                    ("phase1_database", str(paths.phase1)),
                    ("dnsapod_manifest", str(paths.manifest)),
                    ("minute_label", "nearest UTC minute; half-minute rounds forward"),
                    ("coverage", "2 DNSAPOD samples and 6 usable POD samples per minute"),
                    ("objective", "fit one global B_eff only"),
                ],
            )
            output.executescript("DROP TABLE density_minute_stage; DROP TABLE pod_minute_stage;")
            output.commit()
            output.execute("VACUUM")
        os.replace(temporary, paths.output)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "source_day_count": len(sources),
        "valid_density_sample_count": density_count,
        "usable_pod_sample_count": pod_count,
        "paired_minute_count": pair_count,
    }


def run(paths: MinutePairPaths = MinutePairPaths()) -> dict[str, int]:
    """Input: default P6.1 sources. Output: minute-pair SQLite and row counts."""
    return write_pairs(paths, load_manifest(paths))


def main() -> None:
    """Input: no command-line arguments. Output: P6.1 minute-pair summary."""
    if sys.argv[1:]:
        raise SystemExit("Usage: python -m phases.phase6.code.prep_phase6_1_l2_minute_pairs")
    print(run())


if __name__ == "__main__":
    main()
