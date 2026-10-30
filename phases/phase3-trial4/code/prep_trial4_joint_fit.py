"""Run the Trial4 event-offset and event-tau descriptive fit."""

import csv
import math
import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np

from calc_h_tau import filtered_sme, phase_weighted_mean
from prep_h_tau_phase import SOURCE, load_event, load_sme
from calc_trial4_joint_fit import (
    BASELINE_TAU_INDEX,
    BASELINE_TAU_HOURS,
    MAX_R_VALUE,
    EventFitData,
    FitResult,
    FitState,
    fit_variable_tau,
    initial_state,
    model_score,
    select_tau_indices,
    tau_grid_hours,
    update_gain_at_fixed_r,
    update_offsets_and_gain,
)


PREDICTIONS = Path(
    "phases/phase3-trial4/data/sqlite/"
    "swarm_a_phase3_prediction_tau465_exploratory.sqlite"
)
GAIN_GRID = Path(
    "phases/phase3-trial4/data/analysis/phase3_tau_grid_005h_exploratory.csv"
)
MODEL_REPORT = Path("phases/phase3-trial4/data/analysis/trial4_joint_fit_tau15_models.csv")
EVENT_REPORT = Path("phases/phase3-trial4/data/analysis/trial4_joint_fit_tau15_events.csv")
ITERATION_REPORT = Path("phases/phase3-trial4/data/analysis/trial4_joint_fit_tau15_iterations.csv")
SME_REFERENCE_NT = 65.0


def load_initial_gain() -> float:
    """Input: frozen Phase 3 tau-grid CSV. Output: positive G at 4.65 h."""
    with GAIN_GRID.open(encoding="utf-8-sig", newline="") as source:
        matches = [float(row["gain_per_nt"]) for row in csv.DictReader(source)
                   if math.isclose(float(row["tau_hours"]), BASELINE_TAU_HOURS)]
    if len(matches) != 1 or matches[0] <= 0:
        raise ValueError("Expected one positive Phase 3 gain at tau=4.65 h.")
    return matches[0]


def load_density_rows() -> dict[str, dict]:
    """Input: frozen Phase 3 prediction SQLite. Output: {storm_id: density arrays}."""
    uri = f"file:{PREDICTIONS.resolve().as_posix()}?mode=ro"
    grouped: dict[str, list[tuple]] = {}
    with closing(sqlite3.connect(uri, uri=True)) as database:
        rows = database.execute("""
            SELECT prediction.storm_id,prediction.time_us,
                   prediction.rho_l2_phase_kg_m3,
                   prediction.rho_msis_quiet_phase_kg_m3,
                   prediction.rho_msis_full_phase_kg_m3,
                   prediction.h_phase_nt,overview.r_candidate
            FROM phase3_prediction_minute AS prediction
            JOIN phase3_25storm_overview AS overview
              ON overview.storm_id=prediction.storm_id
            ORDER BY overview.t0_time_us,prediction.time_us
        """).fetchall()
    for row in rows:
        grouped.setdefault(row[0], []).append(row[1:])
    if len(grouped) != 25 or not rows:
        raise ValueError("Phase 3 prediction SQLite must contain 25 nonempty storms.")
    result = {}
    for storm_id, storm_rows in grouped.items():
        time_us = np.array([row[0] for row in storm_rows], dtype=np.int64)
        l2_density = np.array([row[1] for row in storm_rows], dtype=float)
        quiet_density = np.array([row[2] for row in storm_rows], dtype=float)
        full_density = np.array([row[3] for row in storm_rows], dtype=float)
        baseline_response = np.array([row[4] for row in storm_rows], dtype=float)
        r_rq = float(storm_rows[0][5])
        if (not np.isfinite(l2_density).all() or not np.isfinite(quiet_density).all()
                or not np.isfinite(full_density).all()
                or not np.isfinite(baseline_response).all() or r_rq <= 0
                or np.any(l2_density <= 0) or np.any(quiet_density <= 0)):
            raise ValueError(f"Invalid Phase 3 density row for {storm_id}.")
        result[storm_id] = {
            "time_us": time_us,
            "rho_l2_phase_kg_m3": l2_density,
            "rho_msis_quiet_phase_kg_m3": quiet_density,
            "rho_msis_full_phase_kg_m3": full_density,
            "log_density_anomaly": np.log(l2_density / quiet_density),
            "h_baseline_nt": baseline_response,
            "r_rq": r_rq,
        }
    return result


