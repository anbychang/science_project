# P6.4 POD、M0、Ridge 下降重整資料血緣

狀態：[done]。P6.4 讀 P6.2、P6.3 與 Phase 1 衍生 SQLite，輸出 minute/event comparison、25 場磁暴等權分數、逐圈底層誤差與兩張圖；不修改上游資料，也不重新計算 density 或 `B_eff`。

| 角色 | 路徑 |
| --- | --- |
| P6.2 M0 | `phases/phase6/data/sqlite/swarm_a_phase6_2_m0_error_v1.sqlite` |
| P6.3 Ridge | `phases/phase6/data/sqlite/swarm_a_phase6_3_ridge_decay_v1.sqlite` |
| P5 V2 L2 reference | `phases/phase5-v2/data/sqlite/storm_r_ridge_density_v1.sqlite` |
| Phase 1 orbit mean | `phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite` |
| P6.4 output | `phases/phase6/data/sqlite/swarm_a_phase6_4_decay_comparison_v1.sqlite` |
| P6.4 orbit score | `phases/phase6/data/sqlite/swarm_a_phase6_4_orbit_scores_v1.sqlite` |
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
下降圖的 M0 與 Ridge 仍依 P6.4 block 分開畫，不跨 density 缺口連線。
密度圖另以 {storm_id, time_us} 精確連接 Phase 5 V2 的 orbit-phase-average L2；214,907 個 P6.4 minutes 都必須有 L2，否則停止繪圖。
Density 圖的 6 個真實資料缺口以兩端值做線性內差，並以同色實線連續顯示，不另外標示缺口。內差只存在於 PNG，不寫回 SQLite，也不進下降積分或磁暴評分。
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

density_comparison (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691041800000000 (us),
    rho_l2_phase_kg_m3: 6.920e-13 (kg/m^3),
    rho_ridge_phase_kg_m3: 6.103e-13 (kg/m^3),
    algorithm_version: storm_r_ridge_density_v1
  },
  ...,
]

swarm_a_phase_orbit_mean_v2 (derived；欄位節錄)
[
  {
    time_us: 1691043232000000 (us),
    orbit_start_time_us: 1691037582000000 (us),
    phase_weighted_mean_semi_major_axis_m: 6.858e6 (m),
    chunk_id: 11
  },
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
phase6_4_density_time_25_storms.png (PNG；L2/M0/Ridge density；25 panels)
```

下降圖的 POD 是 complete-orbit trend，不是 event endpoint estimator。density 圖的 L2 只作觀測參考；P6.4 下降與磁暴分數仍只比較 M0 和 Ridge。

#### [P6.4.3] complete POD orbits + minute predictions -> storm score [done]

```text
calc_phase6_4_orbit_scores.py -> run()

相鄰 complete POD orbits -> Delta-a-POD = mean-a[j] - mean-a[j-1]。
兩個 orbit endpoints 各對應到最近 UTC minute；同一 density block 的 cumulative model predictions 相減，得到該圈 model Delta-a。
POD orbit 必須連續且 chunk_id 相同；model endpoints 必須存在且 block 相同。缺口不插值，跨缺口 orbit 不計分。
每場分別計算 M0 與 Ridge 的 orbit MAE，MAE 較低者贏得該場；25 場磁暴各一票。
正式分數是 Ridge 15 勝、M0 10 勝、0 平手。2,262 個 local orbit errors 與 endpoint comparison 都是輔助證據。
```

```text
swarm_a_phase_orbit_mean_v2 + phase6_4_decay_comparison_minute_v1 (derived；欄位節錄)
[
  {
    time_us: 1691048892000000 (us),
    orbit_start_time_us: 1691043242000000 (us),
    phase_weighted_mean_semi_major_axis_m: 6.858e6 (m),
    chunk_id: 11
  },
  {
    storm_id: S20230805T0546,
    time_us: 1691043240000000 (us),
    block_index: 1,
    predicted_m0_block_delta_a_m: -4.889e-1 (m),
    predicted_ridge_block_delta_a_m: -4.236e-1 (m)
  },
  {
    storm_id: S20230805T0546,
    time_us: 1691048880000000 (us),
    block_index: 1,
    predicted_m0_block_delta_a_m: -2.391e0 (m),
    predicted_ridge_block_delta_a_m: -2.067e0 (m)
  },
  ...,
]
```

```text
phase6_4_orbit_score_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    orbit_end_time_us: 1691048892000000 (us),
    previous_orbit_end_time_us: 1691043232000000 (us),
    model_start_time_us: 1691043240000000 (us),
    model_stop_time_us: 1691048880000000 (us),
    observed_orbit_delta_a_m: 3.274e0 (m),
    predicted_m0_orbit_delta_a_m: -1.903e0 (m),
    m0_error_m: -5.177e0 (m),
    predicted_ridge_orbit_delta_a_m: -1.643e0 (m),
    ridge_error_m: -4.918e0 (m),
    closer_model: P5V2_RIDGE,
    algorithm_version: phase6_4_storm_primary_score_v2
  },
  ...,
]

phase6_4_orbit_summary_v1 (derived)
[
  {
    model_id: M0,
    event_count: 25,
    scored_orbit_count: 2262,
    mean_absolute_error_m: 5.460e0 (m),
    root_mean_square_error_m: 7.461e0 (m),
    closer_orbit_count: 1093,
    algorithm_version: phase6_4_storm_primary_score_v2
  },
  {
    model_id: P5V2_RIDGE,
    event_count: 25,
    scored_orbit_count: 2262,
    mean_absolute_error_m: 5.425e0 (m),
    root_mean_square_error_m: 7.412e0 (m),
    closer_orbit_count: 1169,
    algorithm_version: phase6_4_storm_primary_score_v2
  }
]

phase6_4_orbit_event_summary_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    scored_orbit_count: 91,
    m0_mean_absolute_error_m: 5.441e0 (m),
    ridge_mean_absolute_error_m: 5.428e0 (m),
    winner_model: P5V2_RIDGE,
    mae_margin_m: 1.347e-2 (m),
    algorithm_version: phase6_4_storm_primary_score_v2
  },
  ...,
]

phase6_4_storm_summary_v1 (derived)
[
  {
    summary_id: PRIMARY,
    storm_count: 25,
    m0_win_count: 10,
    ridge_win_count: 15,
    tied_storm_count: 0,
    m0_macro_mean_orbit_mae_m: 5.460e0 (m),
    ridge_macro_mean_orbit_mae_m: 5.425e0 (m),
    algorithm_version: phase6_4_storm_primary_score_v2
  }
]
```

`orbit_end_time_us` 是 Phase 1 complete orbit 的 UTC 結束時刻。`model_start_time_us` 與 `model_stop_time_us` 是對應的最近 UTC minute centers。
