"""Check the direct Trial4 anchor and adjacent-orbit contract."""

import math
import sqlite3
import sys
from contextlib import closing
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from load_phase5_trial4_orbits import load_events  # noqa: E402
from prep_phase5_direct_gpr import build_pairs, eligible_pair_keys  # noqa: E402


def test_direct_trial4_pairs() -> None:
    """Input: two frozen Trial4 SQLite files. Output: verified anchor/pair counts."""
    events, event_times = load_events()
    pairs = build_pairs(events)
    eligible = eligible_pair_keys(events)
    assert len(events) == len(event_times) == 25
    assert sum(map(len, events.values())) == 2295
    assert len(pairs) == 2265
    assert len(eligible) == 2115
    assert eligible <= {(pair["storm_id"], pair["time_us"]) for pair in pairs}
    saved_path = (Path(__file__).resolve().parents[1] /
                  "data/sqlite/swarm_a_phase5_pooled_orbit_gpr_v1.sqlite")
    uri = f"file:{saved_path.as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as database:
        saved = database.execute("""
            SELECT storm_id,time_us,rho_trial4_phase_kg_m3,rho_l2_phase_kg_m3
            FROM phase5_orbit_prediction
        """).fetchall()
        assert database.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert database.execute("PRAGMA foreign_key_check").fetchone() is None
        assert database.execute("SELECT count(*) FROM phase5_orbit_anchor").fetchone()[0] == 2295
        version = database.execute(
            "SELECT value FROM phase5_metadata WHERE name='algorithm_version'").fetchone()[0]
        for table in ("phase5_orbit_anchor", "phase5_fold", "phase5_fold_storm",
                      "phase5_orbit_prediction", "phase5_event_metric",
                      "phase5_summary_metric"):
            assert database.execute(
                f"SELECT count(*) FROM {table} WHERE algorithm_version != ?",
                (version,)).fetchone()[0] == 0
    by_key = {(pair["storm_id"], pair["time_us"]): pair for pair in pairs}
    assert {(row[0], row[1]) for row in saved} == set(by_key)
    assert len(saved) == len(by_key)
    for storm_id, time_us, baseline, l2 in saved:
        pair = by_key[(storm_id, time_us)]
        assert baseline == pair["rho_trial4_phase_kg_m3"]
        assert l2 == pair["rho_l2_phase_kg_m3"]


def test_eligibility_restarts_after_missing_orbit() -> None:
    """Input: [two synthetic orbit runs]. Output: only the seventh orbit in each run."""
    rows = [{"time_us": index, "u_rel_rad": grid * 2 * math.pi}
            for index, grid in enumerate([0, 1, 2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14, 15])]
    assert eligible_pair_keys({"storm": rows}) == {("storm", 6), ("storm", 13)}
