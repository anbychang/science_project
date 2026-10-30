"""Measure Phase4 GPR single-feature and drop-feature held-out contributions."""

import csv
import sys
from pathlib import Path

import numpy as np

TRIAL2_CODE = Path(__file__).resolve().parents[2] / "phase4-trial2/code"
sys.path.insert(0, str(TRIAL2_CODE))

from phases.phase4_shared.code.calc_phase4_feature_ablation import (
    BASELINE_SET_NAME,
    FULL_FEATURE_SET_NAME,
    contribution_deltas,
    feature_set_definitions,
    selected_feature_matrix,
)
from phases.phase4_shared.code.calc_phase4_trial4_gpr import (
    FEATURE_NAMES,
    GprSettings,
    fit_gpr,
    score,
)
from phases.phase4_shared.code.calc_phase4_trial4_groupcv import split_storm_folds
from prep_phase4_trial4_groupcv import load_anchor_rows


ROOT = Path("phases/phase4-trial2")
SUMMARY = ROOT / "data/analysis/phase4_feature_ablation_summary.csv"
FOLD_METRICS = ROOT / "data/analysis/phase4_feature_ablation_fold_metrics.csv"
CONTRIBUTIONS = ROOT / "data/analysis/phase4_feature_ablation_contributions.csv"
ABLATION_OPTIMIZER_RESTARTS = 0


def anchor_data(rows: list[dict]) -> dict:
    """Input: [{Trial1 anchor fields}]. Output: {features, residual, storm_ids}."""
    return {
        "features": np.array([[row[name] for name in FEATURE_NAMES] for row in rows]),
        "residual": np.array([row["residual_log_density"] for row in rows]),
        "storm_ids": np.array([row["storm_id"] for row in rows]),
    }


def evaluate_feature_set(data: dict, definition: dict) -> tuple[dict, list[dict]]:
    """Input: {anchor arrays}, {feature set}. Output: overall metric, [fold metrics]."""
    selected_names = definition["selected_feature_names"]
    features = selected_feature_matrix(data["features"], selected_names)
    residual = data["residual"]
    predictions = np.empty(len(residual))
    uncertainties = np.empty(len(residual))
    fold_rows = []
    for fold_index, (train_indices, test_indices) in enumerate(
        split_storm_folds(data["storm_ids"]), 1
    ):
        fitted = fit_gpr(
            features[train_indices],
            residual[train_indices],
            GprSettings(selected_names, ABLATION_OPTIMIZER_RESTARTS),
        )
        mean, std = fitted["model"].predict(
            fitted["scaler"].transform(features[test_indices]), return_std=True
        )
        predictions[test_indices] = mean
        uncertainties[test_indices] = std
        fold_rows.append({
            "analysis_kind": definition["analysis_kind"],
            "feature_set_name": definition["feature_set_name"],
            "target_feature_name": definition["target_feature_name"],
            "selected_feature_names": ",".join(selected_names),
            "fold_index": fold_index,
            "test_anchor_count": len(test_indices),
            "convergence_warning_count": fitted["warnings_count"],
            **score(residual[test_indices], mean, std),
        })
    overall = {
        "analysis_kind": definition["analysis_kind"],
        "feature_set_name": definition["feature_set_name"],
        "target_feature_name": definition["target_feature_name"],
        "selected_feature_names": ",".join(selected_names),
        "test_anchor_count": len(residual),
        "convergence_warning_count": sum(
            row["convergence_warning_count"] for row in fold_rows
        ),
        **score(residual, predictions, uncertainties),
    }
    return overall, fold_rows


def baseline_summary(data: dict) -> dict:
    """Input: {anchor residual}. Output: fixed Trial4 baseline metric row."""
    residual = data["residual"]
    baseline = score(residual, np.zeros(len(residual)), np.full(len(residual), np.nan))
    return {
        "analysis_kind": "baseline",
        "feature_set_name": BASELINE_SET_NAME,
        "target_feature_name": "",
        "selected_feature_names": "",
        "test_anchor_count": len(residual),
        "convergence_warning_count": 0,
        **baseline,
    }


def contribution_rows(summary_rows: list[dict]) -> list[dict]:
    """Input: [overall ablation metrics]. Output: [per-feature contribution metrics]."""
    by_name = {row["feature_set_name"]: row for row in summary_rows}
    baseline_rmse = by_name[BASELINE_SET_NAME]["gpr_rmse_log_density"]
    full_feature_rmse = by_name[FULL_FEATURE_SET_NAME]["gpr_rmse_log_density"]
    rows = []
    for feature_name in FEATURE_NAMES:
        single_feature_rmse = by_name[f"only_{feature_name}"]["gpr_rmse_log_density"]
        drop_feature_rmse = by_name[f"without_{feature_name}"]["gpr_rmse_log_density"]
        rows.append({
            "feature_name": feature_name,
            "trial4_rmse_log_density": baseline_rmse,
            "all_feature_rmse_log_density": full_feature_rmse,
            "single_feature_rmse_log_density": single_feature_rmse,
            "drop_feature_rmse_log_density": drop_feature_rmse,
            **contribution_deltas(
                baseline_rmse, full_feature_rmse, single_feature_rmse, drop_feature_rmse
            ),
        })
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    """Input: new path, [{field: value}]. Output: UTF-8 CSV."""
    with path.open("x", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """Input: read-only Trial1 anchors. Output: non-overwriting feature-ablation CSVs."""
    outputs = (SUMMARY, FOLD_METRICS, CONTRIBUTIONS)
    if any(path.exists() for path in outputs):
        raise FileExistsError("Phase4 feature ablation outputs already exist.")
    data = anchor_data(load_anchor_rows())
    summary_rows = [baseline_summary(data)]
    fold_rows = []
    definitions = feature_set_definitions()
    for definition in definitions:
        summary, folds = evaluate_feature_set(data, definition)
        summary_rows.append(summary)
        fold_rows.extend(folds)
    expected_summary_rows = len(definitions) + 1
    expected_fold_rows = len(definitions) * len(split_storm_folds(data["storm_ids"]))
    if len(summary_rows) != expected_summary_rows or len(fold_rows) != expected_fold_rows:
        raise ValueError("Phase4 feature ablation result is incomplete.")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    write_csv(SUMMARY, summary_rows)
    write_csv(FOLD_METRICS, fold_rows)
    write_csv(CONTRIBUTIONS, contribution_rows(summary_rows))
    print("Saved Phase4 single-feature and drop-feature GPR ablations")


if __name__ == "__main__":
    main()
