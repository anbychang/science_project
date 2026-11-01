"""Compare ap timing and persistence features for event R prediction."""

import sqlite3
from contextlib import closing

import numpy as np

from prep_storm_r_feature_trials import evaluate, save_results
from prep_storm_r_gpr import ROOT, WEATHER, load_storm_rows


OUTPUT = ROOT / "data/sqlite/storm_r_ap_timing_trials_v5.sqlite"
ALGORITHM_VERSION = "storm_r_ap_timing_trials_v5"
HOUR_US = 60 * 60 * 1_000_000
FEATURE_SETS = {
    "ap_early": ("ap_early",),
    "ap_central": ("ap_central",),
    "ap_active_hours": ("ap_active_hours",),
    "ap_early_central": ("ap_early", "ap_central"),
    "ap_early_f107a": ("ap_early", "f107a_sfu"),
    "ap_central_symh": ("ap_central", "min_symh_nt"),
    "ap_active_sme": ("ap_active_hours", "peak_sme_nt"),
    "ap_recovery": ("ap_central", "ap_late"),
}


def load_timing_features() -> list[dict]:
    """Input: Phase 4 V2 labels and Phase 2 weather. Output: 25 ap timing records."""
    labels, _, _ = load_storm_rows()
    uri = f"file:{WEATHER.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        rows = []
        for label in labels:
            storm_id = label["storm_id"]
            values = database.execute("""
                SELECT avg(CASE WHEN f.source_time_us<e.t0_time_us-24*? THEN f.ap_step END),
                       max(CASE WHEN f.source_time_us>=e.t0_time_us-6*?
                                     AND f.source_time_us<e.t0_time_us+6*?
                                THEN f.ap_step END),
                       sum(CASE WHEN f.source_time_us>=e.t0_time_us
                                      AND f.ap_step>=50 THEN 1 ELSE 0 END)/60.0,
                       avg(CASE WHEN f.source_time_us>=e.t0_time_us+6*?
                                THEN f.ap_step END),
                       avg(f.f107a_sfu),min(f.symh_nt),max(f.sme_nt),
                       count(*),count(f.ap_step)
                FROM storm_minute_feature_v5 AS f
                JOIN storm_event_t0_phase_v5 AS e ON e.storm_id=f.storm_id
                WHERE f.storm_id=? AND f.source_time_us>=e.t0_time_us-48*?
                  AND f.source_time_us<e.t0_time_us+24*?
            """, (HOUR_US, HOUR_US, HOUR_US, HOUR_US,
                  storm_id, HOUR_US, HOUR_US)).fetchone()
            early, central, active, late, f107a, symh_min, sme_peak, count, ap_count = values
            if count != 4320 or ap_count != count:
                raise ValueError(f"Incomplete 72-hour ap window: {storm_id}")
            rows.append({**label, "ap_early": early, "ap_central": central,
                         "ap_active_hours": active, "ap_late": late,
                         "f107a_sfu": f107a, "min_symh_nt": symh_min,
                         "peak_sme_nt": sme_peak})
    return rows


def main() -> None:
    """Input: Phase 4 V2 and Phase 2 SQLite. Output: ap timing trial SQLite."""
    predictions, scores = evaluate(load_timing_features(), FEATURE_SETS)
    save_results(predictions, scores, {"output": OUTPUT, "version": ALGORITHM_VERSION,
                                       "window": "t0 -48 h to +24 h; ap 3-hour steps"})
    actual = np.log([row["r_fit"] for row in predictions])
    predicted = np.log([row["r_pred"] for row in predictions])
    baseline = np.log([row["r_train_mean"] for row in predictions])
    print(f"ap timing GPR RMSE={np.sqrt(np.mean((actual-predicted)**2)):.6f}; "
          f"train mean={np.sqrt(np.mean((actual-baseline)**2)):.6f}")


if __name__ == "__main__":
    main()
