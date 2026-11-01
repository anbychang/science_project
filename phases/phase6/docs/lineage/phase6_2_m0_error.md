# P6.2 Phase 3 M0 -> 半長軸下降誤差資料血緣

狀態：[done]。P6.2 只讀 Phase 3 M0 snapshot、P6.1 minute pairs 與 P6.1 `B_eff`。M0 是 NRLMSIS 2.0 full density。輸出是 `swarm_a_phase6_2_m0_error_v1.sqlite`；上游 SQLite 不修改。

#### [P6.2.1] Phase 3 M0 + P6.1 -> storm-by-storm decay error [done]

```text
calc_phase6_2_m0_error.py -> run()

只處理 25 場磁暴 t0-2 days 至 t0+4 days 窗口；每場各自歸零。
以 time_us 精確連接 Phase 3 M0 與 P6.1 POD minute semi-major axis。
固定 P6.1 B_eff；相鄰分鐘使用 60 s 梯形積分。
缺分鐘或 chunk_id 改變時切 block；不補值、不跨缺口積分。
```

```text
phase3_prediction_minute (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691041800000000 (us),
    rho_msis_full_phase_kg_m3: 7.047e-13 (kg/m^3),
  },
  ...,
]

phase6_1_l2_pod_minute_pair_v1 (derived；欄位節錄)
[
  {
    time_us: 1691041800000000 (us),
    chunk_id: 11,
    mean_semi_major_axis_m: 6.858e6 (m),
  },
  ...,
]

phase6_1_beff_fit_v1 (derived)
[
  {
    fit_id: all_three_year_minute_points,
    beta_eff_m2_kg: 9.229e-3 (m^2/kg),
  },
]
```

```text
phase6_2_m0_decay_minute_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691041800000000 (us),
    block_index: 1,
    chunk_id: 11,
    observed_a_m: 6.858e6 (m),
    rho_m0_kg_m3: 7.047e-13 (kg/m^3),
    predicted_m0_delta_a_m: 0.000e0 (m),
    b_eff_m2_kg: 9.229e-3 (m^2/kg),
    algorithm_version: phase6_2_fixed_beff_m0_error_v1,
  },
  ...,
]

phase6_2_m0_error_event_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    start_time_us: 1691041800000000 (us),
    stop_time_us: 1691562360000000 (us),
    minute_count: 8677,
    block_count: 1,
    observed_covered_delta_a_m: -2.314e2 (m),
    predicted_m0_covered_delta_a_m: -1.764e2 (m),
    m0_error_m: 5.504e1 (m),
    absolute_error_m: 5.504e1 (m),
    absolute_percentage_error: 2.379e1,
    b_eff_m2_kg: 9.229e-3 (m^2/kg),
    algorithm_version: phase6_2_fixed_beff_m0_error_v1,
  },
  ...,
]

phase6_2_m0_error_summary_v1 (derived)
[
  {
    summary_id: all_25_storms,
    event_count: 25,
    underestimated_count: 10,
    overestimated_count: 15,
    mean_error_m: -2.472e1 (m),
    mean_absolute_error_m: 7.222e1 (m),
    root_mean_square_error_m: 8.935e1 (m),
    mean_absolute_percentage_error: 1.677e1,
    b_eff_m2_kg: 9.229e-3 (m^2/kg),
    algorithm_version: phase6_2_fixed_beff_m0_error_v1,
  },
]
```

M0 的 214,907 個 minute rows 全部精確連接 P6.1，共 25 場、31 個 continuous blocks。`time_us` 是 UTC minute center。每場輸出一列獨立誤差；事件結果不包含缺口期間。

M0 直接讀自 `swarm_a_phase3_prediction_tau465_exploratory.sqlite` 的 NRLMSIS 2.0 full-density 欄位，不讀 Phase 4 D-model。P6.2 的誤差是固定 `B_eff` 下的 descriptive closure，不是獨立 forecast skill。
