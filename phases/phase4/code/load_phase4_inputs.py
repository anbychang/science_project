"""Load frozen Phase 2 and Phase 3 inputs for Phase 4 anchors."""

import math
import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np

from phases.phase3.code.calc_h_tau import filtered_sme, phase_support, phase_weighted_mean
from phases.phase3.code.prep_h_tau_phase import SOURCE, load_event, load_sme


PHASE3_RESULTS = Path("phases/phase3/data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite")
PHASE3_QUIET = Path("phases/phase3/data/sqlite/swarm_a_phase3_quiet_density_v1.sqlite")
FEATURE_NAMES = ("h_tau_phase_nt", "h_24h_phase_nt", "sme_phase_nt", "symh_phase_nt")
SME_REFERENCE_NT = 65.0
GRID_TOLERANCE_RAD = 0.02 * math.pi


def load_r_values() -> dict[str, float]:
    """Input: frozen Phase 3 overview SQLite. Output: {storm_id: positive R}."""
    uri = f"file:{PHASE3_RESULTS.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        rows = database.execute(
            "SELECT storm_id,r_candidate FROM phase3_25storm_overview").fetchall()
    result = dict(rows)
    if len(rows) != 25 or len(result) != 25 or any(value <= 0 for value in result.values()):
        raise ValueError("Phase 3 overview requires 25 positive quiet multipliers.")
    return result


def nearest_phase_anchors(u_rad: np.ndarray, valid: np.ndarray,
                          window_cycles: int = 1) -> np.ndarray:
    """Input: [phase radians], [valid flags], cycle width. Output: grid indices."""
    spacing_rad = 2 * math.pi * window_cycles
    selected = {}
    for index in np.flatnonzero(valid):
        grid_index = round(float(u_rad[index]) / spacing_rad)
        distance = abs(float(u_rad[index]) - spacing_rad * grid_index)
        if distance > GRID_TOLERANCE_RAD:
            continue
        previous = selected.get(grid_index)
        if previous is None or distance < previous[0]:
            selected[grid_index] = (distance, int(index))
    return np.array([selected[key][1] for key in sorted(selected)], dtype=np.int64)


def attach_density(events: list[dict], window_cycles: int) -> None:
    """Input: [events], cycle width. Output: attaches window-mean densities."""
    uri = f"file:{PHASE3_QUIET.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        for event in events:
            rows = database.execute("""
                SELECT time_us,paired_sample_count,rho_l2_kg_m3,
                       rho_msis_quiet_kg_m3,rho_l2_phase_kg_m3,
                       phase_is_valid_80pct
                FROM phase3_quiet_density_minute
                WHERE storm_id=? ORDER BY time_us
            """, (event["storm_id"],)).fetchall()
            times = np.fromiter((row[0] for row in rows), dtype=np.int64)
            pairs = np.fromiter((row[1] for row in rows), dtype=np.int16)
            original_valid = np.fromiter((row[5] for row in rows), dtype=bool)
            if not np.array_equal(times, event["time_us"]) or not np.array_equal(
                pairs, event["pair_count"]
            ) or not np.array_equal(original_valid, event["support"]["valid"]):
                raise ValueError(f"Phase 3 density keys or support differ: {event['storm_id']}.")
            event["rho_l2_one_cycle"] = np.array([
                row[4] if row[4] is not None else np.nan for row in rows])
            event["support"] = phase_support(event["u_rel_rad"] / window_cycles, pairs)
            valid = event["support"]["valid"]
            anchors = nearest_phase_anchors(event["u_rel_rad"], valid, window_cycles)
            event["anchors"] = anchors
            rho_l2_minute = np.array([
                row[2] if row[2] is not None else np.nan for row in rows])
            rho_quiet_minute = np.array([
                row[3] if row[3] is not None else np.nan for row in rows])
            event["rho_l2"] = phase_weighted_mean(
                rho_l2_minute, pairs, event["support"])[anchors]
            event["rho_quiet"] = phase_weighted_mean(
                rho_quiet_minute, pairs, event["support"])[anchors]
            if not len(anchors) or not np.isfinite(event["rho_l2"]).all() or not np.isfinite(
                event["rho_quiet"]
            ).all() or np.any(event["rho_l2"] <= 0) or np.any(event["rho_quiet"] <= 0):
                raise ValueError(f"Missing positive anchor densities: {event['storm_id']}.")


def attach_symh(database: sqlite3.Connection, events: list[dict]) -> None:
    """Input: read-only P2.6 connection, [events]. Output: attaches phase SYM-H."""
    for event in events:
        rows = database.execute("""
            SELECT source_time_us,symh_nt FROM storm_minute_feature_v5
            WHERE storm_id=? ORDER BY source_time_us
        """, (event["storm_id"],)).fetchall()
        times = np.fromiter((row[0] for row in rows), dtype=np.int64)
        if not np.array_equal(times, event["time_us"]):
            raise ValueError(f"SYM-H keys differ for {event['storm_id']}.")
        symh = np.array([row[1] if row[1] is not None else np.nan for row in rows])
        event["symh_phase"] = phase_weighted_mean(
            symh, event["pair_count"], event["support"])[event["anchors"]]


def phase_response(events: list[dict], sme: np.ndarray,
                   tau_hours: float) -> list[np.ndarray]:
    """Input: [events], continuous SME nT, tau h. Output: [anchor phase response]."""
    response = filtered_sme(sme, tau_hours) - SME_REFERENCE_NT
    averages = []
    for event in events:
        phase = phase_weighted_mean(
            response[event["minute_index"]], event["pair_count"], event["support"])
        averages.append(phase[event["anchors"]])
    return averages


def load_inputs(window_cycles: int = 1) -> tuple[list[dict], np.ndarray]:
    """Input: cycle width and frozen P2/P3. Output: [event anchors], SME nT."""
    if window_cycles not in (1, 2):
        raise ValueError("Supported phase windows are one or two cycles.")
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        sme, origin = load_sme(database)
        storm_ids = [row[0] for row in database.execute(
            "SELECT storm_id FROM storm_event_t0_phase_v5 ORDER BY t0_time_us")]
        events = [load_event(database, storm_id, origin) for storm_id in storm_ids]
        attach_density(events, window_cycles)
        attach_symh(database, events)
    expected_minimum = 2000 if window_cycles == 1 else 1000
    if len(events) != 25 or sum(len(event["anchors"]) for event in events) < expected_minimum:
        raise ValueError("Storm count or phase anchor count differs from the audited input.")
    uri = f"file:{PHASE3_RESULTS.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        t0_by_storm = dict(database.execute(
            "SELECT storm_id,t0_time_us FROM phase3_25storm_overview"))
    for event in events:
        event["t0_time_us"] = t0_by_storm[event["storm_id"]]
    for event, average in zip(events, phase_response(events, sme, 0)):
        event["sme_phase"] = average + SME_REFERENCE_NT
    for event, average in zip(events, phase_response(events, sme, 24)):
        event["h_24h_phase"] = average
    for event in events:
        if not np.isfinite(event["symh_phase"]).all():
            raise ValueError(f"Missing anchor SYM-H: {event['storm_id']}.")
    return events, sme
