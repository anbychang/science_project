"""Save isolated Trial 2 score tables and the delay diagnostic figure."""

import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from calc_trial2_delay import DELTA_MINUTES, SPLIT_SEED


OUTPUT = Path("phases/phase3-trial2/data/sqlite/swarm_a_phase3_trial2_delay_v1.sqlite")
FIGURE = Path("phases/phase3-trial2/figures/delta_diagnostic.png")
VERSION = "phase3_trial2_delay_v1"


def write_tables(database: sqlite3.Connection, trial: dict) -> None:
    """Input: new SQLite and trial arrays. Output: keyed trial tables."""
    database.executescript("""
        CREATE TABLE trial2_metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE trial2_split (
            fold INTEGER NOT NULL, storm_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('train','test')),
            PRIMARY KEY(fold,storm_id)
        );
        CREATE TABLE trial2_fold (
            fold INTEGER PRIMARY KEY, m1_tau_hours REAL NOT NULL,
            m1_gain_per_nt REAL NOT NULL, delta_minutes INTEGER NOT NULL,
            train_rmse_m1 REAL NOT NULL, train_rmse_delay REAL NOT NULL,
            joint_tau_hours REAL, joint_delta_minutes INTEGER,
            joint_gain_per_nt REAL, train_rmse_joint REAL
        );
        CREATE TABLE trial2_test_score (
            fold INTEGER NOT NULL, storm_id TEXT NOT NULL,
            rmse_m1 REAL NOT NULL, rmse_delay REAL NOT NULL,
            rmse_joint REAL, PRIMARY KEY(fold,storm_id)
        );
        CREATE TABLE trial2_event_summary (
            storm_id TEXT PRIMARY KEY, valid_anchor_count INTEGER NOT NULL,
            r_quiet REAL NOT NULL, mean_rmse_m1 REAL NOT NULL,
            mean_rmse_delay REAL NOT NULL, mean_rmse_joint REAL,
            descriptive_best_delta_minutes INTEGER NOT NULL
        );
        CREATE TABLE trial2_full_delta_grid (
            delta_minutes INTEGER PRIMARY KEY, pooled_rmse_log_density REAL NOT NULL
        );
        CREATE TABLE trial2_event_delta_grid (
            storm_id TEXT NOT NULL, delta_minutes INTEGER NOT NULL,
            rmse_log_density REAL NOT NULL,
            PRIMARY KEY(storm_id,delta_minutes)
        );
        CREATE TABLE trial2_joint_grid (
            tau_hours REAL NOT NULL, delta_minutes INTEGER NOT NULL,
            gain_per_nt REAL NOT NULL, pooled_rmse_log_density REAL NOT NULL,
            PRIMARY KEY(tau_hours,delta_minutes)
        );
    """)
    events = trial["events"]
    first = trial["first"]
    joint = trial["joint"]
    metadata = {
        "algorithm_version": VERSION,
        "split_seed": str(SPLIT_SEED),
        "split_design": "20 random rounds; five disjoint groups of five per round",
        "event_count": str(len(events)),
        "test_appearances_per_event": "20",
        "delta_grid_minutes": ",".join(map(str, DELTA_MINUTES)),
        "m1_reproduction_max_abs_h_nt": str(trial["reproduction_max_nt"]),
        "first_stage_equal_event_improvement": str(first["improvement"]),
        "first_stage_gate": "passed" if joint is not None else "failed",
        "second_stage_executed": str(joint is not None),
        "analysis": "offline centered phase, event-specific pre-storm R",
    }
    if joint is not None:
        metadata["second_stage_equal_event_improvement"] = str(joint["improvement"])
    database.executemany("INSERT INTO trial2_metadata VALUES (?,?)", metadata.items())
    database.executemany("INSERT INTO trial2_split VALUES (?,?,?)", (
        (fold_id, events[int(index)]["storm_id"], role)
        for fold_id, train, test in trial["splits"]
        for role, indexes in (("train", train), ("test", test))
        for index in indexes
    ))
    joint_by_fold = {} if joint is None else {row["fold"]: row for row in joint["folds"]}
    database.executemany("INSERT INTO trial2_fold VALUES (?,?,?,?,?,?,?,?,?,?)", (
        (row["fold"], row["tau_hours"], row["gain_per_nt"],
         row["delta_minutes"], row["train_rmse_m1"], row["train_rmse_delay"],
         joint_by_fold[row["fold"]]["tau_hours"] if joint is not None else None,
         joint_by_fold[row["fold"]]["delta_minutes"] if joint is not None else None,
         joint_by_fold[row["fold"]]["gain_per_nt"] if joint is not None else None,
         joint_by_fold[row["fold"]]["train_rmse_joint"] if joint is not None else None)
        for row in first["folds"]
    ))
    joint_score = {} if joint is None else {
        (row["fold"], row["event_index"]): row["rmse_joint"]
        for row in joint["scores"]
    }
    database.executemany("INSERT INTO trial2_test_score VALUES (?,?,?,?,?)", (
        (row["fold"], events[row["event_index"]]["storm_id"],
         row["rmse_m1"], row["rmse_delay"],
         joint_score.get((row["fold"], row["event_index"])))
        for row in first["scores"]
    ))
    database.executemany("INSERT INTO trial2_event_summary VALUES (?,?,?,?,?,?,?)", (
        (event["storm_id"], event["count"], event["r"],
         float(first["m1_mean"][index]), float(first["delay_mean"][index]),
         float(joint["joint_mean"][index]) if joint is not None else None,
         int(trial["full_delay"]["best_delay_by_event"][index]))
        for index, event in enumerate(events)
    ))
    database.executemany("INSERT INTO trial2_full_delta_grid VALUES (?,?)", (
        (delay, float(rmse))
        for delay, rmse in zip(DELTA_MINUTES, trial["full_delay"]["rmse"], strict=True)
    ))
    database.executemany("INSERT INTO trial2_event_delta_grid VALUES (?,?,?)", (
        (event["storm_id"], delay,
         float(trial["full_delay"]["event_rmse"][delay_index, event_index]))
        for event_index, event in enumerate(events)
        for delay_index, delay in enumerate(DELTA_MINUTES)
    ))
    if joint is not None:
        database.executemany("INSERT INTO trial2_joint_grid VALUES (?,?,?,?)", (
            (tau, delta, float(gain), float(rmse))
            for (tau, delta), gain, rmse in zip(
                joint["candidates"], joint["full_gain"], joint["full_rmse"], strict=True
            )
        ))
    for table in (
        "trial2_split", "trial2_fold", "trial2_test_score",
        "trial2_event_summary", "trial2_full_delta_grid",
        "trial2_event_delta_grid", "trial2_joint_grid",
    ):
        database.execute(
            f"ALTER TABLE {table} ADD COLUMN algorithm_version "
            f"TEXT NOT NULL DEFAULT '{VERSION}'"
        )


