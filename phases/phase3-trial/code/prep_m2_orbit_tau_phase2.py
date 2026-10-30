"""Fit a shared SME-to-tau rule on Phase 2 event-specific orbit segments."""

import math
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import numpy as np

from load_m2_orbit_inputs import (
    TAU_CANDIDATES_HOURS, read_event_support, read_minute_sme,
)
from phases.phase3.code.calc_h_tau import filtered_sme, phase_weighted_mean
from calc_m2_orbit_tau import event_orbit_response, tau_from_previous_sme


OUTPUT = Path("phases/phase3-trial/data/sqlite/swarm_a_m2_orbit_tau_phase2_v1.sqlite")
VERSION = "m2_orbit_tau_phase2_v1"
TWO_PI = 2 * math.pi


def prepare_events(minute_times: np.ndarray, sme_nt: np.ndarray,
                   events: list[dict], initial_tau_hours: float = 3.5) -> list[dict]:
    """Input: [minute epochs], [SME nT], [events], initial tau h. Output: orbit events."""
    constant_response = filtered_sme(sme_nt - 65.0, initial_tau_hours)
    for event in events:
        orbit_labels = np.floor(event["u_rel_rad"] / TWO_PI).astype(np.int32)
        increments = np.diff(orbit_labels)
        if not np.all((increments == 0) | (increments == 1)):
            raise ValueError(f"Phase 2 orbit labels are not contiguous: {event['storm_id']}")
        edges = np.r_[0, np.flatnonzero(increments == 1) + 1, len(orbit_labels)]
        first_index = int(event["minute_index"][0])
        if first_index == 0:
            raise ValueError("No continuous SME state before the first event minute")
        event_sme = sme_nt[event["minute_index"]]
        previous_sme = np.empty(len(edges) - 1)
        previous_sme[0] = 65.0
        for orbit in range(1, len(previous_sme)):
            previous_sme[orbit] = float(np.mean(
                event_sme[edges[orbit - 1]:edges[orbit]]
            ))
        event.update({
            "orbit_labels": orbit_labels,
            "orbit_edges": edges,
            "previous_sme": previous_sme,
            "sme_excess": event_sme - 65.0,
            "initial_h": float(constant_response[first_index - 1]),
            "initial_tau_hours": initial_tau_hours,
        })
    return events


def score_rule(events: list[dict], tau_quiet: float,
               tau_active: float) -> tuple[float, float, list]:
    """Input: [event data], quiet/active tau h. Output: gain, RMSE, [event H]."""
    cross = 0.0
    response_squared = 0.0
    anomaly_squared = 0.0
    minute_count = 0
    event_responses = []
    for event in events:
        orbit_tau = tau_from_previous_sme(
            event["previous_sme"], tau_quiet, tau_active
        )
        response = event_orbit_response(
            event["sme_excess"], event["orbit_edges"], orbit_tau,
            event["initial_h"],
        )
        phase_response = phase_weighted_mean(
            response, event["pairs"], event["support"]
        )[event["support"]["valid"]]
        anomaly = event["anomaly"]
        cross += float(phase_response @ anomaly)
        response_squared += float(phase_response @ phase_response)
        anomaly_squared += float(anomaly @ anomaly)
        minute_count += len(anomaly)
        event_responses.append(phase_response)
    gain = cross / response_squared
    rmse = math.sqrt(max(anomaly_squared - cross * cross / response_squared, 0)
                     / minute_count)
    return gain, rmse, event_responses


def fit_rule_grid(events: list[dict]) -> tuple[list, tuple, list, float]:
    """Input: [Phase 2 orbit events]. Output: 49 scores, best, H, baseline check."""
    grid = []
    best = None
    best_responses = None
    baseline_difference = None
    for tau_quiet in TAU_CANDIDATES_HOURS:
        for tau_active in TAU_CANDIDATES_HOURS:
            gain, rmse, responses = score_rule(events, tau_quiet, tau_active)
            if tau_quiet == tau_active == 3.5:
                baseline_difference = max(
                    float(np.max(np.abs(response - event["old_response"])))
                    for response, event in zip(responses, events, strict=True)
                )
                if baseline_difference > 1e-6:
                    raise ValueError(f"Fixed-tau response mismatch: {baseline_difference}")
            row = (tau_quiet, tau_active, gain, rmse)
            grid.append(row)
            if best is None or rmse < best[3]:
                best = row
                best_responses = responses
    return grid, best, best_responses, baseline_difference


