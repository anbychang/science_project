"""Split Phase 5 anchors into reproducible 20-train/5-test storm folds."""

import numpy as np
from sklearn.model_selection import GroupKFold

from phases.phase5.code.calc_phase5_trial4_gpr import RANDOM_STATE


FOLD_COUNT = 5
STORM_COUNT = 25
TRAIN_STORM_COUNT = 20
TEST_STORM_COUNT = 5


def split_storm_folds(storm_ids: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """Input: [anchor storm_id]. Output: [(train anchor indices, test anchor indices)]."""
    groups = np.asarray(storm_ids)
    if groups.ndim != 1 or len(np.unique(groups)) != STORM_COUNT:
        raise ValueError("Phase 5 group CV requires exactly 25 storm IDs.")
    splitter = GroupKFold(
        n_splits=FOLD_COUNT, shuffle=True, random_state=RANDOM_STATE
    )
    folds = list(splitter.split(groups, groups=groups))
    if len(folds) != FOLD_COUNT:
        raise ValueError("Phase 5 group CV did not produce five folds.")
    for train_indices, test_indices in folds:
        train_storms = set(groups[train_indices])
        test_storms = set(groups[test_indices])
        if (len(train_storms) != TRAIN_STORM_COUNT
                or len(test_storms) != TEST_STORM_COUNT
                or train_storms & test_storms):
            raise ValueError("Phase 5 group CV storm split is invalid.")
    return folds
