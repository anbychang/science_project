# Phase 6 2022 背景斜率資料血緣

狀態：[retained]。本步使用既有 Phase 1R mean-element source，不重新下載已存在的 366 個 2022 POD 日檔。輸出在本機 `phases/phase6/data/sqlite/swarm_a_phase6_2022_baseline_v1.sqlite`，不修改 Phase 1R。

#### [Legacy] 2022 mean elements -> 同 chunk 逐圈平均與 90 天背景斜率 [retained]

```text
calc_phase6_2022_baseline.py -> run()

讀取 [2022-01-01, 2023-01-01) UTC 的可用 mean elements，以 phase = omega + M 劃分完整軌道。
逐圈平均沿用 Phase 1 的 phase-weighted estimator。每個 chunk 只取結束前 90 天作 OLS；不跨 maneuver、campaign 或來源缺口。
chunk coverage 少於 90 天時保留逐圈資料，但不輸出斜率。
```

```text
swarm_a_mean_orbit_elements_v1 + swarm_a_pod_quality (derived；Phase 1R；欄位節錄)
[
  {
    time_us: 1640997832000000 (us),
    mean_semi_major_axis_m: 6.801e6 (m),
    mean_argument_of_perigee_rad: 3.007e0 (rad),
    mean_anomaly_rad: -3.006e0 (rad),
    chunk_id: 6
  },
  ...,
]
```

```text
phase6_2022_orbit_mean_v1 (derived；欄位節錄)
[
  {
    time_us: 1641003412000000 (us),
    orbit_start_time_us: 1640997832000000 (us),
    phase_weighted_mean_semi_major_axis_m: 6.801e6 (m),
    chunk_id: 6,
    algorithm_version: phase6_2022_chunk_90day_baseline_v1
  },
  ...,
]

phase6_2022_chunk_baseline_v1 (derived；欄位節錄)
[
  {
    chunk_id: 7,
    chunk_start_time_us: 1642121392000000 (us),
    chunk_stop_time_us: 1651530482000000 (us),
    chunk_orbit_count: 1684,
    fit_start_time_us: 1643754482000000 (us),
    fit_orbit_count: 1392,
    fit_coverage_days: 9.001e1 (day),
    rate_m_day: -4.536e1 (m/day),
    rate_1sigma_m_day: 1.880e-1 (m/day),
    status: evaluated
  },
  ...,
]
```

`time_us` 是 orbit 結束時刻。四個 chunk 共 4,564 圈；只有 chunk 7 與 8 達到 90 天。OLS sigma 未處理 orbit-to-orbit autocorrelation，斜率是 descriptive background，不是物理 drag measurement。
