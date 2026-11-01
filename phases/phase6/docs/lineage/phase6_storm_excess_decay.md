# Phase 6 磁暴後額外下降量資料血緣

狀態：[retained]。本步錯把 `[-2, 0)` 視為背景控制段，但專案定義的完整磁暴視窗是 `[-2, +4)`。`swarm_a_phase6_storm_excess_decay_v1.sqlite` 只保留為失敗方法紀錄，不作現行輸入。現行方法見 [P6.6 平靜背景差異](phase6_quiet_background_excess_decay.md)。

#### [P6.5] 逐圈半長軸 + 磁暴前斜率 -> 磁暴後額外下降量 [done]

```text
calc_phase6_storm_excess_decay.py -> run()

每場讀取 [t0 - 2 day, t0 + 4 day) 的同 chunk 完整逐圈平均。
前 6 圈、t0 前最後 6 圈與末 6 圈各作局部直線擬合；t0 值只用 t0 前資料外推。
[t0 - 2 day, t0) 的全部逐圈點另作 local pre-storm OLS，這是主要背景斜率。
90 天 pre-storm 斜率保留作敏感度。4/6/8 圈端點定義全部保存。

post excess loss = local pre-storm rate * post duration - observed post delta a

正值代表 t0 後實際下降多於磁暴前局部趨勢；負值代表沒有觀察到增加。
```

```text
swarm_a_phase_orbit_mean_v2 + phase6_prestorm_baseline_v1 (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    t0_time_us: 1715393640000000 (us),
    chunk_id: 11,
    baseline_coverage_days: 9.000e1 (day),
    baseline_rate_m_day: -5.174e1 (m/day)
  },
  ...,
]
```

```text
phase6_storm_excess_decay_v1 (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    t0_time_us: 1715393640000000 (us),
    first_orbit_time_us: 1715225722000000 (us),
    t0_anchor_time_us: 1715393640000000 (us),
    last_orbit_time_us: 1715733692000000 (us),
    orbit_count: 91,
    local_pre_rate_m_day: -5.082e1 (m/day),
    post_observed_delta_a_6_m: -3.210e2 (m),
    local_post_background_delta_a_m: -2.000e2 (m),
    local_post_excess_decay_6_m: 1.210e2 (m),
    local_post_excess_decay_ols_sigma_6_m: 1.032e1 (m),
    local_increased_decay: 1,
    algorithm_version: phase6_storm_post_t0_excess_decay_v1
  },
  ...,
]
```

`t0_anchor_time_us` 是 Phase 4 事件 `t0`，其半長軸值只由 t0 前端點資料外推。OLS sigma 未處理逐圈自相關，也不涵蓋背景方法選擇；90 天與兩天背景符號比較是必要的 model sensitivity，不可併入單一 OLS sigma。
