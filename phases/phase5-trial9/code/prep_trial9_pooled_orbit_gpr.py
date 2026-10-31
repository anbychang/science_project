"""Test a shared next-orbit GPR with five existing 20/5 storm folds."""

import csv
import json
import math
import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "phase5-trial8/code"))
from calc_trial8_four_feature_gpr import feature_vector  # noqa: E402
from prep_trial8_next_orbit_gpr import HOUR_US, load_events, write_csv  # noqa: E402


ROOT = Path("phases/phase5-trial9")
TRIAL8_POINTS = Path("phases/phase5-trial8/data/analysis/trial8_four_feature_predictions.csv")
FOLDS = Path("phases/phase5-trial2/data/analysis/phase4_trial4_groupcv20_5_folds.json")
POINTS = ROOT / "data/analysis/trial9_pooled_predictions.csv"
METRICS = ROOT / "data/analysis/trial9_pooled_event_metrics.csv"
FOLD_METRICS = ROOT / "data/analysis/trial9_pooled_fold_metrics.csv"
FIGURES = ROOT / "figures/pooled_25storm"
OVERVIEW = ROOT / "figures/trial9_pooled_rmse.png"
VERSION = "phase4_trial9_groupcv20_5_orbit_gpr_v1"


def build_pairs(events: dict[str, list[dict]]) -> list[dict]:
    """Input: {storm: [orbit rows]}. Output: [within-storm adjacent orbit pairs]."""
    pairs = []
    for storm_id, rows in events.items():
        for previous, current in zip(rows, rows[1:]):
            previous_grid = round(previous["u_rel_rad"] / (2 * math.pi))
            current_grid = round(current["u_rel_rad"] / (2 * math.pi))
            if current_grid != previous_grid + 1:
                continue
            pairs.append({"storm_id": storm_id,
                          "time_us": current["time_us"],
                          "previous_time_us": previous["time_us"],
                          "rho_l2_phase_kg_m3": current["rho_l2_phase_kg_m3"],
                          "rho_trial4_phase_kg_m3": current["rho_trial4_phase_kg_m3"],
                          "previous_trial4_density_kg_m3":
                              previous["rho_trial4_phase_kg_m3"],
                          "previous_l2_density_kg_m3":
                              previous["rho_l2_phase_kg_m3"],
                          "residual_log_density": current["residual_log_density"],
                          "previous_log_residual": previous["residual_log_density"],
                          "features": feature_vector(current, previous),
                          "change": current["residual_log_density"]
                                    - previous["residual_log_density"]})
    return pairs


def load_folds(storm_ids: set[str]) -> list[dict]:
    """Input: {25 storm IDs}. Output: [five verified historical 20/5 folds]."""
    folds = json.loads(FOLDS.read_text(encoding="utf-8"))
    tested = []
    for fold in folds:
        training = set(fold["train_storm_ids"])
        testing = set(fold["test_storm_ids"])
        if (len(training) != 20 or len(testing) != 5 or training & testing
                or training | testing != storm_ids):
            raise ValueError(f"Invalid 20/5 storm split: {fold['fold_index']}")
        tested.extend(testing)
    if len(folds) != 5 or len(tested) != 25 or set(tested) != storm_ids:
        raise ValueError("Historical folds do not test every storm once.")
    return folds


