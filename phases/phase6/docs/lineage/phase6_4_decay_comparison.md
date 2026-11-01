# P6.4 POD、M0、Ridge 下降重整資料血緣

狀態：[done]。P6.4 讀 P6.2、P6.3 衍生 SQLite，輸出 `swarm_a_phase6_4_decay_comparison_v1.sqlite`。下降圖另讀 Phase 1 完整軌道平均；不修改上游資料，也不重新計算 density 或 `B_eff`。

| 角色 | 路徑 |
| --- | --- |
| P6.2 M0 | `phases/phase6/data/sqlite/swarm_a_phase6_2_m0_error_v1.sqlite` |
| P6.3 Ridge | `phases/phase6/data/sqlite/swarm_a_phase6_3_ridge_decay_v1.sqlite` |
| Phase 1 orbit mean | `phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite` |
| P6.4 output | `phases/phase6/data/sqlite/swarm_a_phase6_4_decay_comparison_v1.sqlite` |
| Decline figure | `phases/phase6/figures/phase6_4_decay_time_25_storms.png` |
| Density figure | `phases/phase6/figures/phase6_4_density_time_25_storms.png` |

#### [P6.4.1] P6.2 + P6.3 -> 統一 minute 與 event comparison [done]

```text
prep_phase6_4_decay_comparison.py -> run()

以 {storm_id, time_us} 精確連接 214,907 個 minute rows；POD、block、chunk 與 B_eff 必須相同。
每個 block 保留原本局部下降；跨 block 只累加已覆蓋 endpoint，不補缺口、不跨缺口積分。
event 與 summary 數值直接沿用 P6.2、P6.3，不重新擬合或重新積分。
```

```text
phase6_2_m0_decay_minute_v1 + phase6_3_ridge_decay_minute_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691041800000000 (us),
    block_index: 1,
    chunk_id: 11,
    observed_a_m: 6.858e6 (m),
    observed_delta_a_m: 0.000e0 (m),
    rho_m0_kg_m3: 7.047e-13 (kg/m^3),
    rho_ridge_kg_m3: 6.103e-13 (kg/m^3),
    predicted_m0_delta_a_m: 0.000e0 (m),
    predicted_ridge_delta_a_m: 0.000e0 (m),
    b_eff_m2_kg: 9.229e-3 (m^2/kg)
  },
  ...,
]
```

```text
phase6_4_decay_comparison_minute_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691041800000000 (us),
    block_index: 1,
    observed_covered_delta_a_m: 0.000e0 (m),
    rho_m0_kg_m3: 7.047e-13 (kg/m^3),
    rho_ridge_kg_m3: 6.103e-13 (kg/m^3),
    predicted_m0_covered_delta_a_m: 0.000e0 (m),
    predicted_ridge_covered_delta_a_m: 0.000e0 (m),
    algorithm_version: phase6_4_decay_comparison_v1
  },
  ...,
]

phase6_4_decay_comparison_event_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    start_time_us: 1691041800000000 (us),
    stop_time_us: 1691562360000000 (us),
    observed_covered_delta_a_m: -2.314e2 (m),
    predicted_m0_covered_delta_a_m: -1.764e2 (m),
    m0_error_m: 5.504e1 (m),
    predicted_ridge_covered_delta_a_m: -1.610e2 (m),
    ridge_error_m: 7.043e1 (m),
    algorithm_version: phase6_4_decay_comparison_v1
  },
  ...,
]

phase6_4_decay_comparison_summary_v1 (derived)
[
  {
    model_id: M0,
    event_count: 25,
    mean_absolute_error_m: 7.222e1 (m),
    root_mean_square_error_m: 8.935e1 (m),
    mean_absolute_percentage_error: 1.677e1,
    algorithm_version: phase6_4_decay_comparison_v1
  },
  {
    model_id: P5V2_RIDGE,
    event_count: 25,
    mean_absolute_error_m: 5.308e1 (m),
    root_mean_square_error_m: 7.404e1 (m),
    mean_absolute_percentage_error: 1.182e1,
    algorithm_version: phase6_4_decay_comparison_v1
  }
]
```

`time_us` 是 UTC minute center。輸出共有 214,907 minute rows、25 events、31 continuous blocks；每場最後一個 cumulative value 與 P6.2、P6.3 event endpoint 完全相同。

#### [P6.4.2] 統一 minute comparison -> 25 場時間圖 [done]

```text
prep_phase6_4_figures.py -> run()

每場以 storm_id 解析 t0，橫軸是相對 t0 小時。
下降圖以 Phase 1 的 mean argument of latitude 切分完整 orbit，POD 每圈畫一個 phase-weighted mean；M0 與 P5 V2 Ridge 保留 minute 積分線。
整場 POD 以窗口開始前、相同初始 chunk 的最後一個完整 orbit 為零點。POD 直接讀完整 Phase 1 orbit means，不繼承 density pairing 的 block；只有 POD orbit 不連續或 `chunk_id` 改變才斷黑線。
M0 與 Ridge 仍依 P6.4 block 分開畫，不跨 density 缺口連線。
orbit mean 只用於圖；event endpoint、B_eff 與誤差仍使用 P6.4 原始 minute 結果。
```

```text
phase6_4_decay_comparison_minute_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691041800000000 (us),
    block_index: 1,
    chunk_id: 11,
    observed_covered_delta_a_m: 0.000e0 (m),
    predicted_m0_covered_delta_a_m: 0.000e0 (m),
    predicted_ridge_covered_delta_a_m: 0.000e0 (m)
  },
  ...,
]

swarm_a_phase_orbit_mean_v2 (derived；欄位節錄)
[
  {
    time_us: 1691048892000000 (us),
    orbit_start_time_us: 1691043242000000 (us),
    phase_weighted_mean_semi_major_axis_m: 6.858e6 (m),
    pod_count: 566,
    phase_coverage_rad: 6.272e0 (rad),
    max_pod_gap_s: 1.000e1 (s),
    chunk_id: 11,
    algorithm_version: phase_weighted_orbit_h2_h3_local_ols_v1
  },
  ...,
]
```

```text
phase6_4_decay_time_25_storms.png (PNG；POD/M0/Ridge 下降；25 panels)
phase6_4_density_time_25_storms.png (PNG；M0/Ridge density；25 panels)
```

下降圖的 POD 是 complete-orbit trend，不是 event endpoint estimator。density 圖與兩條模型下降線仍使用原始 minute values。
