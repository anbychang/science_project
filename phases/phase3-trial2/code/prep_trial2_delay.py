"""Run balanced storm holdouts for an M1 response with a shared delay."""

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from phases.phase3.code.calc_h_tau import filtered_sme, phase_weighted_mean

from calc_trial2_delay import (
    DELTA_MINUTES, FINE_TAU_HOURS, JOINT_TAU_HOURS, M1_TAU_HOURS,
    balanced_splits, event_mean_rmse, fit_gain,
    fixed_gain_error, heldout_rmse, response_statistics,
)
from load_trial2_inputs import load_continuous_sme, load_events


MAINLINE_GAIN_PER_NT = 0.0007032326071208369
IMPROVEMENT_GATE = 0.03


def check_mainline(sme_nt: np.ndarray, events: list[dict]) -> float:
    """Input: continuous SME and M1 pairs. Output: maximum H difference in nT."""
    response = filtered_sme(sme_nt - 65.0, M1_TAU_HOURS)
    maximum = 0.0
    for event in events:
        phase = phase_weighted_mean(response[event["minute_index"]],
                                    event["pairs"], event["support"])
        valid = phase[event["support"]["valid"]]
        maximum = max(maximum, float(np.max(np.abs(valid - event["original_h"]))))
    if maximum > 1e-6:
        raise ValueError(f"delta=0 failed to reproduce M1: {maximum} nT")
    return maximum


def first_stage(sme_nt: np.ndarray, events: list[dict],
                splits: list[tuple]) -> dict:
    """Input: SME, events, balanced splits. Output: fixed-tau delay holdouts."""
    baseline_candidates = [(tau, 0) for tau in FINE_TAU_HOURS]
    baseline_cross, baseline_h2 = response_statistics(
        sme_nt, events, baseline_candidates
    )
    z2 = np.array([event["anomaly_squared"] for event in events])
    counts = np.array([event["count"] for event in events])
    delay_cache = {}
    folds = []
    scores = []
    for fold_id, train, test in splits:
        train_cross = baseline_cross[:, train].sum(axis=1)
        train_h2 = baseline_h2[:, train].sum(axis=1)
        gains, errors = fit_gain(train_cross, train_h2, float(z2[train].sum()))
        best_tau_index = int(np.argmin(errors))
        gain = float(gains[best_tau_index])
        tau_hours = FINE_TAU_HOURS[best_tau_index]
        if best_tau_index not in delay_cache:
            delay_cache[best_tau_index] = response_statistics(
                sme_nt, events, [(tau_hours, delay) for delay in DELTA_MINUTES]
            )
        delay_cross, delay_h2 = delay_cache[best_tau_index]
        delay_errors = fixed_gain_error(
            (delay_cross[:, train].sum(axis=1),
             delay_h2[:, train].sum(axis=1)), float(z2[train].sum()), gain
        )
        best_delay_index = int(np.argmin(delay_errors))
        if not np.allclose(delay_cross[0], baseline_cross[best_tau_index], atol=1e-7):
            raise ValueError(f"delta=0 statistics changed in fold {fold_id}")
        folds.append({
            "fold": fold_id, "train": train, "test": test,
            "tau_hours": tau_hours, "gain_per_nt": gain,
            "delta_minutes": DELTA_MINUTES[best_delay_index],
            "train_rmse_m1": math.sqrt(float(errors[best_tau_index])
                                       / int(counts[train].sum())),
            "train_rmse_delay": math.sqrt(float(delay_errors[best_delay_index])
                                          / int(counts[train].sum())),
        })
        for event_index in test:
            event = events[int(event_index)]
            scores.append({
                "fold": fold_id, "event_index": int(event_index),
                "rmse_m1": heldout_rmse(event, (
                    float(baseline_cross[best_tau_index, event_index]),
                    float(baseline_h2[best_tau_index, event_index])), gain),
                "rmse_delay": heldout_rmse(event, (
                    float(delay_cross[best_delay_index, event_index]),
                    float(delay_h2[best_delay_index, event_index])), gain),
            })
        if (fold_id + 1) % 20 == 0:
            print(f"Fixed-tau holdouts: {fold_id + 1}/100", flush=True)
    m1_mean = event_mean_rmse(scores, "rmse_m1", len(events))
    delay_mean = event_mean_rmse(scores, "rmse_delay", len(events))
    improvement = 1 - float(np.mean(delay_mean) / np.mean(m1_mean))
    return {"folds": folds, "scores": scores, "m1_mean": m1_mean,
            "delay_mean": delay_mean, "improvement": improvement,
            "baseline_cross": baseline_cross, "baseline_h2": baseline_h2}


