"""Build the Phase 4 Trial4-residual GPR and its altitude input."""

import csv
import json
import math
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import numpy as np

from phases.phase0.code.calculation.density.calc_msis_p2_4 import (
    load_msis_weather,
    sample_drivers,
)
from phases.phase0.code.data.density.load_dnsapod import load_dnsapod
from phases.phase2.code.prep_24_density_t0_phase import (
    DensityPaths,
    checked_manifest,
    minute_label,
    minute_targets,
    required_days,
)
from phases.phase3.code.calc_h_tau import filtered_sme, phase_weighted_mean
from phases.phase3.code.prep_h_tau_phase import SOURCE, load_event, load_sme
from phases.phase4.code.calc_phase4_trial4_gpr import (
    ALPHA,
    FEATURE_NAMES,
    RANDOM_STATE,
    fit_gpr,
    hyperparameters,
    score,
)


ROOT = Path("phases/phase4")
TRIAL4_SOURCE = Path(
    "phases/phase3-trial4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite"
)
OUTPUT = ROOT / "data/sqlite/swarm_a_phase4_trial4_altitude_gpr_v1.sqlite"
METRICS = ROOT / "data/analysis/phase4_trial4_altitude_event_metrics.csv"
HYPERPARAMS = ROOT / "data/analysis/phase4_trial4_altitude_gpr_hyperparams.csv"
SCALER_PARAMS = ROOT / "data/analysis/phase4_trial4_altitude_scaler.json"
ALGORITHM_VERSION = "phase4_trial4_altitude_gpr_v1"
SME_REFERENCE_NT = 65.0
EXPECTED_STORM_COUNT = 25