def fit_fold(training: list[dict]) -> tuple[StandardScaler, GaussianProcessRegressor]:
    """Input: [20-storm pairs]. Output: fitted feature scaler and GPR."""
    train_features = np.asarray([pair["features"] for pair in training])
    train_change = np.asarray([pair["change"] for pair in training])
    if not np.isfinite(train_features).all() or not np.isfinite(train_change).all():
        raise ValueError("GPR training inputs must be finite.")
    scaler = StandardScaler().fit(train_features)
    kernel = (
        ConstantKernel(1.0, (1e-2, 1e2))
        * RBF(np.ones(4), (1e-1, 1e1))
        + WhiteKernel(0.1, (1e-3, 1.0))
    )
    model = GaussianProcessRegressor(
        kernel=kernel, alpha=1e-8, normalize_y=True, n_restarts_optimizer=0
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        model.fit(scaler.transform(train_features), train_change)
    return scaler, model


def predict_fold(training: list[dict], testing: list[dict]) -> tuple[np.ndarray, np.ndarray, str]:
    """Input: [20-storm pairs], [5-storm pairs]. Output: (log means, stds, kernel)."""
    test_features = np.asarray([pair["features"] for pair in testing])
    if not np.isfinite(test_features).all():
        raise ValueError("GPR test inputs must be finite.")
    scaler, model = fit_fold(training)
    changes, uncertainty = model.predict(scaler.transform(test_features), return_std=True)
    previous = np.asarray([pair["previous_log_residual"] for pair in testing])
    return previous + changes, uncertainty, str(model.kernel_)


def load_trial8() -> dict[tuple[str, int], float]:
    """Input: saved same-storm Trial8 CSV. Output: {(storm, time_us): log estimate}."""
    with TRIAL8_POINTS.open(encoding="utf-8-sig", newline="") as source:
        return {(row["storm_id"], int(row["time_us"])):
                float(row["gp_log_residual_mean"]) for row in csv.DictReader(source)}


def score(rows: list[dict], storm_id: str) -> dict:
    """Input: [matched orbit prediction rows], storm ID. Output: same-position RMSEs."""
    actual = np.asarray([row["residual_log_density"] for row in rows])
    previous = np.asarray([row["previous_log_residual"] for row in rows])
    same_storm = np.asarray([row["same_storm_gpr_log_residual"] for row in rows])
    pooled = np.asarray([row["pooled_gpr_log_residual"] for row in rows])
    return {"storm_id": storm_id, "matched_orbit_count": len(rows),
            "trial4_log_rmse": float(np.sqrt(np.mean(actual ** 2))),
            "previous_orbit_log_rmse": float(np.sqrt(np.mean((actual - previous) ** 2))),
            "same_storm_gpr_log_rmse":
                float(np.sqrt(np.mean((actual - same_storm) ** 2))),
            "pooled_gpr_log_rmse": float(np.sqrt(np.mean((actual - pooled) ** 2))),
            "algorithm_version": VERSION}


def draw_event(rows: list[dict], storm_id: str, t0_us: int) -> None:
    """Input: [matched predictions], storm ID, event time. Output: signed-error PNG."""
    hours = [(row["time_us"] - t0_us) / HOUR_US for row in rows]
    actual = np.asarray([row["residual_log_density"] for row in rows])
    curves = (
        (np.zeros(len(rows)), "Trial4 D-model", "#d97706"),
        (np.asarray([row["previous_log_residual"] for row in rows]),
         "Previous orbit", "#2563eb"),
        (np.asarray([row["same_storm_gpr_log_residual"] for row in rows]),
         "Same-storm GPR", "#6b7280"),
        (np.asarray([row["pooled_gpr_log_residual"] for row in rows]),
         "Other-storm GPR", "#dc2626"),
    )
    figure, axis = plt.subplots(figsize=(12, 4.5), layout="constrained")
    for estimate, label, color in curves:
        axis.plot(hours, 100 * np.expm1(estimate - actual),
                  label=label, color=color, linewidth=1)
    axis.axhline(0, color="#111827", linewidth=0.8)
    axis.axvline(0, color="#6b7280", linestyle="--", linewidth=0.9)
    axis.set_title(f"{storm_id}: shared next-orbit rule from other storms")
    axis.set_xlabel(r"Hours from event time $t_0$")
    axis.set_ylabel("Estimated density / L2 - 1 (%)")
    axis.grid(alpha=0.2)
    axis.legend(frameon=False, ncol=4)
    figure.savefig(FIGURES / f"{storm_id.lower()}_pooled_error.png", dpi=160)
    plt.close(figure)


def draw_overview(rows: list[dict]) -> None:
    """Input: [25 matched event metrics]. Output: four-method RMSE PNG."""
    positions = np.arange(len(rows))
    figure, axis = plt.subplots(figsize=(10, 11), layout="constrained")
    for offset, field, label, color in (
        (-0.27, "trial4_log_rmse", "Trial4 D-model", "#d97706"),
        (-0.09, "previous_orbit_log_rmse", "Previous orbit", "#2563eb"),
        (0.09, "same_storm_gpr_log_rmse", "Same-storm GPR", "#6b7280"),
        (0.27, "pooled_gpr_log_rmse", "Other-storm GPR", "#dc2626"),
    ):
        axis.barh(positions + offset, [row[field] for row in rows],
                  height=0.17, label=label, color=color)
    axis.set_yticks(positions, [row["storm_id"] for row in rows])
    axis.invert_yaxis()
    axis.set_xlabel("Log-density RMSE on the same orbit anchors")
    axis.set_title("25 held-out storms: shared GPR versus same-storm correction")
    axis.legend(frameon=False)
    axis.grid(axis="x", alpha=0.2)
    figure.savefig(OVERVIEW, dpi=160)
    plt.close(figure)


def main() -> None:
    """Input: fixed anchors, 20/5 folds, Trial8 CSV. Output: Trial9 CSVs and PNGs."""
    if any(path.exists() for path in (POINTS, METRICS, FOLD_METRICS, OVERVIEW)):
        raise FileExistsError("Trial9 result already exists.")
    events, event_times = load_events()
    pairs = build_pairs(events)
    if len(pairs) != 2265:
        raise ValueError(f"Expected 2,265 adjacent pairs, found {len(pairs)}.")
    trial8 = load_trial8()
    folds = load_folds(set(events))
    predictions = []
    for fold in folds:
        training_ids = set(fold["train_storm_ids"])
        testing_ids = set(fold["test_storm_ids"])
        training = [pair for pair in pairs if pair["storm_id"] in training_ids]
        testing = [pair for pair in pairs if pair["storm_id"] in testing_ids]
        means, stds, kernel = predict_fold(training, testing)
        for pair, mean, std in zip(testing, means, stds, strict=True):
            key = (pair["storm_id"], pair["time_us"])
            row = {field: value for field, value in pair.items()
                   if field not in ("features", "change")}
            row["pooled_gpr_log_residual"] = float(mean)
            row["pooled_gpr_log_std"] = float(std)
            row["same_storm_gpr_log_residual"] = trial8.get(key)
            row["rho_pooled_gpr_kg_m3"] = (
                pair["rho_trial4_phase_kg_m3"] * math.exp(float(mean)))
            row["fold_index"] = fold["fold_index"]
            row["training_storm_count"] = len(training_ids)
            row["training_pair_count"] = len(training)
            row["fitted_kernel"] = kernel
            row["algorithm_version"] = VERSION
            predictions.append(row)
        print(f"Fold {fold['fold_index']}: train 20 storms/{len(training)} pairs, "
              f"test 5 storms/{len(testing)} pairs", flush=True)
    matched_all = [row for row in predictions
                   if row["same_storm_gpr_log_residual"] is not None]
    if len(predictions) != 2265 or len(matched_all) != len(trial8):
        raise ValueError("Trial9 and Trial8 scoring keys differ.")
    metrics = [score([row for row in matched_all if row["storm_id"] == storm_id],
                     storm_id) for storm_id in events]
    fold_metrics = [score([row for row in matched_all
                           if row["fold_index"] == fold["fold_index"]],
                          f"fold_{fold['fold_index']}") for fold in folds]
    overall = score(matched_all, "all_matched_orbits")
    POINTS.parent.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    write_csv(POINTS, predictions)
    write_csv(METRICS, [*metrics, overall])
    write_csv(FOLD_METRICS, fold_metrics)
    for storm_id in events:
        draw_event([row for row in matched_all if row["storm_id"] == storm_id],
                   storm_id, event_times[storm_id])
    draw_overview(metrics)
    print(overall)


if __name__ == "__main__":
    main()
