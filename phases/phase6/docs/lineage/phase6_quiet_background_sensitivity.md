# Phase 6 平靜背景逐日留一敏感度資料血緣

狀態：[retained]。本步讀取 v2 平靜背景定義，逐次移除一個已接受平靜 UTC 日並重算背景斜率。輸出在本機 `phases/phase6/data/sqlite/swarm_a_phase6_quiet_background_sensitivity_v1.sqlite`；目前只保留作方法比較。

#### [P6.7] 平靜日逐日留一 -> 背景斜率與六天差異範圍 [done]

```text
calc_phase6_quiet_background_sensitivity.py -> run()

對每場至少有兩個平靜日的事件，每次移除一個完整 UTC 日。
剩餘平靜日的全部逐圈平均重新作 OLS，再以原事件六天 duration 與 observed delta a 重算 excess loss。
reference 與所有 omission 結果同號才標記 sign_stable；reference 與所有 omission 都為正才標記 positive_under_all_omissions。
```

```text
phase6_prestorm_quiet_baseline_v1 + phase6_storm_excess_decay_v2 + swarm_a_phase_orbit_mean_v2 (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    quiet_day_count: 9,
    quiet_rate_m_day: -5.162e1 (m/day),
    duration_days: 5.879e0 (day),
    observed_delta_a_6_m: -4.230e2 (m),
    excess_decay_6_m: 1.195e2 (m)
  },
  ...,
]
```

```text
phase6_quiet_background_omission_v1 + phase6_quiet_background_sensitivity_v1 (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    omitted_day_start_time_us: 1708041600000000 (us),
    remaining_quiet_day_count: 8,
    remaining_orbit_count: 121,
    rate_m_day: -5.174e1 (m/day),
    rate_1sigma_m_day: 2.333e-1 (m/day),
    excess_decay_6_m: 1.189e2 (m)
  },
  {
    storm_id: S20240511T0214,
    omission_count: 9,
    rate_min_m_day: -5.222e1 (m/day),
    rate_max_m_day: -5.090e1 (m/day),
    excess_min_m: 1.160e2 (m),
    excess_max_m: 1.238e2 (m),
    maximum_absolute_excess_change_m: 4.263e0 (m),
    sign_stable: 1,
    positive_under_all_omissions: 1,
    status: evaluated
  },
  ...,
]
```

`omitted_day_start_time_us` 是被移除的完整 UTC 日起點。只剩一個平靜日的 refit 仍可作數學敏感度，但不代表單日背景已通過物理 acceptance；`S20230805T0546` 原本只有一日，因此不能作逐日留一。
