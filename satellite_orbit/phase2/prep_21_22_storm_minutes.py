"""Copy P2.0, screen storm minima, and store observed minute windows."""

import shutil
import sqlite3
import sys
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from satellite_orbit.phase2.prep_20_symh_1min import sha256_file


MINUTE_US = 60_000_000
HOUR_US = 60 * MINUTE_US
EVENT_BEFORE_US = 48 * HOUR_US
EVENT_AFTER_US = 96 * HOUR_US
NEAR_GAP_US = 24 * HOUR_US
COMPOUND_GAP_US = 48 * HOUR_US
OVERLAP_GAP_US = 144 * HOUR_US
STORM_THRESHOLD_NT = -100
CANDIDATE_VERSION = "storm_minima_1min_v1"
WINDOW_VERSION = "storm_window_1min_v1"
DEFAULT_P20_DB = Path("data/sqlite/2023/swarm_a_phase2_symh_p2_0_1min.sqlite")
DEFAULT_PHASE1_DB = Path("data/sqlite/swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite")
DEFAULT_OUTPUT_DB = Path("data/sqlite/2023/swarm_a_phase2_storm_p2_2.sqlite")


def candidate_id(time_us: int) -> str:
    """Input: UTC minute center in us. Output: stable candidate identifier."""
    time_utc = datetime.fromtimestamp(time_us / 1_000_000, timezone.utc)
    return time_utc.strftime("C%Y%m%dT%H%M")


def constant_runs(rows):
    """Input: ordered [minute_row, ...]. Output: contiguous constant-value runs."""
    run_start = run_end = run_value = None
    for time_us, symh_nt in rows:
        if run_start is None:
            run_start = run_end = time_us
            run_value = symh_nt
        elif time_us == run_end + MINUTE_US and symh_nt == run_value:
            run_end = time_us
        else:
            yield run_start, run_end, run_value
            run_start = run_end = time_us
            run_value = symh_nt
    if run_start is not None:
        yield run_start, run_end, run_value


def find_local_minima(connection: sqlite3.Connection, t0_range: tuple[int, int]) -> list[dict]:
    """Input: minute table and inclusive t0 range. Output: raw sub-threshold minima."""
    first_us, last_us = t0_range
    rows = connection.execute(
        "SELECT source_time_us, symh_nt FROM symh_1min_v1 "
        "WHERE source_time_us BETWEEN ? AND ? ORDER BY source_time_us",
        (first_us - MINUTE_US, last_us + MINUTE_US),
    )
    previous = current = None
    minima = []
    for upcoming in constant_runs(rows):
        if previous is not None and current is not None:
            start_us, end_us, value_nt = current
            if (
                first_us <= start_us <= last_us
                and value_nt < STORM_THRESHOLD_NT
                and previous[1] + MINUTE_US == start_us
                and end_us + MINUTE_US == upcoming[0]
                and value_nt < previous[2]
                and value_nt < upcoming[2]
            ):
                minima.append(
                    {
                        "time_us": start_us,
                        "symh_nt": value_nt,
                        "compound": False,
                        "status": "selected",
                        "note": "",
                    }
                )
        previous, current = current, upcoming
    return minima


def group_by_gap(candidates: list[dict], gap_us: int) -> list[list[dict]]:
    """Input: time-sorted candidates and strict gap in us. Output: adjacent groups."""
    groups = []
    for candidate in candidates:
        if not groups or candidate["time_us"] - groups[-1][-1]["time_us"] >= gap_us:
            groups.append([candidate])
        else:
            groups[-1].append(candidate)
    return groups


def stronger_candidate(group: list[dict]) -> dict:
    """Input: nonempty candidate group. Output: deepest, earliest-tie candidate."""
    return min(group, key=lambda item: (item["symh_nt"], item["time_us"]))


