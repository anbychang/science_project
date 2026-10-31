"""Load one trusted local Trial9 model and predict an orbit correction."""

import sys
from pathlib import Path

import joblib

from prep_trial9_pooled_orbit_gpr import ROOT, VERSION
from prep_trial9_save_models import FEATURE_NAMES

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "phase5-trial8/code"))
from calc_trial8_four_feature_gpr import feature_vector  # noqa: E402


def load_fold_model(fold_index: int) -> dict:
    """Input: historical fold index 1..5. Output: fitted scaler, GPR, metadata."""
    if fold_index not in range(1, 6):
        raise ValueError("Trial9 fold index must be 1 through 5.")
    path = ROOT / "data/models" / f"trial9_fold_{fold_index}.joblib"
    bundle = joblib.load(path)
    if (bundle["algorithm_version"] != VERSION
            or bundle["fold_index"] != fold_index
            or tuple(bundle["feature_names"]) != FEATURE_NAMES):
        raise ValueError(f"Unexpected Trial9 model artifact: {path}")
    return bundle


def load_final_model() -> dict:
    """Input: saved all-25 model path. Output: fitted model for later new data."""
    path = ROOT / "data/models/trial9_all_25.joblib"
    bundle = joblib.load(path)
    if (bundle["algorithm_version"] != VERSION
            or bundle["role"] != "all_25_for_later_use"
            or tuple(bundle["feature_names"]) != FEATURE_NAMES):
        raise ValueError(f"Unexpected Trial9 all-storm artifact: {path}")
    return bundle


def predict_next_orbit(bundle: dict, current: dict, previous: dict) -> tuple[float, float]:
    """Input: fitted bundle, {current Trial4}, {previous L2/Trial4/error}. Output: (log mean, std)."""
    if bundle["algorithm_version"] != VERSION:
        raise ValueError("Trial9 model version differs.")
    features = feature_vector(current, previous)
    changes, stds = bundle["model"].predict(
        bundle["scaler"].transform([features]), return_std=True)
    return previous["residual_log_density"] + float(changes[0]), float(stds[0])
