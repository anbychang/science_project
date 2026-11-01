"""Test ap and AE storm features against Phase 4 V2 event R labels."""

import sqlite3
from contextlib import closing

import numpy as np

from prep_storm_r_feature_trials import evaluate, save_results
from prep_storm_r_gpr import ROOT, WEATHER, load_storm_rows


OUTPUT = ROOT / "data/sqlite/storm_r_ap_trials_v4.sqlite"
ALGORITHM_VERSION = "storm_r_ap_trials_v4"
HOUR_US = 60 * 60 * 1_000_000
FEATURE_SETS = {
    "ap_peak": ("ap_peak",),
    "ap_mean": ("ap_mean",),
    "ap_pre": ("ap_pre",),
    "ap_change": ("ap_change",),
    "ae_peak": ("ae_peak_nt",),
    "ae_mean": ("ae_mean_nt",),
    "ap_ae": ("ap_peak", "ae_peak_nt"),
    "ap_f107a": ("ap_mean", "f107a_sfu"),
    "ap_symh": ("ap_peak", "min_symh_nt"),
    "ap_sme": ("ap_mean", "peak_sme_nt"),
}


def load_ap_features() -> list[dict]:
    """Input: Phase 4 V2 event labels and Phase 2 weather. Output: 25 ap/AE records."""
    labels, _, _ = load_storm_rows()
    uri = f"file:{WEATHER.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        rows = []
        for label in labels:
            storm_id = label["storm_id"]
            values = database.execute("""
                SELECT max(CASE WHEN f.source_time_us>=e.t0_time_us THEN f.ap_step END),
                       avg(CASE WHEN f.source_time_us>=e.t0_time_us THEN f.ap_step END),
                       avg(CASE WHEN f.source_time_us<e.t0_time_us THEN f.ap_step END),
                       max(CASE WHEN f.source_time_us>=e.t0_time_us THEN g.ae_nt END),
                       avg(CASE WHEN f.source_time_us>=e.t0_time_us THEN g.ae_nt END),
                       avg(f.f107a_sfu),min(f.symh_nt),max(f.sme_nt),
                       count(*),count(g.ae_nt),count(f.ap_step)
                FROM storm_minute_feature_v5 AS f
                JOIN storm_event_t0_phase_v5 AS e ON e.storm_id=f.storm_id
                JOIN geomag_1min_v2 AS g ON g.time_us=f.source_time_us
                WHERE f.storm_id=? AND f.source_time_us>=e.t0_time_us-24*?
                  AND f.source_time_us<e.t0_time_us+24*?
            """, (storm_id, HOUR_US, HOUR_US)).fetchone()
            ap_peak, ap_mean, ap_pre, ae_peak, ae_mean, f107a, symh_min, sme_peak, count, ae_count, ap_count = values
            if count != 2880 or ae_count != count or ap_count != count:
                raise ValueError(f"Incomplete ap/AE window: {storm_id}")
            rows.append({**label, "ap_peak": ap_peak, "ap_mean": ap_mean,
                         "ap_pre": ap_pre, "ap_change": ap_mean - ap_pre,
                         "ae_peak_nt": ae_peak, "ae_mean_nt": ae_mean,
                         "f107a_sfu": f107a, "min_symh_nt": symh_min,
                         "peak_sme_nt": sme_peak})
    return rows


def main() -> None:
    """Input: Phase 4 V2 and Phase 2 SQLite. Output: ap-feature trial SQLite."""
    predictions, scores = evaluate(load_ap_features(), FEATURE_SETS)
    save_results(predictions, scores, {"output": OUTPUT, "version": ALGORITHM_VERSION,
                                       "window": "t0 +/- 24 h; ap is a 3-hour step series"})
    actual = np.log([row["r_fit"] for row in predictions])
    predicted = np.log([row["r_pred"] for row in predictions])
    baseline = np.log([row["r_train_mean"] for row in predictions])
    print(f"ap/AE GPR RMSE={np.sqrt(np.mean((actual-predicted)**2)):.6f}; "
          f"train mean={np.sqrt(np.mean((actual-baseline)**2)):.6f}")


if __name__ == "__main__":
    main()
