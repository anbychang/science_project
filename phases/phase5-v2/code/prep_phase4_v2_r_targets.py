"""Copy the Phase 4 V2 event R labels into a Phase 5 V2 snapshot."""

import sqlite3
from contextlib import closing
from pathlib import Path


ROOT = Path("phases/phase5-v2")
SOURCE = Path("phases/phase4-v2/data/sqlite/swarm_a_phase4_v2_shared_tau.sqlite")
OUTPUT = ROOT / "data/sqlite/phase4_v2_r_targets_v2.sqlite"
ALGORITHM_VERSION = "phase4_v2_r_targets_v2"


def load_targets() -> list[tuple]:
    """Input: read-only Phase 4 V2 SQLite. Output: 25 event R label rows."""
    source_uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(source_uri, uri=True)) as source:
        rows = source.execute("""
            SELECT storm_id,r_fit,tau_hours,gain_per_nt,valid_phase_minutes,
                   rmse_log_density,algorithm_version
            FROM phase4_v2_events ORDER BY storm_id
        """).fetchall()
    if len(rows) != 25 or len({row[0] for row in rows}) != 25:
        raise ValueError("Expected 25 distinct Phase 4 V2 event R labels.")
    if len({(row[2], row[3]) for row in rows}) != 1:
        raise ValueError("Phase 4 V2 common tau and gain are inconsistent.")
    return rows


def save_targets(rows: list[tuple]) -> None:
    """Input: 25 Phase 4 V2 label rows. Output: new Phase 5 V2 SQLite snapshot."""
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(OUTPUT) as database:
        database.executescript("""
            CREATE TABLE phase4_v2_r_target (
                storm_id TEXT PRIMARY KEY, r_fit REAL NOT NULL,
                tau_hours REAL NOT NULL, gain_per_nt REAL NOT NULL,
                valid_phase_minutes INTEGER NOT NULL,
                rmse_log_density REAL NOT NULL,
                source_algorithm_version TEXT NOT NULL,
                algorithm_version TEXT NOT NULL
            );
            CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        database.executemany("INSERT INTO phase4_v2_r_target VALUES (?,?,?,?,?,?,?,?)",
                             ((*row, ALGORITHM_VERSION) for row in rows))
        database.executemany("INSERT INTO metadata VALUES (?,?)", [
            ("source_sqlite", str(SOURCE)),
            ("source_table", "phase4_v2_events"),
            ("target_field", "r_fit"),
            ("interpretation", "retrospective fitted density-model parameter"),
            ("algorithm_version", ALGORITHM_VERSION),
        ])
        if (database.execute("SELECT count(*) FROM phase4_v2_r_target").fetchone()[0] != 25
                or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"):
            raise ValueError("Phase 4 V2 R target snapshot failed validation.")


def main() -> None:
    """Input: Phase 4 V2 event R table. Output: Phase 5 V2 target snapshot."""
    rows = load_targets()
    save_targets(rows)
    print(f"Saved {len(rows)} Phase 4 V2 R labels to {OUTPUT}")


if __name__ == "__main__":
    main()
