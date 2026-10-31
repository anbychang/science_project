"""Save one all-25-storm GPR for later use after the 20/5 evaluation."""

import json

import joblib
import numpy as np
import sklearn

from prep_trial9_pooled_orbit_gpr import VERSION, build_pairs, fit_fold, load_events
from prep_trial9_save_models import FEATURE_NAMES, MODELS, save_bundle


FINAL_MODEL = MODELS / "trial9_all_25.joblib"
FINAL_MANIFEST = MODELS / "final_manifest.json"


def main() -> None:
    """Input: 25 fixed storms. Output: reusable all-storm model and manifest."""
    if FINAL_MODEL.exists() or FINAL_MANIFEST.exists():
        raise FileExistsError("Trial9 all-storm model already exists.")
    events, _ = load_events()
    pairs = build_pairs(events)
    if len(pairs) != 2265:
        raise ValueError("Expected 2,265 adjacent training pairs.")
    scaler, model = fit_fold(pairs)
    bundle = {"algorithm_version": VERSION,
              "role": "all_25_for_later_use",
              "feature_names": FEATURE_NAMES,
              "train_storm_ids": sorted(events),
              "scaler": scaler,
              "model": model}
    sample = np.asarray([pair["features"] for pair in pairs[:10]])
    original = model.predict(scaler.transform(sample), return_std=True)
    MODELS.mkdir(parents=True, exist_ok=True)
    save_bundle(FINAL_MODEL, bundle)
    loaded = joblib.load(FINAL_MODEL)
    restored = loaded["model"].predict(loaded["scaler"].transform(sample),
                                       return_std=True)
    if not (np.array_equal(original[0], restored[0])
            and np.array_equal(original[1], restored[1])):
        raise ValueError("Reloaded all-storm model changed its predictions.")
    manifest = {"algorithm_version": VERSION,
                "role": "future use only; not a held-out score for the 25 training storms",
                "train_storm_count": len(events),
                "train_pair_count": len(pairs),
                "feature_names": FEATURE_NAMES,
                "kernel": str(model.kernel_),
                "scikit_learn_version": sklearn.__version__,
                "joblib_version": joblib.__version__,
                "file": FINAL_MODEL.name,
                "size_bytes": FINAL_MODEL.stat().st_size}
    FINAL_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(f"Saved and reloaded all-25-storm model: {FINAL_MODEL.name}")


if __name__ == "__main__":
    main()
