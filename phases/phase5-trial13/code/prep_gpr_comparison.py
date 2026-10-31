"""Audit three saved M1-only GP trials on identical held-out storm orbits."""

import math
import os
import sqlite3
import tempfile
from contextlib import closing
from itertools import groupby
from pathlib import Path

from calc_gpr_comparison import bootstrap_delta, event_sums, rmse


ROOT = Path("phases/phase5-trial13")
OUTPUT = ROOT / "data/sqlite/swarm_a_phase5_m1_gpr_comparison_v1.sqlite"
SOURCES = {
    "Trial10": Path("phases/phase5-trial10/data/sqlite/swarm_a_phase5_m1_shape_gpr_v1.sqlite"),
    "Trial11": Path("phases/phase5-trial11/data/sqlite/swarm_a_phase5_temporal_shape_gpr_v1.sqlite"),
    "Trial12": Path("phases/phase5-trial12/data/sqlite/swarm_a_phase5_peak_context_gpr_v1.sqlite"),
}


def load_predictions(model_name: str, path: Path) -> list[tuple]:
    """Input: saved trial name and SQLite path. Output: sorted held-out orbit rows."""
    density_column = "rho_gpr_kg_m3" if model_name == "Trial10" else "rho_gp_kg_m3"
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        rows = database.execute(f"""
            SELECT storm_id,time_us,grid_index,fold_index,
                   rho_m1_kg_m3,rho_l2_kg_m3,{density_column}
            FROM prediction ORDER BY storm_id,time_us
        """).fetchall()
    if len(rows) != 2235 or len({row[0] for row in rows}) != 25:
        raise ValueError(f"{model_name} must contain 2,235 orbits in 25 storms.")
    return rows


def check_alignment(predictions: dict[str, list[tuple]]) -> None:
    """Input: {trial: held-out orbit rows}. Output: rejects mismatched targets or folds."""
    reference = predictions["Trial10"]
    for model_name, rows in predictions.items():
        for original, compared in zip(reference, rows, strict=True):
            if original[:4] != compared[:4] or any(
                not math.isclose(original[index], compared[index], rel_tol=1e-12)
                for index in (4, 5)
            ):
                raise ValueError(f"{model_name} differs in orbit, fold, M1 or L2.")


def build_audit() -> dict:
    """Input: three saved, read-only trial SQLite files. Output: matched storm and summary metrics."""
    predictions = {name: load_predictions(name, path) for name, path in SOURCES.items()}
    check_alignment(predictions)
    events = {name: {} for name in ("M1", *SOURCES)}
    storm_folds = {}
    for model_name, rows in predictions.items():
        for storm_id, group in groupby(rows, key=lambda row: row[0]):
            storm_rows = list(group)
            fold = storm_rows[0][3]
            if any(row[3] != fold for row in storm_rows):
                raise ValueError("A storm appears in multiple test folds.")
            storm_folds[storm_id] = fold
            gp_samples = [(row[2], row[5], row[6]) for row in storm_rows]
            events[model_name][storm_id] = event_sums(gp_samples)
            if model_name == "Trial10":
                m1_samples = [(row[2], row[5], row[4]) for row in storm_rows]
                events["M1"][storm_id] = event_sums(m1_samples)
    if sorted({fold for fold in storm_folds.values()}) != [1, 2, 3, 4, 5]:
        raise ValueError("Expected five held-out storm folds.")
    event_rows = []
    fold_rows = []
    summary_rows = []
    for model_name, storm_events in events.items():
        ordered_storms = sorted(storm_events)
        ordered = [storm_events[storm] for storm in ordered_storms]
        for storm_id, event in zip(ordered_storms, ordered, strict=True):
            event_rows.append((model_name, storm_id, storm_folds[storm_id],
                               event["count"], event["total_sse"], event["shape_sse"],
                               event["change_sse"], event["change_count"],
                               rmse([event], "total"), rmse([event], "shape"),
                               rmse([event], "change")))
        for fold in range(1, 6):
            fold_events = [storm_events[storm] for storm in ordered_storms
                           if storm_folds[storm] == fold]
            fold_rows.append((model_name, fold, len(fold_events),
                              sum(event["count"] for event in fold_events),
                              rmse(fold_events, "total"), rmse(fold_events, "shape"),
                              rmse(fold_events, "change")))
        improved_events = 0
        improved_folds = 0
        ci_low = None
        ci_high = None
        if model_name != "M1":
            baseline = events["M1"]
            pairs = [(baseline[storm], storm_events[storm]) for storm in ordered_storms]
            improved_events = sum(rmse([gp], "shape") < rmse([m1], "shape")
                                  for m1, gp in pairs)
            improved_folds = sum(
                rmse([storm_events[storm] for storm in ordered_storms
                      if storm_folds[storm] == fold], "shape")
                < rmse([baseline[storm] for storm in ordered_storms
                        if storm_folds[storm] == fold], "shape")
                for fold in range(1, 6)
            )
            ci_low, ci_high = bootstrap_delta(pairs, "shape")
        summary_rows.append((model_name, sum(event["count"] for event in ordered),
                             len(ordered), rmse(ordered, "total"),
                             rmse(ordered, "shape"), rmse(ordered, "change"),
                             improved_events, improved_folds, ci_low, ci_high))
    return {"event": event_rows, "fold": fold_rows, "summary": summary_rows}


