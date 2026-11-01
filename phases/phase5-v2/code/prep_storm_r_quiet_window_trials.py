"""Predict the additive Phase 4 R correction from Phase 3 quiet-window quality."""

import math
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from phases.phase3.code.calc_h_tau import filtered_sme
from phases.phase3.code.prep_phase3_ap_check import AP_SOURCE, read_ap_minutes
from phases.phase3.code.prep_phase3_anytime_quiet_pairs import FIRST_MINUTE_US, MINUTE_US, source_symh_and_extrema
from phases.phase3.code.prep_phase3_rquiet_near_zero import near_zero_runs, nearest_pre_runs
from phases.phase3.code.prep_phase3_sme_check import SOURCE as SME_SOURCE, read_source

from prep_storm_r_feature_trials import fit_predict
from prep_storm_r_phase3_trials import load_phase3_rows, quiet_group_folds
from prep_storm_r_gpr import ROOT


OUTPUT = ROOT / "data/sqlite/storm_r_quiet_window_trials_v7.sqlite"
ALGORITHM_VERSION = "storm_r_quiet_window_trials_v7"
DAY_US = 86_400_000_000
PHASE1_WEATHER = Path("phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite")
FEATURE_SETS = {
    "phase3_r_distance": ("r_phase3", "distance_log_days"),
    "phase3_r_quiet_date": ("r_phase3", "quiet_day"),
    "phase3_r_quiet_sme": ("r_phase3", "quiet_mean_sme_nt"),
    "phase3_r_quiet_h": ("r_phase3", "quiet_max_abs_h_nt"),
    "phase3_r_quiet_duration": ("r_phase3", "quiet_duration_h"),
    "distance_quiet_sme": ("distance_log_days", "quiet_mean_sme_nt"),
    "distance_quiet_h": ("distance_log_days", "quiet_max_abs_h_nt"),
    "distance_quiet_date": ("distance_log_days", "quiet_day"),
    "phase3_r_distance_h": ("r_phase3", "distance_log_days", "quiet_max_abs_h_nt"),
    "phase3_r_distance_sme": ("r_phase3", "distance_log_days", "quiet_mean_sme_nt"),
}