def screen_candidates(candidates: list[dict]) -> list[dict]:
    """Input: raw minima in time order. Output: selected independent candidates."""
    near_representatives = []
    for group in group_by_gap(candidates, NEAR_GAP_US):
        strongest = stronger_candidate(group)
        near_representatives.append(strongest)
        for candidate in group:
            if candidate is not strongest:
                candidate["status"] = "excluded_sub24"
                candidate["note"] = f"deeper_candidate={candidate_id(strongest['time_us'])}"

    compound_representatives = []
    for group in group_by_gap(near_representatives, COMPOUND_GAP_US):
        strongest = stronger_candidate(group)
        strongest["compound"] = len(group) > 1
        compound_representatives.append(strongest)
        for candidate in group:
            if candidate is not strongest:
                candidate["status"] = "merged_compound"
                candidate["note"] = f"compound_representative={candidate_id(strongest['time_us'])}"

    selected = []
    for candidate in sorted(
        compound_representatives, key=lambda item: (item["symh_nt"], item["time_us"])
    ):
        overlapping = [
            stronger for stronger in selected
            if abs(candidate["time_us"] - stronger["time_us"]) < OVERLAP_GAP_US
        ]
        if overlapping:
            candidate["status"] = "excluded_overlap"
            candidate["note"] = f"stronger_candidate={candidate_id(overlapping[0]['time_us'])}"
        else:
            selected.append(candidate)
    return sorted(selected, key=lambda item: item["time_us"])


def phase1_t0_range(phase1_db: Path) -> tuple[int, int]:
    """Input: read-only Phase 1 SQLite. Output: inclusive minute-aligned t0 range in us."""
    with closing(sqlite3.connect(f"file:{phase1_db.as_posix()}?mode=ro", uri=True)) as connection:
        first_us, last_us = connection.execute(
            "SELECT "
            "(SELECT time_us FROM swarm_a_mean_orbit_elements_v1 ORDER BY time_us LIMIT 1), "
            "(SELECT time_us FROM swarm_a_mean_orbit_elements_v1 ORDER BY time_us DESC LIMIT 1)"
        ).fetchone()
    if first_us is None or last_us is None:
        raise ValueError("Phase 1 mean-element table is empty.")
    first_t0_us = ((first_us + MINUTE_US - 1) // MINUTE_US) * MINUTE_US + EVENT_BEFORE_US
    last_t0_us = (last_us // MINUTE_US) * MINUTE_US - EVENT_AFTER_US
    if first_t0_us > last_t0_us:
        raise ValueError("Phase 1 coverage cannot contain a full storm window.")
    return first_t0_us, last_t0_us


def create_derived_tables(connection: sqlite3.Connection) -> None:
    """Input: copied P2.0 connection. Output: versioned P2.1 and P2.2 tables."""
    connection.executescript(
        """
        CREATE TABLE storm_candidate_v1 (
            candidate_id TEXT PRIMARY KEY,
            t0_time_us INTEGER NOT NULL UNIQUE,
            symh_min_nt INTEGER NOT NULL,
            compound INTEGER NOT NULL CHECK (compound IN (0, 1)),
            symh_screening_status TEXT NOT NULL CHECK (
                symh_screening_status IN
                ('selected', 'excluded_sub24', 'merged_compound', 'excluded_overlap')
            ),
            symh_screening_note TEXT NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE storm_symh_1min_v1 (
            candidate_id TEXT NOT NULL REFERENCES storm_candidate_v1(candidate_id),
            source_time_us INTEGER NOT NULL,
            t_rel_h REAL NOT NULL,
            symh_nt INTEGER NOT NULL,
            symh_version INTEGER NOT NULL,
            source_file_name TEXT NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (candidate_id, source_time_us)
        );
        """
    )


def write_candidate_rows(connection: sqlite3.Connection, candidates: list[dict]) -> None:
    """Input: copied output and screened minima. Output: stored P2.1 candidate rows."""
    connection.executemany(
        "INSERT INTO storm_candidate_v1 VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            (
                candidate_id(item["time_us"]),
                item["time_us"],
                item["symh_nt"],
                int(item["compound"]),
                item["status"],
                item["note"],
                CANDIDATE_VERSION,
            )
            for item in candidates
        ),
    )


