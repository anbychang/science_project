"""Check Trial4's bounded offset and tau-grid updates."""

import math
import sys
from pathlib import Path

import numpy as np


CODE_DIRECTORY = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE_DIRECTORY))

from calc_trial4_joint_fit import (
    EventFitData,
    FitState,
    select_tau_indices,
    tau_grid_hours,
    update_offsets,
)
import calc_h_tau
import prep_h_tau_phase
from prep_trial4_joint_fit import GAIN_GRID, PREDICTIONS


def test_joint_fit_reads_trial4_input_snapshots() -> None:
    """Input: Trial4 entry-point paths. Output: Trial4-owned source snapshots."""
    assert PREDICTIONS.parent.parent.name == "data"
    assert PREDICTIONS.parents[2].name == "phase3-trial4"
    assert GAIN_GRID.parents[2].name == "phase3-trial4"


def test_joint_fit_uses_trial4_local_phase_response_code() -> None:
    """Input: Trial4 response loader. Output: local calculator and local output path."""
    assert prep_h_tau_phase.filtered_sme is calc_h_tau.filtered_sme
    assert prep_h_tau_phase.OUTPUT.parents[2].name == "phase3-trial4"


def test_offset_update_keeps_r_below_two() -> None:
    """Input: event requiring R=3. Output: fitted R remains below the hard bound."""
    event = EventFitData(
        storm_id="S",
        log_density_anomaly=np.full(2, math.log(3)),
        r_rq=1.0,
        h_baseline_nt=np.zeros(2),
        h_tau_grid_nt=np.zeros((len(tau_grid_hours()), 2)),
    )
    state = FitState(np.zeros(1), np.zeros(1, dtype=np.int16), 1.0)
    assert math.exp(update_offsets([event], state).log_r_by_event[0]) < 2


def test_tau_update_selects_lower_loss_grid_value() -> None:
    """Input: response matching tau index 1. Output: selected tau index is 1."""
    response_grid = np.zeros((len(tau_grid_hours()), 2))
    response_grid[1] = [0.0, 1.0]
    event = EventFitData(
        storm_id="S",
        log_density_anomaly=np.array([0.0, 1.0]),
        r_rq=1.0,
        h_baseline_nt=np.zeros(2),
        h_tau_grid_nt=response_grid,
    )
    state = FitState(np.zeros(1), np.zeros(1, dtype=np.int16), 1.0)
    assert select_tau_indices([event], state).tau_index_by_event[0] == 1