def prepare_events(density_by_storm: dict[str, dict]) -> list[EventFitData]:
    """Input: {storm_id: density arrays}. Output: [event data with 0.1-hour H grid]."""
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        sme, first_time_us = load_sme(database)
        phase_events = [load_event(database, storm_id, first_time_us)
                        for storm_id in density_by_storm]
    grid = tau_grid_hours()
    response_grids = [np.empty((len(grid), len(density_by_storm[event["storm_id"]]["time_us"])))
                      for event in phase_events]
    for tau_index, tau_hours in enumerate(grid):
        response = filtered_sme(sme, float(tau_hours)) - SME_REFERENCE_NT
        for event_index, phase_event in enumerate(phase_events):
            support = phase_event["support"]
            phase_response = phase_weighted_mean(
                response[phase_event["minute_index"]], phase_event["pair_count"], support
            )
            valid_times = phase_event["time_us"][support["valid"]]
            density = density_by_storm[phase_event["storm_id"]]
            if not np.array_equal(valid_times, density["time_us"]):
                raise ValueError(f"Phase 3 time keys differ: {phase_event['storm_id']}")
            response_grids[event_index][tau_index] = phase_response[support["valid"]]
    events = [
        EventFitData(
            storm_id=phase_event["storm_id"],
            log_density_anomaly=density_by_storm[phase_event["storm_id"]]["log_density_anomaly"],
            r_rq=density_by_storm[phase_event["storm_id"]]["r_rq"],
            h_baseline_nt=density_by_storm[phase_event["storm_id"]]["h_baseline_nt"],
            h_tau_grid_nt=response_grid,
        )
        for phase_event, response_grid in zip(phase_events, response_grids, strict=True)
    ]
    if sum(len(event.log_density_anomaly) for event in events) != 214_907:
        raise ValueError("Joint fit did not load every valid Phase 3 prediction row.")
    return events


def baseline_state(events: list[EventFitData], gain_per_nt: float) -> FitState:
    """Input: [event fit data], original G. Output: frozen Phase 3 parameter state."""
    return FitState(
        log_r_by_event=np.log([event.r_rq for event in events]),
        tau_index_by_event=np.full(len(events), BASELINE_TAU_INDEX, dtype=np.int16),
        gain_per_nt=gain_per_nt,
    )


def fit_models(events: list[EventFitData], gain_per_nt: float) -> dict[str, FitResult]:
    """Input: [event fit data], original G. Output: {model name: fit result}."""
    baseline = baseline_state(events, gain_per_nt)
    offsets = update_offsets_and_gain(events, baseline)
    tau_fixed_r = fit_variable_tau(events, initial_state(events, gain_per_nt),
                                    update_gain_at_fixed_r)
    joint = fit_variable_tau(events, initial_state(events, gain_per_nt),
                             update_offsets_and_gain)
    return {
        "A_phase3_baseline": FitResult(baseline, [], True),
        "B_free_r": FitResult(offsets, [{"iteration": 1,
                                          "gain_per_nt": offsets.gain_per_nt,
                                          "changed_tau_count": 0}], True),
        "C_free_tau": tau_fixed_r,
        "D_free_r_tau": joint,
    }


def tau_range_within_one_percent(event: EventFitData, log_r: float,
                                 gain_per_nt: float) -> tuple[float, float]:
    """Input: event data, fitted log R and G. Output: tau range within 1% loss."""
    residual = event.log_density_anomaly - log_r - gain_per_nt * event.h_tau_grid_nt
    loss = np.mean(residual * residual, axis=1)
    accepted = tau_grid_hours()[loss <= float(np.min(loss)) * 1.01]
    return float(accepted[0]), float(accepted[-1])