def write_event_windows(connection: sqlite3.Connection, selected: list[dict]) -> None:
    """Input: copied output and selected storms. Output: observed P2.2 minute rows."""
    for candidate in selected:
        t0_us = candidate["time_us"]
        connection.execute(
            "INSERT INTO storm_symh_1min_v1 "
            "SELECT ?, source_time_us, (source_time_us - ?) / ?, symh_nt, "
            "symh_version, source_file_name, ? FROM symh_1min_v1 "
            "WHERE source_time_us >= ? AND source_time_us < ? "
            "ORDER BY source_time_us",
            (
                candidate_id(t0_us),
                t0_us,
                float(HOUR_US),
                WINDOW_VERSION,
                t0_us - EVENT_BEFORE_US,
                t0_us + EVENT_AFTER_US,
            ),
        )


def write_phase2_through_p22(
    p20_db: Path = DEFAULT_P20_DB,
    phase1_db: Path = DEFAULT_PHASE1_DB,
    output_db: Path = DEFAULT_OUTPUT_DB,
) -> dict[str, int]:
    """Input: frozen P2.0, Phase 1, new output path. Output: P2.1/P2.2 row counts."""
    p20_db = Path(p20_db).resolve()
    phase1_db = Path(phase1_db).resolve()
    output_db = Path(output_db).resolve()
    if not p20_db.is_file() or not phase1_db.is_file():
        raise FileNotFoundError("P2.0 and Phase 1 SQLite inputs must exist.")
    if output_db.exists():
        raise FileExistsError(f"Phase 2 output already exists: {output_db}")
    output_db.parent.mkdir(parents=True, exist_ok=True)
    t0_range = phase1_t0_range(phase1_db)
    p20_sha256 = sha256_file(p20_db)
    phase1_sha256 = sha256_file(phase1_db)

    with tempfile.NamedTemporaryFile(
        prefix=f"{output_db.stem}.", suffix=".building", dir=output_db.parent, delete=False
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)
    try:
        shutil.copyfile(p20_db, temporary_path)
        if sha256_file(temporary_path) != p20_sha256:
            raise ValueError("Copied P2.0 bytes do not match the frozen input.")
        connection = sqlite3.connect(temporary_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            version = connection.execute(
                "SELECT value FROM phase2_metadata WHERE name = 'algorithm_version'"
            ).fetchone()
            if version != ("symh_1min_csv_v1",):
                raise ValueError("Input is not the verified one-minute P2.0 dataset.")
            candidates = find_local_minima(connection, t0_range)
            selected = screen_candidates(candidates)
            create_derived_tables(connection)
            with connection:
                write_candidate_rows(connection, candidates)
                write_event_windows(connection, selected)
                connection.executemany(
                    "INSERT INTO phase2_metadata VALUES (?, ?)",
                    (
                        ("p2_0_sha256", p20_sha256),
                        ("phase1_path", str(phase1_db)),
                        ("phase1_sha256", phase1_sha256),
                        ("pilot_t0_first_us", str(t0_range[0])),
                        ("pilot_t0_last_us", str(t0_range[1])),
                        ("p2_1_algorithm_version", CANDIDATE_VERSION),
                        ("p2_2_algorithm_version", WINDOW_VERSION),
                        ("symh_threshold_nt", str(STORM_THRESHOLD_NT)),
                    ),
                )
            candidate_count = len(candidates)
            selected_count = len(selected)
            window_count = connection.execute(
                "SELECT count(*) FROM storm_symh_1min_v1"
            ).fetchone()[0]
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("P2.2 SQLite integrity check failed.")
        finally:
            connection.close()
        if output_db.exists():
            raise FileExistsError(f"Phase 2 output appeared during build: {output_db}")
        temporary_path.replace(output_db)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return {
        "candidate_rows": candidate_count,
        "selected_events": selected_count,
        "window_minute_rows": window_count,
    }


def main() -> None:
    """Input: optional P2.0, Phase 1, output paths. Output: printed row counts."""
    arguments = sys.argv[1:]
    if len(arguments) not in (0, 3):
        raise SystemExit(
            "Usage: python -m satellite_orbit.phase2.prep_21_22_storm_minutes "
            "[P20_DB PHASE1_DB OUTPUT_DB]"
        )
    paths = tuple(map(Path, arguments)) if arguments else (
        DEFAULT_P20_DB,
        DEFAULT_PHASE1_DB,
        DEFAULT_OUTPUT_DB,
    )
    print(write_phase2_through_p22(*paths))


if __name__ == "__main__":
    main()