def load_quiet_features() -> list[dict]:
    """Input: frozen Phase 2/3 sources and Phase 4 V2 R. Output: 25 quiet-window rows."""
    rows = load_phase3_rows()
    sme_source, events = read_source(SME_SOURCE)
    ap_source, ap_first_time = read_ap_minutes(AP_SOURCE)
    last_valid = int(np.flatnonzero(np.isfinite(sme_source))[-1]) + 1
    sme = sme_source[:last_valid]
    ap = ap_source[:last_valid]
    if int(ap_first_time.timestamp() * 1_000_000) != FIRST_MINUTE_US:
        raise ValueError("Phase 3 ap and SME origins differ.")
    runs = near_zero_runs(sme, ap)
    symh, extrema = source_symh_and_extrema(events, len(sme))
    with closing(sqlite3.connect(f"file:{SME_SOURCE.resolve().as_posix()}?mode=ro", uri=True)) as source:
        ae = np.fromiter((value for (value,) in source.execute(
            "SELECT ae_nt FROM geomag_1min_v2 ORDER BY time_us")), dtype=float, count=len(sme))
    selected = nearest_pre_runs(events, runs, extrema)
    response = filtered_sme(sme, 4.65) - 65.0
    first_end_us = min(FIRST_MINUTE_US + end * MINUTE_US for _, end in selected.values())
    for row in rows:
        start, end = selected[row["storm_id"]]
        quiet_end_us = FIRST_MINUTE_US + end * MINUTE_US
        distance_days = (extrema[row["storm_id"]][0] - end) / 1440
        if not math.isclose(distance_days, row["distance_days"], abs_tol=1e-10):
            raise ValueError(f"Quiet run differs from Phase 3: {row['storm_id']}")
        if not np.isfinite(symh[start:end]).all():
            raise ValueError(f"Missing quiet SYM-H: {row['storm_id']}")
        if start < 1440 or not np.isfinite(ae[start:end]).all():
            raise ValueError(f"Missing quiet history: {row['storm_id']}")
        quiet_start_us = FIRST_MINUTE_US + start * MINUTE_US
        with closing(sqlite3.connect(
                f"file:{PHASE1_WEATHER.resolve().as_posix()}?mode=ro", uri=True)) as weather:
            solar = weather.execute("""
                SELECT time_us,f107a_last81_sfu FROM space_weather
                WHERE time_us<=? ORDER BY time_us DESC LIMIT 1
            """, (quiet_start_us,)).fetchone()
        if solar is None or solar[1] is None or quiet_start_us - solar[0] > 3 * 60 * MINUTE_US:
            raise ValueError(f"Missing quiet F10.7A: {row['storm_id']}")
        quiet_date = datetime.fromtimestamp(quiet_end_us / 1_000_000, timezone.utc)
        quiet_sme = sme[start:end]
        quiet_h = response[start:end]
        row.update({
            "quiet_start_time_us": quiet_start_us,
            "quiet_end_exclusive_time_us": quiet_end_us,
            "quiet_day": (quiet_end_us - first_end_us) / DAY_US,
            "quiet_season_sin": math.sin(2 * math.pi * (quiet_date.timetuple().tm_yday - 1) / 365.25),
            "quiet_season_cos": math.cos(2 * math.pi * (quiet_date.timetuple().tm_yday - 1) / 365.25),
            "quiet_duration_h": (end - start) / 60,
            "quiet_mean_sme_nt": float(np.mean(quiet_sme)),
            "quiet_max_sme_nt": float(np.max(quiet_sme)),
            "quiet_std_sme_nt": float(np.std(quiet_sme)),
            "quiet_sme_trend_nt_h": float(np.polyfit(np.arange(end - start) / 60, quiet_sme, 1)[0]),
            "quiet_mean_ap": float(np.mean(ap[start:end])),
            "quiet_mean_symh_nt": float(np.mean(symh[start:end])),
            "quiet_symh_range_nt": float(np.ptp(symh[start:end])),
            "quiet_mean_h_nt": float(np.mean(quiet_h)),
            "quiet_std_h_nt": float(np.std(quiet_h)),
            "quiet_max_abs_h_nt": float(np.max(abs(quiet_h))),
            "quiet_abs_h_p90_nt": float(np.percentile(abs(quiet_h), 90)),
            "quiet_positive_h_fraction": float(np.mean(quiet_h > 0)),
            "quiet_mean_ae_nt": float(np.mean(ae[start:end])),
            "quiet_max_ae_nt": float(np.max(ae[start:end])),
            "prequiet_sme_mean_nt": float(np.mean(sme[start - 1440:start])),
            "prequiet_ap_mean": float(np.mean(ap[start - 1440:start])),
            "quiet_f107a_last81_sfu": float(solar[1]),
        })
    if len({row["quiet_end_exclusive_time_us"] for row in rows}) != 20:
        raise ValueError("Expected 20 distinct Phase 3 quiet windows.")
    return rows


def evaluate(rows: list[dict], feature_sets: dict = FEATURE_SETS) -> tuple[list[dict], list[dict]]:
    """Input: 25 quiet-window rows and candidates. Output: held-out corrections and scores."""
    targets = np.array([row["r_fit"] - row["r_phase3"] for row in rows])
    data = {name: {"features": np.array([[row[field] for field in fields]
                                         for row in rows]), "targets": targets}
            for name, fields in feature_sets.items()}
    predictions = []
    scores = []
    for fold_index, test in enumerate(quiet_group_folds(rows, np.arange(25), 5), 1):
        train = np.setdiff1d(np.arange(25), test)
        inner_folds = quiet_group_folds(rows, train, 4)
        candidates = []
        for name in feature_sets:
            squared_errors = []
            for inner_test in inner_folds:
                inner_train = np.setdiff1d(train, inner_test)
                means, _ = fit_predict(inner_train, inner_test, data[name])
                squared_errors.extend((targets[inner_test] - means) ** 2)
            candidates.append((name, math.sqrt(float(np.mean(squared_errors)))))
        selected = min(candidates, key=lambda candidate: candidate[1])[0]
        means, stds = fit_predict(train, test, data[selected])
        scores.extend({"fold_index": fold_index, "feature_set": name,
                       "inner_rmse_delta_r": score, "selected": int(name == selected)}
                      for name, score in candidates)
        for index, delta_r, std in zip(test, means, stds, strict=True):
            row = rows[int(index)]
            predicted_r = row["r_phase3"] + float(delta_r)
            if not 0 < predicted_r < 2:
                raise ValueError(f"GPR correction produced invalid R: {row['storm_id']}")
            predictions.append({**row, "fold_index": fold_index,
                                "feature_set": selected, "delta_r_pred": float(delta_r),
                                "delta_r_std": float(std), "r_pred": predicted_r})
    return sorted(predictions, key=lambda row: row["storm_id"]), scores


