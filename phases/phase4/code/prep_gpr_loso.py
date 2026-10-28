"""Run storm-held-out GPR correction on centered phase anchors."""

import argparse
import csv
import json
import math
import os
import sqlite3
import tempfile
import time
from contextlib import closing
from pathlib import Path

import numpy as np

from phases.phase4.code.calc_phase4_gpr import (
    ALPHA, RANDOM_STATE, TAU_STEPS, TAU_STEP_HOURS, fit_gpr, fit_physics,
    hyperparameters, make_features, score,
)
from phases.phase4.code.load_phase4_inputs import (
    FEATURE_NAMES, PHASE3_RESULTS, SME_REFERENCE_NT, load_inputs, load_r_values,
)
from phases.phase3.code.calc_h_tau import filtered_sme, phase_weighted_mean


ROOT = Path("phases/phase4")
PREDICTIONS = ROOT / "data/sqlite/swarm_a_phase4_gpr_loso_v1.sqlite"
METRICS = ROOT / "data/analysis/phase4_loso_event_metrics.csv"
HYPERPARAMS = ROOT / "data/analysis/gpr_hyperparams.csv"
SCALER_PARAMS = ROOT / "data/analysis/scaler_params.json"
FOLD_DIR = ROOT / "data/analysis/folds_default_optimizer"
ALGORITHM_VERSION = "phase4_gpr_loso_v1"


def response_grid(events: list[dict], sme: np.ndarray) -> None:
    """Input: [events], continuous SME nT. Output: attaches [anchor x 201 H_tau]."""
    for event in events:
        event["h_grid"] = np.empty((len(event["anchors"]), TAU_STEPS))
    for tau_index in range(TAU_STEPS):
        response = filtered_sme(sme, tau_index * TAU_STEP_HOURS) - SME_REFERENCE_NT
        for event in events:
            phase = phase_weighted_mean(
                response[event["minute_index"]], event["pair_count"], event["support"])
            event["h_grid"][:, tau_index] = phase[event["anchors"]]
    if any(not np.isfinite(event["h_grid"]).all() for event in events):
        raise ValueError("Response grid has missing anchor values.")


def combine_events(events: list[dict], r_values: dict[str, float]) -> dict:
    """Input: [event anchor arrays], {storm: R}. Output: aligned fold arrays."""
    identifiers = np.concatenate([
        np.repeat(event["storm_id"], len(event["anchors"])) for event in events
    ])
    time_us = np.concatenate([event["time_us"][event["anchors"]] for event in events])
    u_rad = np.concatenate([event["u_rel_rad"][event["anchors"]] for event in events])
    rho_l2 = np.concatenate([event["rho_l2"] for event in events])
    rho_quiet = np.concatenate([event["rho_quiet"] for event in events])
    log_r = np.array([math.log(r_values[storm_id]) for storm_id in identifiers])
    fixed = np.concatenate([
        np.column_stack((event["h_24h_phase"], event["sme_phase"],
                         event["symh_phase"])) for event in events
    ])
    h_grid = np.concatenate([event["h_grid"] for event in events])
    if len(np.unique(time_us)) != len(time_us):
        raise ValueError("Storm anchors contain duplicate time keys.")
    return {"storm_id": identifiers, "time_us": time_us, "u_rad": u_rad,
            "rho_l2": rho_l2, "rho_quiet": rho_quiet, "log_r": log_r,
            "z": np.log(rho_l2 / rho_quiet) - log_r,
            "fixed": fixed, "h_grid": h_grid}


