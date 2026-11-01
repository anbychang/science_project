"""Read the frozen Phase 2/3 inputs for the independent Phase 4 v2 fit."""

import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np

from phases.phase3.code.prep_h_tau_phase import load_event, load_sme


PREDICTIONS = Path("phases/phase3/data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite")
PHASE2 = Path("phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_6_final.sqlite")
SME_REFERENCE_NT = 65.0


def load_density_rows() -> dict[str, dict]:
    """Input: frozen Phase 3 SQLite. Output: {storm_id: density and time arrays}."""
    uri = f"file:{PREDICTIONS.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        rows = database.execute("""
            SELECT p.storm_id,p.time_us,p.rho_l2_phase_kg_m3,
                   p.rho_msis_quiet_phase_kg_m3,o.r_candidate
            FROM phase3_prediction_minute AS p
            JOIN phase3_25storm_overview AS o ON o.storm_id=p.storm_id
            ORDER BY o.t0_time_us,p.time_us
        """).fetchall()
    grouped = {}
    for storm_id, time_us, rho_l2, rho_quiet, r_candidate in rows:
        event = grouped.setdefault(storm_id, {"time_us": [], "rho_l2": [],
                                              "rho_quiet": [], "r_candidate": r_candidate})
        event["time_us"].append(time_us)
        event["rho_l2"].append(rho_l2)
        event["rho_quiet"].append(rho_quiet)
    if len(grouped) != 25 or len(rows) != 214_907:
        raise ValueError("Phase 3 source must contain 25 storms and 214907 minutes.")
    for storm_id, event in grouped.items():
        for name, dtype in (("time_us", np.int64), ("rho_l2", float), ("rho_quiet", float)):
            event[name] = np.asarray(event[name], dtype=dtype)
        if (event["r_candidate"] <= 0 or not np.isfinite(event["rho_l2"]).all()
                or not np.isfinite(event["rho_quiet"]).all()
                or np.any(event["rho_l2"] <= 0) or np.any(event["rho_quiet"] <= 0)):
            raise ValueError(f"Invalid density input: {storm_id}")
        event["log_anomaly"] = np.log(event["rho_l2"] / event["rho_quiet"])
    return grouped


def load_phase_events(storm_ids: list[str]) -> tuple[np.ndarray, list[dict]]:
    """Input: [storm_id]. Output: [SME nT], [event with phase support and time_us]."""
    uri = f"file:{PHASE2.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        sme, first_time_us = load_sme(database)
        events = [load_event(database, storm_id, first_time_us) for storm_id in storm_ids]
    return sme, events
