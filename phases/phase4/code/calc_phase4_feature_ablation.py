"""Define reproducible single-feature and drop-feature GPR ablations."""

import numpy as np

from phases.phase4.code.calc_phase4_trial4_gpr import FEATURE_NAMES


FULL_FEATURE_SET_NAME = "all_five_features"
BASELINE_SET_NAME = "trial4_baseline"


def feature_set_definitions() -> list[dict]:
    """Input: fixed five Trial1 features. Output: [{ablation definition}]."""
    definitions = [{
        "analysis_kind": "all_features",
        "feature_set_name": FULL_FEATURE_SET_NAME,
        "selected_feature_names": FEATURE_NAMES,
        "target_feature_name": "",
    }]
    for feature_name in FEATURE_NAMES:
        definitions.append({
            "analysis_kind": "single_feature",
            "feature_set_name": f"only_{feature_name}",
            "selected_feature_names": (feature_name,),
            "target_feature_name": feature_name,
        })
    for feature_name in FEATURE_NAMES:
        definitions.append({
            "analysis_kind": "drop_feature",
            "feature_set_name": f"without_{feature_name}",
            "selected_feature_names": tuple(
                name for name in FEATURE_NAMES if name != feature_name
            ),
            "target_feature_name": feature_name,
        })
    return definitions


def selected_feature_matrix(
    full_features: np.ndarray, selected_feature_names: tuple[str, ...]
) -> np.ndarray:
    """Input: [anchors x five features], selected names. Output: [anchors x selected features]."""
    if full_features.ndim != 2 or full_features.shape[1] != len(FEATURE_NAMES):
        raise ValueError("Feature ablation requires the five Trial1 feature columns.")
    if not selected_feature_names or len(set(selected_feature_names)) != len(selected_feature_names):
        raise ValueError("Selected feature names must be nonempty and unique.")
    indexes = []
    for feature_name in selected_feature_names:
        if feature_name not in FEATURE_NAMES:
            raise ValueError(f"Unknown Phase4 feature: {feature_name}")
        indexes.append(FEATURE_NAMES.index(feature_name))
    return full_features[:, indexes]


def contribution_deltas(
    baseline_rmse: float, full_feature_rmse: float, single_feature_rmse: float,
    drop_feature_rmse: float,
) -> dict:
    """Input: baseline, full, single, drop RMSE. Output: signed contribution deltas."""
    return {
        "single_feature_delta_vs_trial4": single_feature_rmse - baseline_rmse,
        "drop_feature_delta_vs_all_features": drop_feature_rmse - full_feature_rmse,
    }
