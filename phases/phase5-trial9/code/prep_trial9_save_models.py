"""Save the five fitted Trial9 GPR models for reuse without training."""

import csv
import json
import math
import os
import tempfile
from pathlib import Path

import joblib
import numpy as np
import sklearn

from prep_trial9_pooled_orbit_gpr import (
    POINTS, ROOT, VERSION, build_pairs, fit_fold, load_events, load_folds,
)


MODELS = ROOT / "data/models"
MANIFEST = MODELS / "manifest.json"
FEATURE_NAMES = (
    "log_trial4_current_kg_m3",
    "log_trial4_previous_kg_m3",
    "log_l2_previous_kg_m3",
    "previous_log_residual",
)


def load_saved_predictions() -> dict[tuple[str, int], tuple[float, float]]:
    """Input: saved Trial9 prediction CSV. Output: {(storm, time_us): (mean, std)}."""
    with POINTS.open(encoding="utf-8-sig", newline="") as source:
        return {(row["storm_id"], int(row["time_us"])):
                (float(row["pooled_gpr_log_residual"]),
                 float(row["pooled_gpr_log_std"]))
                for row in csv.DictReader(source)}


def verify_predictions(bundle: dict, testing: list[dict], saved: dict) -> None:
    """Input: fitted model bundle, [held-out pairs], saved scores. Output: raises on mismatch."""
    features = np.asarray([pair["features"] for pair in testing])
    changes, stds = bundle["model"].predict(
        bundle["scaler"].transform(features), return_std=True)
    for pair, change, std in zip(testing, changes, stds, strict=True):
        expected_mean, expected_std = saved[(pair["storm_id"], pair["time_us"])]
        predicted_mean = pair["previous_log_residual"] + float(change)
        if (not math.isclose(predicted_mean, expected_mean, rel_tol=0, abs_tol=1e-10)
                or not math.isclose(float(std), expected_std, rel_tol=0, abs_tol=1e-10)):
            raise ValueError(f"Saved Trial9 prediction differs: {pair['storm_id']}:{pair['time_us']}")


def save_bundle(path: Path, bundle: dict) -> None:
    """Input: model path, fitted bundle. Output: atomically saved compressed joblib."""
    handle, name = tempfile.mkstemp(prefix="trial9_model_", suffix=".building", dir=path.parent)
    os.close(handle)
    temporary = Path(name)
    try:
        joblib.dump(bundle, temporary, compress=3)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    """Input: fixed anchors, folds, Trial9 CSV. Output: five models and manifest."""
    events, _ = load_events()
    pairs = build_pairs(events)
    folds = load_folds(set(events))
    saved = load_saved_predictions()
    paths = [MODELS / f"trial9_fold_{fold['fold_index']}.joblib" for fold in folds]
    if MANIFEST.exists() or any(path.exists() for path in paths):
        raise FileExistsError("Trial9 model artifacts already exist.")
    MODELS.mkdir(parents=True, exist_ok=True)
    records = []
    for fold, path in zip(folds, paths, strict=True):
        train_ids = set(fold["train_storm_ids"])
        test_ids = set(fold["test_storm_ids"])
        training = [pair for pair in pairs if pair["storm_id"] in train_ids]
        testing = [pair for pair in pairs if pair["storm_id"] in test_ids]
        scaler, model = fit_fold(training)
        bundle = {"algorithm_version": VERSION,
                  "fold_index": fold["fold_index"],
                  "feature_names": FEATURE_NAMES,
                  "train_storm_ids": sorted(train_ids),
                  "test_storm_ids": sorted(test_ids),
                  "scaler": scaler,
                  "model": model}
        verify_predictions(bundle, testing, saved)
        save_bundle(path, bundle)
        loaded = joblib.load(path)
        verify_predictions(loaded, testing, saved)
        records.append({"fold_index": fold["fold_index"],
                        "file": path.name,
                        "train_storm_count": len(train_ids),
                        "train_pair_count": len(training),
                        "test_storm_count": len(test_ids),
                        "test_pair_count": len(testing),
                        "kernel": str(model.kernel_),
                        "size_bytes": path.stat().st_size})
        print(f"Saved and reloaded fold {fold['fold_index']}: {path.name}", flush=True)
    manifest = {"algorithm_version": VERSION,
                "scikit_learn_version": sklearn.__version__,
                "joblib_version": joblib.__version__,
                "feature_names": FEATURE_NAMES,
                "source_predictions": str(POINTS),
                "folds": records}
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"Saved {len(records)} reusable GPR models")


if __name__ == "__main__":
    main()
