# Phase 6 磁暴前平靜背景與六天額外下降量資料血緣

狀態：[retained]。本步在完整磁暴視窗 `[-2, +4)` 之前搜尋平靜日，再計算六天差異。輸出在本機 `phases/phase6/data/sqlite/swarm_a_phase6_storm_excess_decay_v2.sqlite`；目前只保留作方法比較。

#### [P6.6] 磁暴前平靜日 + 完整六天逐圈半長軸 -> 額外下降量 [done]

```text
calc_phase6_quiet_background_excess_decay.py -> run()

每場從 t0 - 2 day 往前搜尋 90 天，限制同一 chunk_id。
完整 UTC 日必須有 8 筆 Ap、1,440 筆 SME，且 Ap <= 7、SME < 300 nT；不要求 density。
所有通過的平靜日逐圈平均共同作 OLS，不手選單一日期，也不跨入 [-2, +4) 磁暴視窗。
完整磁暴窗的前後端點以 4/6/8 圈局部擬合；6 圈是 reference。

excess loss = quiet rate * event duration - observed event delta a
```

```text
space_weather + SME_YYYYMMDD.csv + swarm_a_phase_orbit_mean_v2 + trial4_25storm_overview (欄位節錄)
[
  {
    storm_id: S20240511T0214,
    t0_time_us: 1715393640000000 (us),
    chunk_id: 11
  },
  {
    day_start_time_us: 1706832000000000 (us),
    ap_max: 4.000e0,
    sme_max_nt: 2.515e2 (nT)
  },
  ...,
]
```

```text
phase6_prestorm_quiet_baseline_v1 + phase6_storm_excess_decay_v2 (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    event_start_time_us: 1715220840000000 (us),
    search_start_time_us: 1707444840000000 (us),
    quiet_day_count: 9,
    longest_quiet_run_days: 2,
    nearest_quiet_gap_days: 1.309e1 (day),
    quiet_orbit_count: 137,
    quiet_coverage_days: 7.001e1 (day),
    quiet_rate_m_day: -5.162e1 (m/day),
    status: evaluated
  },
  {
    storm_id: S20240511T0214,
    first_orbit_time_us: 1715225722000000 (us),
    last_orbit_time_us: 1715733692000000 (us),
    event_orbit_count: 91,
    duration_days: 5.879e0 (day),
    observed_delta_a_6_m: -4.230e2 (m),
    quiet_background_delta_a_m: -3.035e2 (m),
    excess_decay_6_m: 1.195e2 (m),
    excess_decay_ols_sigma_6_m: 5.697e0 (m),
    increased_decay: 1,
    status: evaluated
  },
  ...,
]
```

`day_start_time_us` 是完整 UTC 日起點；`event_start_time_us = t0 - 2 day`。`quiet_coverage_days` 是首末平靜逐圈點的時間跨度，不表示中間日期全部平靜。24 場有數學上可擬合的平靜背景，但平靜日數、連續性與距離差異很大；OLS sigma 不包含這個 selection uncertainty 或逐圈自相關。