def save_results(predictions: list[dict], scores: list[dict]) -> None:
    """Input: 25 held-out predictions and candidate scores. Output: new SQLite tables."""
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(OUTPUT) as database:
        database.executescript("""
            CREATE TABLE storm_r_prediction (
                storm_id TEXT PRIMARY KEY, quiet_start_time_us INTEGER NOT NULL,
                quiet_end_exclusive_time_us INTEGER NOT NULL,
                distance_days REAL NOT NULL, quiet_duration_h REAL NOT NULL,
                quiet_mean_sme_nt REAL NOT NULL, quiet_max_sme_nt REAL NOT NULL,
                quiet_mean_ap REAL NOT NULL, quiet_mean_symh_nt REAL NOT NULL,
                quiet_max_abs_h_nt REAL NOT NULL, r_phase3 REAL NOT NULL,
                r_fit REAL NOT NULL, delta_r_pred REAL NOT NULL,
                delta_r_std REAL NOT NULL, r_pred REAL NOT NULL,
                fold_index INTEGER NOT NULL, feature_set TEXT NOT NULL,
                algorithm_version TEXT NOT NULL
            );
            CREATE TABLE feature_selection (
                fold_index INTEGER NOT NULL, feature_set TEXT NOT NULL,
                inner_rmse_delta_r REAL NOT NULL, selected INTEGER NOT NULL,
                algorithm_version TEXT NOT NULL, PRIMARY KEY(fold_index,feature_set)
            );
            CREATE TABLE metadata (name TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        database.executemany("INSERT INTO storm_r_prediction VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            (row["storm_id"], row["quiet_start_time_us"], row["quiet_end_exclusive_time_us"],
             row["distance_days"], row["quiet_duration_h"], row["quiet_mean_sme_nt"],
             row["quiet_max_sme_nt"], row["quiet_mean_ap"], row["quiet_mean_symh_nt"],
             row["quiet_max_abs_h_nt"], row["r_phase3"], row["r_fit"],
             row["delta_r_pred"], row["delta_r_std"], row["r_pred"],
             row["fold_index"], row["feature_set"], ALGORITHM_VERSION)
            for row in predictions
        ))
        database.executemany("INSERT INTO feature_selection VALUES (?,?,?,?,?)", (
            (row["fold_index"], row["feature_set"], row["inner_rmse_delta_r"],
             row["selected"], ALGORITHM_VERSION) for row in scores
        ))
        database.executemany("INSERT INTO metadata VALUES (?,?)", [
            ("target", "r_fit - r_phase3"),
            ("quiet_selection", "Phase 3 P3.1 near_zero_runs and nearest_pre_runs"),
            ("split", "5 outer 20/5, 4 inner 15/5; repeated quiet runs intact"),
        ])
        if database.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Quiet-window trial SQLite integrity check failed.")


def main() -> None:
    """Input: frozen Phase 2/3 and Phase 4 V2 data. Output: Phase 5 V2 trial SQLite."""
    predictions, scores = evaluate(load_quiet_features())
    save_results(predictions, scores)
    actual = np.array([row["r_fit"] for row in predictions])
    baseline = np.array([row["r_phase3"] for row in predictions])
    predicted = np.array([row["r_pred"] for row in predictions])
    print(f"Phase 3 R MAE={np.mean(abs(actual-baseline)):.6f}; "
          f"quiet-window GPR MAE={np.mean(abs(actual-predicted)):.6f}")


if __name__ == "__main__":
    main()