def write_trial(database: sqlite3.Connection, events: list[dict],
                results: tuple) -> None:
    """Input: new SQLite, [event data], fitted rule. Output: derived trial tables."""
    grid, best, responses, baseline_difference = results
    tau_quiet, tau_active, gain, _ = best
    database.executescript("""
        CREATE TABLE m2_phase2_tau_rule_grid (
            tau_quiet_hours REAL NOT NULL,
            tau_active_hours REAL NOT NULL,
            gain_per_nt REAL NOT NULL,
            rmse_log_density REAL NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (tau_quiet_hours,tau_active_hours)
        );
        CREATE TABLE m2_phase2_tau_orbit (
            storm_id TEXT NOT NULL,
            orbit_index INTEGER NOT NULL,
            first_minute_time_us INTEGER NOT NULL,
            last_minute_time_us INTEGER NOT NULL,
            previous_orbit_sme_mean_nt REAL NOT NULL,
            tau_hours REAL NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id,orbit_index)
        );
        CREATE TABLE m2_phase2_tau_minute (
            storm_id TEXT NOT NULL,
            time_us INTEGER NOT NULL,
            orbit_index INTEGER NOT NULL,
            tau_at_anchor_hours REAL NOT NULL,
            h_phase_nt REAL NOT NULL,
            rho_l2_phase_kg_m3 REAL NOT NULL,
            rho_m0_phase_kg_m3 REAL NOT NULL,
            rho_m2_phase_kg_m3 REAL NOT NULL,
            algorithm_version TEXT NOT NULL,
            PRIMARY KEY (storm_id,time_us)
        );
        CREATE TABLE m2_phase2_tau_event (
            storm_id TEXT PRIMARY KEY,
            valid_minutes INTEGER NOT NULL,
            fixed_r REAL NOT NULL,
            rmse_log_density REAL NOT NULL,
            algorithm_version TEXT NOT NULL
        );
        CREATE TABLE m2_phase2_tau_metadata (
            algorithm_version TEXT PRIMARY KEY,
            constant_response_max_abs_difference_nt REAL NOT NULL
        );
    """)
    database.executemany("INSERT INTO m2_phase2_tau_rule_grid VALUES (?,?,?,?,?)",
                         ((quiet, active, trial_gain, rmse, VERSION)
                          for quiet, active, trial_gain, rmse in grid))
    database.execute("INSERT INTO m2_phase2_tau_metadata VALUES (?,?)",
                     (VERSION, baseline_difference))
    for event, phase_response in zip(events, responses, strict=True):
        orbit_tau = tau_from_previous_sme(
            event["previous_sme"], tau_quiet, tau_active
        )
        edges = event["orbit_edges"]
        labels = event["orbit_labels"]
        database.executemany("INSERT INTO m2_phase2_tau_orbit VALUES (?,?,?,?,?,?,?)",
                             ((event["storm_id"], int(labels[edges[index]]),
                               int(event["times"][edges[index]]),
                               int(event["times"][edges[index + 1] - 1]),
                               float(event["previous_sme"][index]),
                               float(orbit_tau[index]), VERSION)
                              for index in range(len(orbit_tau))))
        valid = event["support"]["valid"]
        predicted = event["r"] * event["rho_m0"] * np.exp(gain * phase_response)
        residual = event["anomaly"] - gain * phase_response
        database.executemany("INSERT INTO m2_phase2_tau_minute VALUES (?,?,?,?,?,?,?,?,?)",
                             ((event["storm_id"], int(time), int(label),
                               float(orbit_tau[int(label - labels[0])]),
                               float(h_value), float(l2), float(m0), float(m2), VERSION)
                              for time, label, h_value, l2, m0, m2 in zip(
                                  event["times"][valid], labels[valid], phase_response,
                                  event["rho_l2"], event["rho_m0"], predicted,
                                  strict=True)))
        database.execute("INSERT INTO m2_phase2_tau_event VALUES (?,?,?,?,?)",
                         (event["storm_id"], len(residual), event["r"],
                          float(np.sqrt(np.mean(residual * residual))), VERSION))


def main() -> None:
    """Input: read-only Phase 2 SME/u and M2 residuals. Output: new trial SQLite."""
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    minute_times, sme_nt = read_minute_sme()
    events = prepare_events(minute_times, sme_nt,
                            read_event_support(minute_times))
    results = fit_rule_grid(events)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix="m2_phase2_tau_", suffix=".building", dir=OUTPUT.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            write_trial(database, events, results)
            database.commit()
            if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Phase 2 orbit tau SQLite integrity check failed")
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)
    best = results[1]
    print(f"Events={len(events)}, orbit_segments={sum(len(e['previous_sme']) for e in events)}, "
          f"tau_quiet={best[0]:g} h, tau_active={best[1]:g} h, "
          f"G={best[2]:.8g} 1/nT, RMSE={best[3]:.6f}")


if __name__ == "__main__":
    main()
