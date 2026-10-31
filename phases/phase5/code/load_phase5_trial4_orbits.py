"""Read orbit anchors directly from frozen Phase 4 outputs."""

import math
import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path


PHASE = Path("phases/phase4/data/sqlite/swarm_a_phase3_h_tau_phase_v1.sqlite")
DENSITY = Path("phases/phase4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite")


def read_only(path: Path) -> sqlite3.Connection:
    """Input: SQLite path. Output: read-only connection."""
    return sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)


def load_phase_anchors() -> dict[str, list[tuple[int, float]]]:
    """Input: frozen phase minute table. Output: {storm: [(time_us, phase_rad)]}."""
    with closing(read_only(PHASE)) as database:
        rows = database.execute("""
            SELECT storm_id,time_us,u_rel_rad,phase_is_valid_80pct
            FROM phase3_h_tau_minute ORDER BY storm_id,time_us
        """).fetchall()
    selected = defaultdict(dict)
    for storm_id, time_us, phase_rad, valid in rows:
        if not valid:
            continue
        grid = round(phase_rad / (2 * math.pi))
        distance = abs(phase_rad - 2 * math.pi * grid)
        if distance > 0.02 * math.pi:
            continue
        previous = selected[storm_id].get(grid)
        if previous is None or distance < previous[0]:
            selected[storm_id][grid] = (distance, time_us, phase_rad)
    return {storm_id: [(values[1], values[2]) for _, values in sorted(grids.items())]
            for storm_id, grids in selected.items()}


def load_events() -> tuple[dict[str, list[dict]], dict[str, int]]:
    """Input: two frozen Trial4 SQLite files. Output: {storm: [orbit]}, {storm: t0_us}."""
    anchors = load_phase_anchors()
    with closing(read_only(DENSITY)) as database:
        event_times = dict(database.execute(
            "SELECT storm_id,t0_time_us FROM trial4_25storm_overview"))
        density_rows = database.execute("""
            SELECT storm_id,time_us,rho_l2_phase_kg_m3,
                   rho_trial4_joint_phase_kg_m3,residual_log_density
            FROM trial4_joint_fit_minute
        """).fetchall()
    densities = {(storm_id, time_us): (l2, baseline, residual)
                 for storm_id, time_us, l2, baseline, residual in density_rows}
    if len(anchors) != 25 or set(anchors) != set(event_times):
        raise ValueError("Expected the same 25 Trial4 storms in both sources.")
    events = {}
    for storm_id, positions in sorted(anchors.items()):
        event = []
        for time_us, phase_rad in positions:
            l2, baseline, residual = densities[(storm_id, time_us)]
            if (l2 <= 0 or baseline <= 0 or not math.isfinite(residual)
                    or not math.isclose(residual, math.log(l2 / baseline),
                                        rel_tol=1e-12, abs_tol=1e-12)):
                raise ValueError(f"Invalid Trial4 density: {storm_id}:{time_us}")
            event.append({"storm_id": storm_id, "time_us": time_us,
                          "u_rel_rad": phase_rad,
                          "rho_l2_phase_kg_m3": l2,
                          "rho_trial4_phase_kg_m3": baseline,
                          "residual_log_density": residual})
        events[storm_id] = event
    if sum(map(len, events.values())) != 2295:
        raise ValueError("Expected 2,295 one-orbit anchors from Trial4.")
    return events, event_times