def nearest_phase_anchors(u_rad: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Input: [phase radians], [valid flags]. Output: one valid index near each 2pi grid."""
    selected = {}
    tolerance_rad = 0.02 * math.pi
    for index in np.flatnonzero(valid):
        grid_index = round(float(u_rad[index]) / (2 * math.pi))
        distance = abs(float(u_rad[index]) - 2 * math.pi * grid_index)
        if distance > tolerance_rad:
            continue
        previous = selected.get(grid_index)
        if previous is None or distance < previous[0]:
            selected[grid_index] = (distance, int(index))
    return np.array([selected[key][1] for key in sorted(selected)], dtype=np.int64)


def load_trial4_by_storm() -> dict[str, dict]:
    """Input: read-only Trial4 SQLite. Output: {storm_id: aligned Trial4 minute arrays}."""
    uri = f"file:{TRIAL4_SOURCE.resolve().as_posix()}?mode=ro"
    grouped: dict[str, list[tuple]] = {}
    with closing(sqlite3.connect(uri, uri=True)) as database:
        rows = database.execute("""
            SELECT storm_id,time_us,h_phase_nt,rho_l2_phase_kg_m3,
                   rho_trial4_joint_phase_kg_m3,residual_log_density,
                   r_fit,tau_hours,gain_per_nt
            FROM trial4_joint_fit_minute ORDER BY storm_id,time_us
        """).fetchall()
    for row in rows:
        grouped.setdefault(row[0], []).append(row[1:])
    if len(grouped) != EXPECTED_STORM_COUNT:
        raise ValueError("Trial4 must contain 25 storms.")
    output = {}
    for storm_id, storm_rows in grouped.items():
        output[storm_id] = {
            "time_us": np.array([row[0] for row in storm_rows], dtype=np.int64),
            "h_tau": np.array([row[1] for row in storm_rows], dtype=float),
            "rho_l2": np.array([row[2] for row in storm_rows], dtype=float),
            "rho_trial4": np.array([row[3] for row in storm_rows], dtype=float),
            "residual": np.array([row[4] for row in storm_rows], dtype=float),
            "r_fit": float(storm_rows[0][5]),
            "tau_hours": float(storm_rows[0][6]),
            "gain_per_nt": float(storm_rows[0][7]),
        }
    return output


def load_events(storm_ids: set[str]) -> tuple[list[dict], np.ndarray]:
    """Input: Trial4 storm IDs. Output: [P2 event supports] and continuous SME."""
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        sme, first_time_us = load_sme(database)
        ordered = [row[0] for row in database.execute(
            "SELECT storm_id FROM storm_event_t0_phase_v5 ORDER BY t0_time_us"
        )]
        if set(ordered) != storm_ids:
            raise ValueError("Trial4 and Phase 2 storm IDs differ.")
        events = [load_event(database, storm_id, first_time_us) for storm_id in ordered]
        for event in events:
            rows = database.execute("""
                SELECT source_time_us,symh_nt FROM storm_minute_feature_v5
                WHERE storm_id=? ORDER BY source_time_us
            """, (event["storm_id"],)).fetchall()
            times = np.array([row[0] for row in rows], dtype=np.int64)
            if not np.array_equal(times, event["time_us"]):
                raise ValueError(f"SYM-H keys differ: {event['storm_id']}")
            event["symh_nt"] = np.array([row[1] for row in rows], dtype=float)
    return events, sme


def collect_native_altitudes() -> dict[tuple[str, int], tuple[float, int]]:
    """Input: frozen P2.6 and DNSAPOD ZIPs. Output: {(storm,time): altitude sum,count}."""
    uri = f"file:{SOURCE.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        targets = minute_targets(database)
        days = required_days(database)
    paths = DensityPaths()
    weather = load_msis_weather(paths.gfz_ap, paths.solar)
    totals: dict[tuple[str, int], list[float]] = {}
    files = checked_manifest(paths, days)
    for number, zip_path in enumerate(files, 1):
        for sample in load_dnsapod(zip_path)["samples"]:
            minute_us = minute_label(sample["time_us"])
            storm_ids = targets.get(minute_us)
            if storm_ids is None or sample["rho_l2_kg_m3"] is None:
                continue
            if sample_drivers(sample["time_us"], weather) is None:
                continue
            for storm_id in storm_ids:
                total = totals.setdefault((storm_id, minute_us), [0.0, 0.0])
                total[0] += sample["altitude_m"]
                total[1] += 1
        if number % 50 == 0 or number == len(files):
            print(f"Read altitude {number}/{len(files)} DNSAPOD days", flush=True)
    return {key: (value[0], int(value[1])) for key, value in totals.items()}


def attach_altitude(events: list[dict], totals: dict[tuple[str, int], tuple[float, int]]) -> None:
    """Input: [events], native altitude totals. Output: attaches phase altitude arrays."""
    for event in events:
        altitude = np.full(len(event["time_us"]), np.nan)
        for index, time_us in enumerate(event["time_us"]):
            total, count = totals.get((event["storm_id"], int(time_us)), (0.0, 0))
            expected = int(event["pair_count"][index])
            if count != expected:
                raise ValueError(f"Altitude pairing differs: {event['storm_id']}:{time_us}")
            if count:
                altitude[index] = total / count
        event["altitude_phase_m"] = phase_weighted_mean(
            altitude, event["pair_count"], event["support"]
        )


def attach_fixed_features(events: list[dict], sme: np.ndarray) -> None:
    """Input: [events], continuous SME. Output: attaches H24, SME, and SYM-H phase means."""
    response_24h = filtered_sme(sme, 24.0) - SME_REFERENCE_NT
    for event in events:
        support = event["support"]
        minute_index = event["minute_index"]
        event["h_24h_phase_nt"] = phase_weighted_mean(
            response_24h[minute_index], event["pair_count"], support
        )
        event["sme_phase_nt"] = phase_weighted_mean(
            sme[minute_index], event["pair_count"], support
        )
        event["symh_phase_nt"] = phase_weighted_mean(
            event["symh_nt"], event["pair_count"], support
        )


def build_anchor_data(events: list[dict], trial4: dict[str, dict]) -> dict:
    """Input: [featured events], Trial4 minute rows. Output: aligned Phase 4 anchors."""
    rows = []
    for event in events:
        storm_id = event["storm_id"]
        source = trial4[storm_id]
        if not np.array_equal(event["time_us"][event["support"]["valid"]], source["time_us"]):
            raise ValueError(f"Trial4 keys differ from Phase 2 support: {storm_id}")
        valid_indices = np.flatnonzero(event["support"]["valid"])
        anchors = nearest_phase_anchors(event["u_rel_rad"], event["support"]["valid"])
        source_index = {int(time_us): index for index, time_us in enumerate(source["time_us"])}
        for anchor in anchors:
            time_us = int(event["time_us"][anchor])
            index = source_index[time_us]
            rows.append({
                "storm_id": storm_id,
                "time_us": time_us,
                "u_rel_rad": float(event["u_rel_rad"][anchor]),
                "altitude_phase_m": float(event["altitude_phase_m"][anchor]),
                "h_24h_phase_nt": float(event["h_24h_phase_nt"][anchor]),
                "sme_phase_nt": float(event["sme_phase_nt"][anchor]),
                "symh_phase_nt": float(event["symh_phase_nt"][anchor]),
                "phase_paired_coverage": float(event["support"]["coverage"][anchor]),
                "h_tau_phase_nt": float(source["h_tau"][index]),
                "rho_l2_phase_kg_m3": float(source["rho_l2"][index]),
                "rho_trial4_phase_kg_m3": float(source["rho_trial4"][index]),
                "residual_log_density": float(source["residual"][index]),
                "r_fit": source["r_fit"],
                "tau_hours": source["tau_hours"],
                "gain_per_nt": source["gain_per_nt"],
            })
        if len(valid_indices) == 0:
            raise ValueError(f"No valid phase support: {storm_id}")
    if len(rows) != 2295:
        raise ValueError(f"Expected 2295 one-cycle anchors, found {len(rows)}.")
    if any(not math.isfinite(row["altitude_phase_m"]) for row in rows):
        raise ValueError("Altitude is missing at a selected Phase 4 anchor.")
    return {"rows": rows}


def fit_anchor_model(data: dict) -> dict:
    """Input: aligned anchor records. Output: fitted in-sample GPR predictions and metrics."""
    rows = data["rows"]
    features = np.array([[row[name] for name in FEATURE_NAMES] for row in rows])
    residual = np.array([row["residual_log_density"] for row in rows])
    fitted = fit_gpr(features, residual)
    mean, std = fitted["model"].predict(fitted["scaler"].transform(features), return_std=True)
    for row, correction, uncertainty in zip(rows, mean, std, strict=True):
        row["gp_log_residual_mean"] = float(correction)
        row["gp_log_residual_std"] = float(uncertainty)
        row["rho_gpr_median_kg_m3"] = float(
            row["rho_trial4_phase_kg_m3"] * math.exp(correction)
        )
        row["rho_95_lower_kg_m3"] = float(
            row["rho_trial4_phase_kg_m3"] * math.exp(correction - 1.96 * uncertainty)
        )
        row["rho_95_upper_kg_m3"] = float(
            row["rho_trial4_phase_kg_m3"] * math.exp(correction + 1.96 * uncertainty)
        )
    metrics = []
    for storm_id in sorted({row["storm_id"] for row in rows}):
        mask = np.array([row["storm_id"] == storm_id for row in rows])
        metrics.append({"storm_id": storm_id, "anchor_count": int(mask.sum()),
                        **score(residual[mask], mean[mask], std[mask])})
    overall = {"storm_id": "all_anchors", "anchor_count": len(rows),
               **score(residual, mean, std)}
    parameters = hyperparameters(fitted["model"])
    parameters["convergence_warning_count"] = fitted["warnings_count"]
    return {"rows": rows, "metrics": metrics, "overall": overall,
            "parameters": parameters, "scaler": fitted["scaler"]}


def write_csv(path: Path, rows: list[dict]) -> None:
    """Input: new CSV path, [{field: value}]. Output: saved UTF-8 CSV."""
    with path.open("x", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_sqlite(result: dict) -> None:
    """Input: fitted Phase 4 result. Output: atomic SQLite with altitude and predictions."""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix="phase4_trial4.", suffix=".building", dir=OUTPUT.parent)
    os.close(handle)
    temporary = Path(name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            database.executescript("""
                CREATE TABLE phase4_altitude_anchor (
                    storm_id TEXT NOT NULL, time_us INTEGER NOT NULL,
                    altitude_phase_m REAL NOT NULL, phase_paired_coverage REAL NOT NULL,
                    algorithm_version TEXT NOT NULL, PRIMARY KEY (storm_id,time_us)
                );
                CREATE TABLE phase4_trial4_gpr_prediction (
                    storm_id TEXT NOT NULL, time_us INTEGER NOT NULL, u_rel_rad REAL NOT NULL,
                    h_tau_phase_nt REAL NOT NULL, h_24h_phase_nt REAL NOT NULL,
                    sme_phase_nt REAL NOT NULL, symh_phase_nt REAL NOT NULL,
                    altitude_phase_m REAL NOT NULL, rho_l2_phase_kg_m3 REAL NOT NULL,
                    rho_trial4_phase_kg_m3 REAL NOT NULL, residual_log_density REAL NOT NULL,
                    rho_gpr_median_kg_m3 REAL NOT NULL, gp_log_residual_mean REAL NOT NULL,
                    gp_log_residual_std REAL NOT NULL, rho_95_lower_kg_m3 REAL NOT NULL,
                    rho_95_upper_kg_m3 REAL NOT NULL, r_fit REAL NOT NULL,
                    tau_hours REAL NOT NULL, gain_per_nt REAL NOT NULL,
                    algorithm_version TEXT NOT NULL, PRIMARY KEY (storm_id,time_us)
                );
                CREATE TABLE phase4_metadata (name TEXT PRIMARY KEY,value TEXT NOT NULL);
            """)
            rows = result["rows"]
            database.executemany("INSERT INTO phase4_altitude_anchor VALUES (?,?,?,?,?)", (
                (row["storm_id"], row["time_us"], row["altitude_phase_m"],
                 row["phase_paired_coverage"], ALGORITHM_VERSION) for row in rows
            ))
            fields = [
                "storm_id", "time_us", "u_rel_rad", "h_tau_phase_nt", "h_24h_phase_nt",
                "sme_phase_nt", "symh_phase_nt", "altitude_phase_m", "rho_l2_phase_kg_m3",
                "rho_trial4_phase_kg_m3", "residual_log_density", "rho_gpr_median_kg_m3",
                "gp_log_residual_mean", "gp_log_residual_std", "rho_95_lower_kg_m3",
                "rho_95_upper_kg_m3", "r_fit", "tau_hours", "gain_per_nt",
            ]
            database.executemany("INSERT INTO phase4_trial4_gpr_prediction VALUES ("
                                 + ",".join("?" for _ in range(20)) + ")", (
                tuple(row[field] for field in fields) + (ALGORITHM_VERSION,) for row in rows
            ))
            metadata = {
                "evaluation": "retrospective descriptive in-sample; not forecast or held-out validation",
                "feature_names": ",".join(FEATURE_NAMES),
                "phase_window": "u +/- pi, paired native samples, centered",
                "trial4_source": str(TRIAL4_SOURCE),
                "altitude_source": "DNSAPOD altitude_m paired to P2.6 density samples",
            }
            database.executemany("INSERT INTO phase4_metadata VALUES (?,?)", metadata.items())
            found = database.execute("SELECT count(*) FROM phase4_trial4_gpr_prediction").fetchone()[0]
            if found != len(rows) or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Phase 4 SQLite audit failed.")
            database.commit()
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    """Input: frozen P2.6 DNSAPOD and Trial4 SQLite. Output: Phase 4 derived result."""
    outputs = (OUTPUT, METRICS, HYPERPARAMS, SCALER_PARAMS)
    if any(path.exists() for path in outputs):
        raise FileExistsError("Phase 4 outputs already exist.")
    trial4 = load_trial4_by_storm()
    events, sme = load_events(set(trial4))
    attach_fixed_features(events, sme)
    attach_altitude(events, collect_native_altitudes())
    result = fit_anchor_model(build_anchor_data(events, trial4))
    METRICS.parent.mkdir(parents=True, exist_ok=True)
    write_sqlite(result)
    write_csv(METRICS, result["metrics"] + [result["overall"]])
    write_csv(HYPERPARAMS, [result["parameters"]])
    SCALER_PARAMS.write_text(json.dumps({
        "algorithm_version": ALGORITHM_VERSION,
        "feature_names": FEATURE_NAMES,
        "mean": result["scaler"].mean_.tolist(),
        "scale": result["scaler"].scale_.tolist(),
        "anchor_count": len(result["rows"]),
    }, indent=2), encoding="utf-8")
    from phases.phase4.code.prep_phase4_trial4_figures import main as draw_figures

    draw_figures()
    print(f"Saved Phase 4 Trial4 GPR for {len(result['rows'])} anchors")


if __name__ == "__main__":
    main()