def run_fold(data: dict, held_out_storm: str) -> dict:
    """Input: aligned anchors, held-out storm. Output: predictions and fold diagnostics."""
    train = data["storm_id"] != held_out_storm
    test = ~train
    if not np.any(test) or np.count_nonzero(train) + np.count_nonzero(test) != len(train):
        raise ValueError("Leave-one-storm-out partition is invalid.")
    physical = fit_physics(data["z"][train], data["h_grid"][train])
    h_tau = data["h_grid"][:, physical["tau_index"]]
    features = make_features(h_tau, data["fixed"])
    log_physical = data["log_r"] + physical["gain_per_nt"] * h_tau
    residual = data["z"] - physical["gain_per_nt"] * h_tau
    fitted = fit_gpr(features[train], residual[train])
    scaler = fitted["scaler"]
    model = fitted["model"]
    gp_mean, gp_std = model.predict(scaler.transform(features[test]), return_std=True)
    train_mean, train_std = model.predict(scaler.transform(features[train]), return_std=True)
    predicted_physical = data["rho_quiet"][test] * np.exp(log_physical[test])
    corrected = predicted_physical * np.exp(gp_mean)
    observed = data["rho_l2"][test]
    baseline_error = np.log(observed / predicted_physical)
    metrics = {"storm_id": held_out_storm, "test_anchors": int(np.count_nonzero(test)),
               "train_anchors": int(np.count_nonzero(train)),
               "tau_hours": physical["tau_hours"], "gain_per_nt": physical["gain_per_nt"],
               "m1_rmse_log_density": float(np.sqrt(np.mean(baseline_error ** 2))),
               "m1_mae_log_density": float(np.mean(np.abs(baseline_error))),
               **{f"gpr_{key}": value for key, value in score(
                   residual[test], gp_mean, gp_std).items()},
               "train_coverage_95": score(residual[train], train_mean, train_std)[
                   "coverage_95"]}
    predictions = list(zip(
        data["time_us"][test].tolist(), data["u_rad"][test].tolist(),
        observed.tolist(), predicted_physical.tolist(), corrected.tolist(),
        gp_mean.tolist(), gp_std.tolist(),
        (predicted_physical * np.exp(gp_mean - 1.96 * gp_std)).tolist(),
        (predicted_physical * np.exp(gp_mean + 1.96 * gp_std)).tolist(),
    ))
    params = {"storm_id": held_out_storm, **physical, **hyperparameters(model),
              "alpha": ALPHA, "random_state": RANDOM_STATE,
              "n_restarts_optimizer": 5, "normalize_y": False,
              "optimizer": "scikit_learn_default_fmin_l_bfgs_b",
              "convergence_warning_count": fitted["convergence_warning_count"]}
    scaler_record = {"feature_names": FEATURE_NAMES,
                     "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(),
                     "train_anchors": int(np.count_nonzero(train))}
    return {"predictions": predictions, "metrics": metrics,
            "hyperparameters": params, "scaler": scaler_record}


def fold_path(storm_id: str) -> Path:
    """Input: held-out storm ID. Output: Phase 4 fold checkpoint path."""
    return FOLD_DIR / f"{storm_id}.json"


def load_fold(storm_id: str) -> dict:
    """Input: held-out storm ID. Output: matching saved fold result."""
    result = json.loads(fold_path(storm_id).read_text(encoding="utf-8"))
    params = result["hyperparameters"]
    if (result["metrics"]["storm_id"] != storm_id
            or params["optimizer"] != "scikit_learn_default_fmin_l_bfgs_b"
            or params["n_restarts_optimizer"] != 5):
        raise ValueError(f"Fold checkpoint settings differ for {storm_id}.")
    return result


