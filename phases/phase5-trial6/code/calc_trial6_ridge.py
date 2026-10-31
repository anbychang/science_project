"""Evaluate same-storm post-event residual filling on whole-orbit anchors."""

import csv
import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler


ROOT = Path("phases/phase5-trial6")
FEATURES = ROOT / "data/sqlite/swarm_a_trial6_day_fraction.sqlite"
PREDICTIONS = ROOT / "data/analysis/trial6_block_predictions.csv"
BLOCK_METRICS = ROOT / "data/analysis/trial6_block_metrics.csv"
EVENT_METRICS = ROOT / "data/analysis/trial6_event_metrics.csv"
BLOCK_HOURS = 6.0
STEP_HOURS = 12.0
KNOT_HOURS = 12.0
RIDGE_ALPHA = 1.0
METHODS = ("trial4", "interpolation", "ridge_time", "ridge_time_day")


def load_rows() -> dict[str, list[dict]]:
    """Input: Trial6 feature SQLite. Output: {storm_id: [ordered anchor records]}."""
    connection = sqlite3.connect(f"file:{FEATURES.resolve().as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    with closing(connection) as database:
        source = database.execute("""
            SELECT storm_id,time_us,elapsed_hours,day_fraction,
                   support_start_us,support_end_us,residual_log_density
            FROM trial6_anchor_feature ORDER BY storm_id,time_us
        """).fetchall()
    grouped: dict[str, list[dict]] = {}
    for row in source:
        grouped.setdefault(row["storm_id"], []).append(dict(row))
    if len(grouped) != 25 or sum(map(len, grouped.values())) != 2295:
        raise ValueError("Trial6 anchor count differs from frozen 25-storm source.")
    return grouped


def time_features(elapsed_hours: np.ndarray) -> np.ndarray:
    """Input: [elapsed hours]. Output: [linear and fixed 12-hour hinge columns]."""
    knots = np.arange(KNOT_HOURS, elapsed_hours[-1], KNOT_HOURS)
    return np.column_stack((
        elapsed_hours / KNOT_HOURS,
        np.maximum(0, (elapsed_hours[:, None] - knots[None, :]) / KNOT_HOURS),
    ))


def ridge_predict(features: np.ndarray, residual: np.ndarray,
                  masks: dict) -> np.ndarray:
    """Input: [features], [residual], {train, test}. Output: [test predictions]."""
    scaler = StandardScaler().fit(features[masks["train"]])
    model = Ridge(alpha=RIDGE_ALPHA).fit(
        scaler.transform(features[masks["train"]]), residual[masks["train"]]
    )
    return model.predict(scaler.transform(features[masks["test"]]))


def block_masks(rows: list[dict], start_hour: float) -> dict | None:
    """Input: [ordered anchors], block start hour. Output: {train,test} or None."""
    elapsed = np.array([row["elapsed_hours"] for row in rows])
    test = (elapsed >= start_hour) & (elapsed < start_hour + BLOCK_HOURS)
    if not np.any(test):
        return None
    held = [row for row, selected in zip(rows, test, strict=True) if selected]
    support_start = min(row["support_start_us"] for row in held)
    support_end = max(row["support_end_us"] for row in held)
    train = np.array([
        row["support_end_us"] < support_start
        or row["support_start_us"] > support_end
        for row in rows
    ])
    if not np.any(train & (elapsed < start_hour)) or not np.any(
        train & (elapsed >= start_hour + BLOCK_HOURS)
    ):
        return None
    if np.any(train & test):
        raise ValueError("Training and held-out anchors overlap.")
    return {"train": train, "test": test}


def evaluate_block(rows: list[dict], start_hour: float) -> list[dict]:
    """Input: [one storm's anchors], block start hour. Output: [held-out predictions]."""
    elapsed = np.array([row["elapsed_hours"] for row in rows])
    residual = np.array([row["residual_log_density"] for row in rows])
    day_fraction = np.array([row["day_fraction"] for row in rows])
    time_matrix = time_features(elapsed)
    combined_matrix = np.column_stack((time_matrix, day_fraction))
    masks = block_masks(rows, start_hour)
    if masks is None:
        return []
    train, test = masks["train"], masks["test"]
    interpolated = np.interp(elapsed[test], elapsed[train], residual[train])
    time_only = ridge_predict(time_matrix, residual, masks)
    time_day = ridge_predict(combined_matrix, residual, masks)
    predictions = []
    for index, interpolation, ridge_a, ridge_b in zip(
        np.flatnonzero(test), interpolated, time_only, time_day, strict=True
    ):
        predictions.append({
            "storm_id": rows[index]["storm_id"],
            "block_start_us": rows[0]["time_us"] + round(start_hour * 3_600_000_000),
            "time_us": rows[index]["time_us"],
            "day_fraction": float(day_fraction[index]),
            "train_count": int(train.sum()),
            "residual_true": float(residual[index]),
            "trial4": 0.0,
            "interpolation": float(interpolation),
            "ridge_time": float(ridge_a),
            "ridge_time_day": float(ridge_b),
        })
    return predictions


def evaluate_storm(rows: list[dict]) -> list[dict]:
    """Input: [one storm's ordered anchors]. Output: [regular held-out predictions]."""
    predictions = []
    for start_hour in np.arange(BLOCK_HOURS, rows[-1]["elapsed_hours"] - BLOCK_HOURS,
                                STEP_HOURS):
        predictions.extend(evaluate_block(rows, float(start_hour)))
    return predictions


def score(rows: list[dict]) -> dict:
    """Input: [held-out predictions]. Output: {count, method_rmse, method_mae}."""
    truth = np.array([row["residual_true"] for row in rows])
    metrics = {"heldout_count": len(rows)}
    for method in METHODS:
        error = truth - np.array([row[method] for row in rows])
        metrics[f"{method}_rmse"] = float(np.sqrt(np.mean(error ** 2)))
        metrics[f"{method}_mae"] = float(np.mean(np.abs(error)))
    return metrics


def write_csv(path: Path, rows: list[dict]) -> None:
    """Input: new CSV path, [{field: value}]. Output: UTF-8 CSV on disk."""
    with path.open("x", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """Input: Trial6 anchor features. Output: blocked predictions and metrics CSVs."""
    if any(path.exists() for path in (PREDICTIONS, BLOCK_METRICS, EVENT_METRICS)):
        raise FileExistsError("Trial6 Ridge output already exists.")
    grouped = load_rows()
    all_predictions = []
    event_metrics = []
    block_metrics = []
    for storm_id, rows in grouped.items():
        predictions = evaluate_storm(rows)
        if not predictions:
            raise ValueError(f"No valid held-out blocks: {storm_id}")
        all_predictions.extend(predictions)
        event_metrics.append({"storm_id": storm_id, "block_count": len({
            row["block_start_us"] for row in predictions
        }), **score(predictions)})
        for block_start_us in sorted({row["block_start_us"] for row in predictions}):
            block = [row for row in predictions if row["block_start_us"] == block_start_us]
            block_metrics.append({"storm_id": storm_id, "block_start_us": block_start_us,
                                  **score(block)})
    event_metrics.append({"storm_id": "all_storms", "block_count": len(block_metrics),
                          **score(all_predictions)})
    PREDICTIONS.parent.mkdir(parents=True, exist_ok=True)
    write_csv(PREDICTIONS, all_predictions)
    write_csv(BLOCK_METRICS, block_metrics)
    write_csv(EVENT_METRICS, event_metrics)
    print(f"Scored {len(all_predictions)} held-out anchors in {len(block_metrics)} blocks")


if __name__ == "__main__":
    main()
