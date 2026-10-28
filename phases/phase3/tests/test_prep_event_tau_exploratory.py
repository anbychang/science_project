"""Check event-delay exclusion rules at their boundaries."""

from phases.phase3.code.prep_event_tau_exploratory import summarize_grid


def test_boundary_and_broad_range_are_not_trend_eligible():
    """Input: synthetic fit grids. Output: boundary and width flags."""
    grid = [{"tau_hours": index / 4, "gain_per_nt": 0.001,
             "train_rmse_log_density": 1 + abs(index - 40) / 100}
            for index in range(41)]
    boundary = summarize_grid(grid)
    assert boundary["at_grid_boundary"]
    assert not boundary["trend_eligible"]

    for row in grid:
        row["train_rmse_log_density"] = 1 + abs(row["tau_hours"] - 5) / 100
    broad = summarize_grid(grid)
    assert broad["broad_5pct_range"]
    assert not broad["trend_eligible"]