def save_sqlite(trial: dict) -> Path:
    """Input: trial arrays. Output: new independent SQLite path."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="trial2_delay_", suffix=".building", dir=OUTPUT.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            write_tables(database, trial)
            database.commit()
            counts = {
                name: database.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
                for name in ("trial2_split", "trial2_fold", "trial2_test_score",
                             "trial2_event_summary", "trial2_full_delta_grid")
            }
            if counts != {
                "trial2_split": 2500, "trial2_fold": 100,
                "trial2_test_score": 500, "trial2_event_summary": 25,
                "trial2_full_delta_grid": 25,
            }:
                raise ValueError(f"Trial 2 row counts changed: {counts}")
            if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Trial 2 SQLite integrity check failed")
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)
    return OUTPUT


def draw_figure(trial: dict) -> Path:
    """Input: trial arrays. Output: fixed-M1 delay diagnostic PNG."""
    FIGURE.parent.mkdir(parents=True, exist_ok=True)
    events = trial["events"]
    full = trial["full_delay"]
    figure, axes = plt.subplots(2, 1, figsize=(11, 8), constrained_layout=True)
    hours = [minute / 60 for minute in DELTA_MINUTES]
    axes[0].plot(hours, full["rmse"], marker="o", markersize=3)
    axes[0].set(xlabel="Effective delay (hours)",
                ylabel="Pooled RMSE (log density)",
                title="Full-data diagnostic with M1 tau and gain fixed")
    axes[0].grid(alpha=0.25)
    axes[1].bar(range(len(events)), full["best_delay_by_event"] / 60)
    axes[1].set(xticks=range(len(events)),
                xticklabels=[event["storm_id"][1:9] for event in events],
                ylabel="Best delay (hours)",
                title="Descriptive per-event minima; not held-out estimates")
    axes[1].tick_params(axis="x", labelrotation=70)
    axes[1].grid(axis="y", alpha=0.25)
    figure.savefig(FIGURE, dpi=180)
    plt.close(figure)
    return FIGURE
