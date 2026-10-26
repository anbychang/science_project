"""Check provisional Phase 3 tau and gain by holding out one storm at a time."""

import csv
from pathlib import Path

import numpy as np

from satellite_orbit.phase3.prep_exploratory_fit import (
    load_fit_arrays, load_r_candidates,
)


REPORT = Path("output/report/phase3_baseline_loo_exploratory.csv")


def fold_rows(data: dict) -> list[dict]:
    """Input: {z, h, event_index, identifiers}. Output: 25 holdout fit rows."""
    z = data["z"]
    h = data["h"]
    event_index = data["event_index"]
    total_cross = h.T @ z
    total_h2 = np.sum(h * h, axis=0)
    total_z2 = float(z @ z)
    rows = []
    for index, storm_id in enumerate(data["identifiers"]):
        test = event_index == index
        test_h = h[test]
        test_z = z[test]
        test_cross = test_h.T @ test_z
        test_h2 = np.sum(test_h * test_h, axis=0)
        test_z2 = float(test_z @ test_z)
        train_cross = total_cross - test_cross
        train_h2 = total_h2 - test_h2
        gain = train_cross / train_h2
        train_count = len(z) - len(test_z)
        train_sse = total_z2 - test_z2 - train_cross * gain
        train_rmse = np.sqrt(np.maximum(train_sse, 0) / train_count)
        best = int(np.argmin(train_rmse))
        test_sse = (test_z2 - 2 * gain[best] * test_cross[best]
                    + gain[best] ** 2 * test_h2[best])
        rows.append({
            "held_out_storm_id": storm_id,
            "train_storms": len(data["identifiers"]) - 1,
            "train_minutes": train_count,
            "test_minutes": len(test_z),
            "selected_tau_hours": best / 4,
            "gain_per_nt": float(gain[best]),
            "train_rmse_log_density": float(train_rmse[best]),
            "test_rmse_log_density": float(np.sqrt(max(test_sse, 0) / len(test_z))),
            "status": "provisional_R_exploratory",
        })
    return rows


def main() -> None:
    """Input: provisional R and Phase 3 aligned tables. Output: LOO CSV."""
    if REPORT.exists():
        raise FileExistsError(REPORT)
    z, h, event_index, identifiers = load_fit_arrays(load_r_candidates())
    rows = fold_rows({"z": z, "h": h, "event_index": event_index,
                      "identifiers": identifiers})
    with REPORT.open("x", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} provisional leave-one-storm-out folds")


if __name__ == "__main__":
    main()
