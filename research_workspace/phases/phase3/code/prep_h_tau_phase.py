"""Prepare centered phase averages of the continuous SME response."""

import csv
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import numpy as np

from research_workspace.phases.phase3.code.calc_h_tau import (
    filtered_sme, phase_support, phase_weighted_mean,
)


SOURCE = Path("research_workspace/phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_6_final.sqlite")
OUTPUT = Path("research_workspace/phases/phase3/data/sqlite/swarm_a_phase3_h_tau_phase_v1.sqlite")
QC_REPORT = Path("research_workspace/phases/phase3/data/analysis/phase3_h_tau_phase_qc.csv")
MINUTE_US = 60_000_000
SME_REFERENCE_NT = 65.0
TAU_STEPS = 41


def load_sme(database: sqlite3.Connection) -> tuple[np.ndarray, int]:
    """Input: read-only P2.6 connection. Output: [continuous SME], first time_us."""
    first_time_us, total = database.execute(
        "SELECT min(time_us),count(*) FROM geomag_1min_v2"
    ).fetchone()
    sme = np.fromiter(
        (float(value) if valid else np.nan for value, valid in database.execute(
            "SELECT sme_nt,sme_valid FROM geomag_1min_v2 ORDER BY time_us")),
        dtype=float, count=total,
    )
    valid_end = int(np.flatnonzero(np.isfinite(sme))[-1]) + 1
    if not np.isfinite(sme[:valid_end]).all():
        raise ValueError("SME has an internal gap before the last event.")
    return sme[:valid_end], first_time_us


def load_event(database: sqlite3.Connection, storm_id: str,
               first_time_us: int) -> dict:
    """Input: read-only P2.6, storm ID, SME origin. Output: minute phase support."""
    rows = database.execute("""
        SELECT feature.source_time_us,feature.u_rel_rad,density.paired_sample_count
        FROM storm_minute_feature_v5 AS feature
        JOIN storm_density_1min_v5 AS density
          ON density.storm_id=feature.storm_id
         AND density.source_time_us=feature.source_time_us
        WHERE feature.storm_id=? ORDER BY feature.source_time_us
    """, (storm_id,)).fetchall()
    times = np.fromiter((row[0] for row in rows), dtype=np.int64)
    phase = np.fromiter((row[1] for row in rows), dtype=float)
    pairs = np.fromiter((row[2] for row in rows), dtype=np.int16)
    elapsed_us = times - first_time_us
    if np.any(elapsed_us % MINUTE_US) or np.any(np.diff(times) != MINUTE_US):
        raise ValueError(f"Event minute keys are not consecutive: {storm_id}")
    return {"storm_id": storm_id, "time_us": times, "u_rel_rad": phase,
            "pair_count": pairs, "minute_index": elapsed_us // MINUTE_US,
            "support": phase_support(phase, pairs), "columns": {}}


def insert_event(database: sqlite3.Connection, event: dict) -> None:
    """Input: Phase 3 connection and prepared event. Output: inserted keyed rows."""
    support = event["support"]
    response_names = list(event["columns"])
    field_count = 9 + len(response_names)
    statement = ("INSERT INTO phase3_h_tau_minute VALUES ("
                 + ",".join("?" for _ in range(field_count)) + ")")
    rows = (
        (event["storm_id"], int(event["time_us"][index]),
         float(event["u_rel_rad"][index]), int(event["pair_count"][index]),
         int(support["expected"][index]), int(support["paired"][index]),
         float(support["coverage"][index]), int(support["valid"][index]),
         *(float(event["columns"][name][index])
           if np.isfinite(event["columns"][name][index]) else None
           for name in response_names),
         "phase3_h_tau_phase_v1")
        for index in range(len(event["time_us"]))
    )
    database.executemany(statement, rows)


def save_results(events: list[dict]) -> None:
    """Input: [prepared event with 41 response columns]. Output: SQLite and QC CSV."""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix="h_tau_phase_3y.", suffix=".building", dir=OUTPUT.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    qc_rows = []
    try:
        with closing(sqlite3.connect(temporary)) as database:
            response_names = list(events[0]["columns"])
            response_fields = ",".join(f"{name} REAL" for name in response_names)
            database.execute(f"""
                CREATE TABLE phase3_h_tau_minute (
                    storm_id TEXT NOT NULL,
                    time_us INTEGER NOT NULL,
                    u_rel_rad REAL NOT NULL,
                    paired_sample_count INTEGER NOT NULL,
                    phase_expected_sample_count INTEGER NOT NULL,
                    phase_paired_sample_count INTEGER NOT NULL,
                    phase_paired_coverage REAL NOT NULL,
                    phase_is_valid_80pct INTEGER NOT NULL,
                    {response_fields},
                    algorithm_version TEXT NOT NULL,
                    PRIMARY KEY (storm_id,time_us)
                )
            """)
            database.execute("CREATE TABLE phase3_h_tau_metadata "
                             "(name TEXT PRIMARY KEY,value TEXT NOT NULL)")
            database.executemany("INSERT INTO phase3_h_tau_metadata VALUES (?,?)", (
                ("sme_reference_nt", "65"),
                ("tau_grid_hours", "index / 4, index=0..40"),
                ("phase_window", "u +/- pi, paired native samples, centered"),
                ("source", str(SOURCE)),
            ))
            for event in events:
                with database:
                    insert_event(database, event)
                support = event["support"]
                qc_rows.append({
                    "storm_id": event["storm_id"],
                    "minute_rows": len(event["time_us"]),
                    "valid_phase_rows": int(np.count_nonzero(support["valid"])),
                    "invalid_edge_or_coverage_rows": int(np.count_nonzero(
                        ~support["valid"])),
                    "minimum_paired_coverage": float(np.min(support["coverage"])),
                    "median_paired_coverage": float(np.median(support["coverage"])),
                })
            total_rows = database.execute(
                "SELECT count(*) FROM phase3_h_tau_minute").fetchone()[0]
            if total_rows != sum(row["minute_rows"] for row in qc_rows):
                raise ValueError("Phase 3 response output lost minute keys.")
            if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Phase 3 response SQLite integrity check failed.")
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)
    with QC_REPORT.open("x", newline="", encoding="utf-8-sig") as output:
        csv_writer = csv.DictWriter(output, fieldnames=list(qc_rows[0]))
        csv_writer.writeheader()
        csv_writer.writerows(qc_rows)


def main() -> None:
    """Input: frozen P2.6 checkpoint. Output: Phase 3 response SQLite and QC CSV."""
    if OUTPUT.exists() or QC_REPORT.exists():
        raise FileExistsError("Phase 3 H-tau output already exists.")
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        sme, first_time_us = load_sme(database)
        storm_ids = [row[0] for row in database.execute(
            "SELECT storm_id FROM storm_event_t0_phase_v5 ORDER BY t0_time_us")]
        events = [load_event(database, storm_id, first_time_us)
                  for storm_id in storm_ids]
    if len(events) != 25:
        raise ValueError(f"Expected 25 storms, found {len(events)}.")
    for tau_index in range(TAU_STEPS):
        response = filtered_sme(sme, tau_index / 4) - SME_REFERENCE_NT
        for event in events:
            raw = response[event["minute_index"]]
            event["columns"][f"h_phase_tau_{tau_index:02d}_nt"] = (
                phase_weighted_mean(raw, event["pair_count"], event["support"]))
            if tau_index in (0, 16, 40):
                event["columns"][f"h_raw_tau_{tau_index:02d}_nt"] = raw
    save_results(events)
    print(f"Saved {sum(len(event['time_us']) for event in events)} minute anchors")


if __name__ == "__main__":
    main()