def event_rows(events: list[EventFitData], fits: dict[str, FitResult]) -> list[dict]:
    """Input: [event fit data], {model: fit result}. Output: per-event result rows."""
    rows = []
    grid = tau_grid_hours()
    for model_name, result in fits.items():
        state = result.state
        for event, log_r, tau_index in zip(
            events, state.log_r_by_event, state.tau_index_by_event, strict=True
        ):
            r_fit = math.exp(log_r)
            if tau_index == BASELINE_TAU_INDEX:
                tau_hours = BASELINE_TAU_HOURS
                tau_low, tau_high = BASELINE_TAU_HOURS, BASELINE_TAU_HOURS
            else:
                tau_hours = float(grid[tau_index])
                tau_low, tau_high = tau_range_within_one_percent(
                    event, log_r, state.gain_per_nt
                )
            rows.append({
                "model": model_name,
                "storm_id": event.storm_id,
                "r_rq": event.r_rq,
                "r_fit": r_fit,
                "r_fit_over_r_rq": r_fit / event.r_rq,
                "r_fit_near_upper_bound": int(r_fit >= MAX_R_VALUE * 0.99),
                "tau_hours": tau_hours,
                "tau_within_1pct_low_hours": tau_low,
                "tau_within_1pct_high_hours": tau_high,
            })
    return rows


def model_rows(events: list[EventFitData], fits: dict[str, FitResult]) -> list[dict]:
    """Input: [event fit data], {model: fit result}. Output: model comparison rows."""
    rows = []
    for model_name, result in fits.items():
        rows.append({
            "model": model_name,
            "converged": int(result.converged),
            "outer_iterations": len(result.iteration_rows),
            "gain_per_nt": result.state.gain_per_nt,
            **model_score(events, result.state),
        })
    return rows


def iteration_rows(fits: dict[str, FitResult]) -> list[dict]:
    """Input: {model: fit result}. Output: joint-fit iteration rows."""
    return [
        {"model": model_name, **row}
        for model_name, result in fits.items()
        for row in result.iteration_rows
    ]


def write_csv(rows: list[dict], path: Path) -> None:
    """Input: [{field: value}], new CSV path. Output: saved Trial4 CSV."""
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def validate_fits(events: list[EventFitData], fits: dict[str, FitResult]) -> None:
    """Input: [event fit data], {model: fit result}. Output: raises on invalid fit."""
    if set(fits) != {"A_phase3_baseline", "B_free_r", "C_free_tau", "D_free_r_tau"}:
        raise ValueError("Joint fit did not produce all four planned models.")
    for result in fits.values():
        state = result.state
        r_values = np.exp(state.log_r_by_event)
        if (not np.isfinite(r_values).all() or np.any(r_values <= 0)
                or np.any(r_values >= MAX_R_VALUE) or state.gain_per_nt <= 0):
            raise ValueError("Joint fit produced invalid R or G.")
    if len(events) != 25:
        raise ValueError("Joint fit event count changed.")


def main() -> None:
    """Input: frozen Phase 2/3 data. Output: Trial4 joint-fit CSV reports."""
    output_paths = (MODEL_REPORT, EVENT_REPORT, ITERATION_REPORT)
    if any(path.exists() for path in output_paths):
        raise FileExistsError("Trial4 joint-fit outputs already exist.")
    events = prepare_events(load_density_rows())
    fits = fit_models(events, load_initial_gain())
    validate_fits(events, fits)
    write_csv(model_rows(events, fits), MODEL_REPORT)
    write_csv(event_rows(events, fits), EVENT_REPORT)
    write_csv(iteration_rows(fits), ITERATION_REPORT)
    score = next(row for row in model_rows(events, fits)
                 if row["model"] == "D_free_r_tau")
    print("Saved Trial4 joint fit: "
          f"RMSE={score['event_equal_rmse_log_density']:.6f}, "
          f"G={score['gain_per_nt']:.9f}")


if __name__ == "__main__":
    main()
