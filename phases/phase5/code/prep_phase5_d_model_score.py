"""Score the saved Phase 4 D-model on Trial 10-12 held-out orbit positions."""

import math
import os
import sqlite3
import tempfile
from collections import defaultdict
from contextlib import closing
from pathlib import Path


PREDICTIONS = Path(
    "phases/phase5-trial10/data/sqlite/swarm_a_phase5_m1_shape_gpr_v1.sqlite"
)
D_MODEL = Path("phases/phase4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite")
OUTPUT = Path("phases/phase5/data/sqlite/swarm_a_phase5_d_model_same_orbits_v1.sqlite")
VERSION = "phase5_d_model_same_orbits_v1"


def load_aligned_rows() -> list[tuple]:
    """Input: read-only Trial 10 and Phase 4 SQLite. Output: [(fold, storm, L2, M1, D)]."""
    prediction_uri = f"file:{PREDICTIONS.resolve().as_posix()}?mode=ro"
    d_model_uri = f"file:{D_MODEL.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(prediction_uri, uri=True)) as database:
        database.execute("ATTACH DATABASE ? AS d_model", (d_model_uri,))
        rows = database.execute("""
            SELECT p.fold_index,p.storm_id,p.rho_l2_kg_m3,p.rho_m1_kg_m3,
                   d.rho_l2_phase_kg_m3,d.rho_trial4_joint_phase_kg_m3
            FROM prediction AS p
            LEFT JOIN d_model.trial4_joint_fit_minute AS d
              ON d.storm_id=p.storm_id AND d.time_us=p.time_us
            ORDER BY p.fold_index,p.storm_id,p.time_us
        """).fetchall()
    if len(rows) != 2235 or len({row[1] for row in rows}) != 25:
        raise ValueError("Expected 2,235 aligned orbit centers in 25 storms")
    aligned = []
    for fold, storm, l2, m1, d_l2, d_density in rows:
        if (d_density is None or l2 != d_l2
                or not all(math.isfinite(value) and value > 0
                           for value in (l2, m1, d_density))):
            raise ValueError(f"D-model alignment failed: {storm}")
        aligned.append((fold, storm, l2, m1, d_density))
    return aligned


def rmse(rows: list[tuple], density_index: int) -> float:
    """Input: [(fold, storm, L2, M1, D)], density index. Output: log-density RMSE."""
    squared = [math.log(row[density_index] / row[2]) ** 2 for row in rows]
    return math.sqrt(sum(squared) / len(squared))


def score_rows(rows: list[tuple]) -> tuple[list[tuple], tuple]:
    """Input: aligned orbit rows. Output: ([five fold scores], overall score)."""
    by_fold = defaultdict(list)
    for row in rows:
        by_fold[row[0]].append(row)
    if set(by_fold) != {1, 2, 3, 4, 5}:
        raise ValueError("Expected five held-out storm folds")
    folds = []
    for fold, fold_rows in sorted(by_fold.items()):
        if len({row[1] for row in fold_rows}) != 5:
            raise ValueError(f"Fold {fold} does not contain five storms")
        folds.append((fold, 5, len(fold_rows), rmse(fold_rows, 3),
                      rmse(fold_rows, 4), VERSION))
    summary = (25, len(rows), rmse(rows, 3), rmse(rows, 4), VERSION)
    return folds, summary


def write_sqlite(folds: list[tuple], summary: tuple) -> None:
    """Input: five fold scores, overall score. Output: new derived SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(suffix=".building", dir=OUTPUT.parent)
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            database.executescript("""
                CREATE TABLE fold_metric (
                    fold_index INTEGER PRIMARY KEY,storm_count INTEGER NOT NULL,
                    orbit_count INTEGER NOT NULL,m1_log_rmse REAL NOT NULL,
                    d_model_log_rmse REAL NOT NULL,algorithm_version TEXT NOT NULL
                );
                CREATE TABLE summary (
                    storm_count INTEGER NOT NULL,orbit_count INTEGER NOT NULL,
                    m1_log_rmse REAL NOT NULL,d_model_log_rmse REAL NOT NULL,
                    algorithm_version TEXT NOT NULL
                );
            """)
            database.executemany("INSERT INTO fold_metric VALUES (?,?,?,?,?,?)", folds)
            database.execute("INSERT INTO summary VALUES (?,?,?,?,?)", summary)
            if (database.execute("SELECT count(*) FROM fold_metric").fetchone()[0] != 5
                    or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"):
                raise ValueError("D-model score SQLite failed validation")
            database.commit()
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    """Input: saved Phase 4 and Trial 10 results. Output: same-orbit D-model scores."""
    folds, summary = score_rows(load_aligned_rows())
    write_sqlite(folds, summary)
    for fold in folds:
        print(f"Fold {fold[0]}: D-model {fold[4]:.5f}, M1 {fold[3]:.5f}")
    print(f"Overall: D-model {summary[3]:.5f}, M1 {summary[2]:.5f}")


if __name__ == "__main__":
    main()