def second_stage(sme_nt: np.ndarray, events: list[dict],
                 first: dict) -> dict:
    """Input: SME, events, first-stage folds. Output: joint grid and holdouts."""
    candidates = [(tau, delay) for tau in JOINT_TAU_HOURS
                  for delay in DELTA_MINUTES]
    cross, h2 = response_statistics(sme_nt, events, candidates)
    z2 = np.array([event["anomaly_squared"] for event in events])
    counts = np.array([event["count"] for event in events])
    scores = []
    fitted = []
    for fold in first["folds"]:
        train, test = fold["train"], fold["test"]
        train_cross = cross[:, train].sum(axis=1)
        train_h2 = h2[:, train].sum(axis=1)
        gains, errors = fit_gain(train_cross, train_h2, float(z2[train].sum()))
        best_index = int(np.argmin(errors))
        tau_hours, delay_minutes = candidates[best_index]
        gain = float(gains[best_index])
        fitted.append({"fold": fold["fold"], "tau_hours": tau_hours,
                       "delta_minutes": delay_minutes, "gain_per_nt": gain,
                       "train_rmse_joint": math.sqrt(float(errors[best_index])
                                                     / int(counts[train].sum()))})
        for event_index in test:
            scores.append({
                "fold": fold["fold"], "event_index": int(event_index),
                "rmse_joint": heldout_rmse(events[int(event_index)], (
                    float(cross[best_index, event_index]),
                    float(h2[best_index, event_index])), gain),
            })
    joint_mean = event_mean_rmse(scores, "rmse_joint", len(events))
    improvement = 1 - float(np.mean(joint_mean) / np.mean(first["delay_mean"]))
    full_gain, full_error = fit_gain(cross.sum(axis=1), h2.sum(axis=1),
                                    float(z2.sum()))
    full_rmse = np.sqrt(full_error / int(counts.sum()))
    return {"folds": fitted, "scores": scores, "joint_mean": joint_mean,
            "improvement": improvement, "candidates": candidates,
            "full_gain": full_gain, "full_rmse": full_rmse}


def full_data_delay(sme_nt: np.ndarray, events: list[dict]) -> dict:
    """Input: SME and all events. Output: descriptive M1-fixed delay grid."""
    cross, h2 = response_statistics(
        sme_nt, events, [(M1_TAU_HOURS, delay) for delay in DELTA_MINUTES]
    )
    z2 = sum(event["anomaly_squared"] for event in events)
    count = sum(event["count"] for event in events)
    error = fixed_gain_error((cross.sum(axis=1), h2.sum(axis=1)),
                             z2, MAINLINE_GAIN_PER_NT)
    rmse = np.sqrt(error / count)
    per_event_error = fixed_gain_error(
        (cross, h2), np.array([event["anomaly_squared"] for event in events]),
        MAINLINE_GAIN_PER_NT
    )
    per_event_rmse = np.sqrt(
        per_event_error / np.array([event["count"] for event in events])
    )
    best_by_event = np.argmin(per_event_rmse, axis=0)
    return {"rmse": rmse, "best_delay_minutes": DELTA_MINUTES[int(np.argmin(rmse))],
            "event_rmse": per_event_rmse,
            "best_delay_by_event": np.array(DELTA_MINUTES)[best_by_event]}


def run_trial() -> dict:
    """Input: frozen source databases. Output: complete Trial 2 analysis arrays."""
    minute_times, sme_nt = load_continuous_sme()
    events = load_events(minute_times)
    maximum = check_mainline(sme_nt, events)
    print(f"M1 reproduction: max |H difference|={maximum:.3g} nT", flush=True)
    splits = balanced_splits(len(events))
    first = first_stage(sme_nt, events, splits)
    print(f"Fixed-tau delay improvement={first['improvement']:.4%}", flush=True)
    full_delay = full_data_delay(sme_nt, events)
    joint = None
    if first["improvement"] >= IMPROVEMENT_GATE:
        print("First-stage gate passed; scanning joint delta/tau grid", flush=True)
        joint = second_stage(sme_nt, events, first)
        print(f"Joint over delay-only improvement={joint['improvement']:.4%}", flush=True)
    return {"events": events, "sme": sme_nt, "minute_times": minute_times,
            "splits": splits, "reproduction_max_nt": maximum,
            "first": first, "full_delay": full_delay, "joint": joint}


if __name__ == "__main__":
    trial = run_trial()
    from prep_trial2_outputs import draw_figure, save_sqlite

    output = save_sqlite(trial)
    figure = draw_figure(trial)
    print(f"Full-data fixed-M1 delta={trial['full_delay']['best_delay_minutes']} min")
    print(f"Saved {output} and {figure}")
