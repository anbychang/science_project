"""Check altitude ARD lower bounds on held-out storms."""

import os
import sqlite3
import sys
import tempfile
import warnings
from contextlib import closing
from pathlib import Path

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from phases.phase5.code.calc_phase5_trial4_gpr import FEATURE_NAMES
from phases.phase5.code.calc_phase5_trial4_groupcv import split_storm_folds
from prep_phase5_trial4_groupcv import feature_matrix, load_anchor_rows


RAISED_OUTPUT = Path("phases/phase5-trial2/data/sqlite/phase5_altitude_bound_v1.sqlite")
LOWERED_OUTPUT = Path("phases/phase5-trial2/data/sqlite/phase5_altitude_lower_bound_v1.sqlite")
RAISED_MINIMUMS = (0.01, 0.1, 0.3)
LOWERED_MINIMUMS = (0.001, 0.0001)
EXPECTED_ANCHORS = 2295


def fit_bound(features: np.ndarray, residual: np.ndarray, minimum: float) -> tuple:
    """Input: [train anchors x five features], [log residual], altitude bound. Output: scaler, model, warning count."""
    scaler = StandardScaler().fit(features)
    bounds = np.tile((0.01, 1000.0), (features.shape[1], 1))
    bounds[FEATURE_NAMES.index("altitude_phase_m"), 0] = minimum
    kernel = (ConstantKernel(1.0, (1e-3, 1e3))
              * RBF(np.ones(features.shape[1]), bounds)
              + WhiteKernel(0.1, (1e-5, 1.0)))
    model = GaussianProcessRegressor(
        kernel=kernel, alpha=1e-10, normalize_y=False,
        n_restarts_optimizer=0, random_state=20261030,
    )
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        model.fit(scaler.transform(features), residual)
    warning_count = sum(isinstance(item.message, ConvergenceWarning) for item in emitted)
    return scaler, model, warning_count


def evaluate(minimums: tuple[float, ...], version: str) -> tuple:
    """Input: altitude bounds, version, fixed Trial1/2 data. Output: prediction, fold, summary rows."""
    rows = load_anchor_rows()
    features = feature_matrix(rows)
    residual = np.array([row["residual_log_density"] for row in rows])
    storm_ids = np.array([row["storm_id"] for row in rows])
    folds = split_storm_folds(storm_ids)
    predictions = []
    fits = []
    summaries = []
    baseline_rmse = float(np.sqrt(np.mean(residual ** 2)))
    for minimum in minimums:
        held_out = np.full(len(rows), np.nan)
        for fold_index, (train, test) in enumerate(folds, 1):
            scaler, model, warning_count = fit_bound(
                features[train], residual[train], minimum,
            )
            mean = model.predict(scaler.transform(features[test]))
            held_out[test] = mean
            fold_rmse = float(np.sqrt(np.mean((residual[test] - mean) ** 2)))
            altitude_index = FEATURE_NAMES.index("altitude_phase_m")
            fits.append((minimum, fold_index,
                         float(model.kernel_.k1.k2.length_scale[altitude_index]),
                         fold_rmse, warning_count, version))
            predictions.extend((minimum, str(storm_ids[index]), rows[int(index)]["time_us"],
                                fold_index, float(residual[index]), float(value), version)
                               for index, value in zip(test, mean, strict=True))
            print(f"altitude bound {minimum:g}, fold {fold_index}: RMSE {fold_rmse:.6f}",
                  flush=True)
        if not np.isfinite(held_out).all():
            raise ValueError("Every anchor must receive one held-out prediction.")
        rmse = float(np.sqrt(np.mean((residual - held_out) ** 2)))
        summaries.append((minimum, len(rows), baseline_rmse, rmse, version))
        print(f"altitude bound {minimum:g}: combined RMSE {rmse:.6f}", flush=True)
    if 0.01 in minimums:
        baseline = next(row[3] for row in summaries if row[0] == 0.01)
        if abs(baseline - 0.1102811537008736) > 1e-6:
            raise ValueError("The 0.01 baseline did not reproduce the saved ablation result.")
    return predictions, fits, summaries


def write_sqlite(output: Path, result: tuple) -> None:
    """Input: destination, evaluated rows. Output: atomic, non-overwriting SQLite result."""
    predictions, fits, summaries = result
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(suffix=".building", dir=output.parent)
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with closing(sqlite3.connect(temporary)) as database:
            database.executescript("""
                CREATE TABLE prediction (
                    altitude_min_length_scale REAL NOT NULL,
                    storm_id TEXT NOT NULL, time_us INTEGER NOT NULL,
                    fold_index INTEGER NOT NULL, actual_log_residual REAL NOT NULL,
                    predicted_log_residual REAL NOT NULL, algorithm_version TEXT NOT NULL,
                    PRIMARY KEY (altitude_min_length_scale, storm_id, time_us)
                );
                CREATE TABLE fold_fit (
                    altitude_min_length_scale REAL NOT NULL, fold_index INTEGER NOT NULL,
                    fitted_altitude_length_scale REAL NOT NULL,
                    test_log_rmse REAL NOT NULL, convergence_warning_count INTEGER NOT NULL,
                    algorithm_version TEXT NOT NULL,
                    PRIMARY KEY (altitude_min_length_scale, fold_index)
                );
                CREATE TABLE summary (
                    altitude_min_length_scale REAL PRIMARY KEY, test_anchor_count INTEGER NOT NULL,
                    phase4_log_rmse REAL NOT NULL, gpr_log_rmse REAL NOT NULL,
                    algorithm_version TEXT NOT NULL
                );
            """)
            database.executemany("INSERT INTO prediction VALUES (?,?,?,?,?,?,?)", predictions)
            database.executemany("INSERT INTO fold_fit VALUES (?,?,?,?,?,?)", fits)
            database.executemany("INSERT INTO summary VALUES (?,?,?,?,?)", summaries)
            if (database.execute("SELECT count(*) FROM prediction").fetchone()[0]
                    != EXPECTED_ANCHORS * len(summaries)
                    or database.execute("PRAGMA integrity_check").fetchone()[0] != "ok"):
                raise ValueError("Altitude bound SQLite audit failed.")
            database.commit()
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    """Input: optional 'lower', fixed Trial1/2 data. Output: one bound-check SQLite."""
    if len(sys.argv) > 2:
        raise SystemExit("Usage: prep_phase5_altitude_bound.py [lower]")
    mode = sys.argv[1] if len(sys.argv) == 2 else "raised"
    if mode == "raised":
        minimums, output = RAISED_MINIMUMS, RAISED_OUTPUT
        version = "phase5_trial2_altitude_bound_v1"
    elif mode == "lower":
        minimums, output = LOWERED_MINIMUMS, LOWERED_OUTPUT
        version = "phase5_trial2_altitude_lower_bound_v1"
    else:
        raise SystemExit("Usage: prep_phase5_altitude_bound.py [lower]")
    result = evaluate(minimums, version)
    write_sqlite(output, result)
    print(f"Saved {output}")


if __name__ == "__main__":
    main()