def write_sqlite(result: dict) -> None:
    """Input: matched Trial 10–12 comparison. Output: separate atomic audit SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(suffix=".building", dir=OUTPUT.parent)
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            database.executescript("""
                CREATE TABLE event_metric (
                    model_name TEXT NOT NULL,storm_id TEXT NOT NULL,
                    fold_index INTEGER NOT NULL,orbit_count INTEGER NOT NULL,
                    total_sse REAL NOT NULL,shape_sse REAL NOT NULL,
                    change_sse REAL NOT NULL,change_count INTEGER NOT NULL,
                    total_rmse REAL NOT NULL,shape_rmse REAL NOT NULL,
                    change_rmse REAL NOT NULL,PRIMARY KEY(model_name,storm_id)
                );
                CREATE TABLE fold_metric (
                    model_name TEXT NOT NULL,fold_index INTEGER NOT NULL,
                    storm_count INTEGER NOT NULL,orbit_count INTEGER NOT NULL,
                    total_rmse REAL NOT NULL,shape_rmse REAL NOT NULL,
                    change_rmse REAL NOT NULL,PRIMARY KEY(model_name,fold_index)
                );
                CREATE TABLE summary (
                    model_name TEXT PRIMARY KEY,orbit_count INTEGER NOT NULL,
                    storm_count INTEGER NOT NULL,total_rmse REAL NOT NULL,
                    shape_rmse REAL NOT NULL,change_rmse REAL NOT NULL,
                    improved_shape_storms INTEGER NOT NULL,
                    improved_shape_folds INTEGER NOT NULL,
                    shape_delta_ci_low REAL,shape_delta_ci_high REAL
                );
                CREATE TABLE source (model_name TEXT PRIMARY KEY,sqlite_path TEXT NOT NULL);
            """)
            database.executemany("INSERT INTO event_metric VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                 result["event"])
            database.executemany("INSERT INTO fold_metric VALUES (?,?,?,?,?,?,?)",
                                 result["fold"])
            database.executemany("INSERT INTO summary VALUES (?,?,?,?,?,?,?,?,?,?)",
                                 result["summary"])
            database.executemany("INSERT INTO source VALUES (?,?)",
                                 [(name, str(path)) for name, path in SOURCES.items()])
            if (database.execute("SELECT count(*) FROM event_metric").fetchone()[0] != 100
                    or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"):
                raise ValueError("Trial 13 comparison SQLite audit failed.")
            database.commit()
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    """Input: saved Trial 10–12 SQLite files. Output: independent comparison SQLite."""
    result = build_audit()
    write_sqlite(result)
    for row in result["summary"]:
        print(f"{row[0]}: total {row[3]:.6f}, shape {row[4]:.6f}, "
              f"change {row[5]:.6f}, improved storms {row[6]}/25")


if __name__ == "__main__":
    main()