def save_fold(result: dict) -> None:
    """Input: completed fold result. Output: atomic Phase 4 JSON checkpoint."""
    FOLD_DIR.mkdir(parents=True, exist_ok=True)
    path = fold_path(result["metrics"]["storm_id"])
    if path.exists():
        raise FileExistsError(f"Fold checkpoint already exists: {path}")
    handle, name = tempfile.mkstemp(prefix="phase4_fold.", suffix=".building", dir=FOLD_DIR)
    os.close(handle)
    temporary = Path(name)
    try:
        temporary.write_text(json.dumps(result), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_csv(path: Path, rows: list[dict]) -> None:
    """Input: new CSV path and [{field: value}]. Output: saved report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_predictions(results: list[dict]) -> None:
    """Input: [fold result]. Output: new keyed Phase 4 prediction SQLite."""
    PREDICTIONS.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(
        prefix="phase4_gpr.", suffix=".building", dir=PREDICTIONS.parent)
    os.close(handle)
    temporary = Path(name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            database.execute("""
                CREATE TABLE phase4_gpr_prediction (
                    storm_id TEXT NOT NULL, time_us INTEGER NOT NULL,
                    u_rel_rad REAL NOT NULL, rho_l2_phase_kg_m3 REAL NOT NULL,
                    rho_phys_phase_kg_m3 REAL NOT NULL,
                    rho_gpr_median_kg_m3 REAL NOT NULL,
                    gp_log_residual_mean REAL NOT NULL,
                    gp_log_residual_std REAL NOT NULL,
                    rho_95_lower_kg_m3 REAL NOT NULL,
                    rho_95_upper_kg_m3 REAL NOT NULL,
                    algorithm_version TEXT NOT NULL,
                    PRIMARY KEY (storm_id,time_us)
                )
            """)
            database.execute("CREATE TABLE phase4_gpr_metadata "
                             "(name TEXT PRIMARY KEY,value TEXT NOT NULL)")
            database.executemany("INSERT INTO phase4_gpr_metadata VALUES (?,?)", (
                ("feature_names", ",".join(FEATURE_NAMES)),
                ("phase_grid", "nearest valid u=2*pi*j within 0.01 cycles"),
                ("phase_window", "u +/- pi, paired native samples, centered"),
                ("phase3_source", str(PHASE3_RESULTS)),
                ("scikit_learn", __import__("sklearn").__version__),
            ))
            for result in results:
                storm_id = result["metrics"]["storm_id"]
                database.executemany("INSERT INTO phase4_gpr_prediction VALUES "
                                     "(?,?,?,?,?,?,?,?,?,?,?)", (
                    (storm_id, int(row[0]), *row[1:], ALGORITHM_VERSION)
                    for row in result["predictions"]
                ))
            expected = sum(len(result["predictions"]) for result in results)
            found = database.execute("SELECT count(*) FROM phase4_gpr_prediction").fetchone()[0]
            if found != expected or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Phase 4 SQLite output integrity check failed.")
            database.commit()
        os.replace(temporary, PREDICTIONS)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    """Input: frozen Phase 2/3 data; optional trial fold. Output: Phase 4 validation."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--trial", action="store_true", help="fit only the first held-out storm")
    args = parser.parse_args()
    outputs = (PREDICTIONS, METRICS, HYPERPARAMS, SCALER_PARAMS)
    if not args.trial and any(path.exists() for path in outputs):
        raise FileExistsError("Phase 4 output already exists.")
    started = time.monotonic()
    events, sme = load_inputs()
    response_grid(events, sme)
    data = combine_events(events, load_r_values())
    print(f"Prepared {len(data['storm_id'])} anchors in {time.monotonic() - started:.1f}s", flush=True)
    storms = [event["storm_id"] for event in events]
    if args.trial:
        storms = storms[:1]
    results = []
    for storm_id in storms:
        fold_started = time.monotonic()
        if not args.trial and fold_path(storm_id).exists():
            result = load_fold(storm_id)
            print(f"Reused checkpoint for {storm_id}", flush=True)
        else:
            result = run_fold(data, storm_id)
            if not args.trial:
                save_fold(result)
        results.append(result)
        metrics = result["metrics"]
        print(f"{storm_id}: tau={metrics['tau_hours']:.2f}h, "
              f"M1 RMSE={metrics['m1_rmse_log_density']:.4f}, "
              f"GPR RMSE={metrics['gpr_rmse_log_density']:.4f}, "
              f"coverage={metrics['gpr_coverage_95']:.3f}, "
              f"convergence_warnings={result['hyperparameters']['convergence_warning_count']}, "
              f"elapsed={time.monotonic() - fold_started:.1f}s", flush=True)
    if args.trial:
        return
    write_predictions(results)
    write_csv(METRICS, [result["metrics"] for result in results])
    write_csv(HYPERPARAMS, [result["hyperparameters"] for result in results])
    SCALER_PARAMS.write_text(json.dumps({
        "algorithm_version": ALGORITHM_VERSION,
        "folds": {result["metrics"]["storm_id"]: result["scaler"] for result in results},
    }, indent=2), encoding="utf-8")
    from phases.phase4.code.prep_gpr_figures import main as draw_gpr_figures

    draw_gpr_figures()
    print(f"Saved {len(storms)} folds in {time.monotonic() - started:.1f}s", flush=True)


if __name__ == "__main__":
    main()
