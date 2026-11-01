"""Compare pre-storm background and recovery features for event R prediction."""

import sqlite3
from contextlib import closing

import numpy as np

from prep_storm_r_feature_trials import evaluate, save_results
from prep_storm_r_gpr import ROOT, WEATHER, load_storm_rows


OUTPUT = ROOT / "data/sqlite/storm_r_context_trials_v3.sqlite"
ALGORITHM_VERSION = "storm_r_context_trials_v3"
HOUR_US = 60 * 60 * 1_000_000
FEATURE_SETS = {
    "f107a_pre": ("f107a_pre_sfu",),
    "sme_pre": ("sme_pre_nt",),
    "symh_pre": ("symh_pre_nt",),
    "f107a_sme_pre": ("f107a_pre_sfu", "sme_pre_nt"),
    "main_sme_recovery": ("sme_main_peak_nt", "symh_recovery_nt"),
    "symh_depth_recovery": ("min_symh_nt", "symh_recovery_nt"),
}


def load_context_features() -> list[dict]:
    """Input: Phase 4 V2 event R and Phase 2 minute weather. Output: 25 context records."""
    labels, _, _ = load_storm_rows()
    uri = f"file:{WEATHER.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        rows = []
        for label in labels:
            storm_id = label["storm_id"]
            values = database.execute("""
                SELECT avg(CASE WHEN f.source_time_us<e.t0_time_us-12*? THEN f.sme_nt END),
                       avg(CASE WHEN f.source_time_us<e.t0_time_us-12*? THEN f.symh_nt END),
                       avg(CASE WHEN f.source_time_us<e.t0_time_us THEN f.f107a_sfu END),
                       max(CASE WHEN f.source_time_us>=e.t0_time_us-12*?
                                     AND f.source_time_us<e.t0_time_us THEN f.sme_nt END),
                       min(f.symh_nt),
                       avg(CASE WHEN f.source_time_us>=e.t0_time_us+6*? THEN f.symh_nt END),
                       count(*)
                FROM storm_minute_feature_v5 AS f
                JOIN storm_event_t0_phase_v5 AS e ON e.storm_id=f.storm_id
                WHERE f.storm_id=? AND f.source_time_us>=e.t0_time_us-24*?
                  AND f.source_time_us<e.t0_time_us+24*?
            """, (HOUR_US, HOUR_US, HOUR_US, HOUR_US,
                  storm_id, HOUR_US, HOUR_US)).fetchone()
            sme_pre, symh_pre, f107a_pre, sme_main, symh_min, symh_late, count = values
            if count != 2880 or any(value is None for value in values[:6]):
                raise ValueError(f"Incomplete storm context: {storm_id}")
            rows.append({**label, "sme_pre_nt": sme_pre, "symh_pre_nt": symh_pre,
                         "f107a_pre_sfu": f107a_pre, "sme_main_peak_nt": sme_main,
                         "min_symh_nt": symh_min,
                         "symh_recovery_nt": symh_late - symh_min})
    return rows


def main() -> None:
    """Input: Phase 4 V2 and Phase 2 SQLite. Output: context-feature trial SQLite."""
    predictions, scores = evaluate(load_context_features(), FEATURE_SETS)
    save_results(predictions, scores, {"output": OUTPUT, "version": ALGORITHM_VERSION,
                                       "window": "t0 +/- 24 h; pre/main/recovery subwindows"})
    actual = np.log([row["r_fit"] for row in predictions])
    predicted = np.log([row["r_pred"] for row in predictions])
    baseline = np.log([row["r_train_mean"] for row in predictions])
    print(f"context GPR RMSE={np.sqrt(np.mean((actual-predicted)**2)):.6f}; "
          f"train mean={np.sqrt(np.mean((actual-baseline)**2)):.6f}")


if __name__ == "__main__":
    main()
