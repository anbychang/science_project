# P6.3 Phase 5 V2 Ridge -> 半長軸下降資料血緣

狀態：[done]。P6.3 只讀 Phase 5 V2 Ridge density、P6.1 minute pairs 與 P6.1 `B_eff`。輸出是 `swarm_a_phase6_3_ridge_decay_v1.sqlite`；上游 SQLite 不修改。結果屬探索性回溯檢查。

| 角色 | SQLite 路徑 |
| --- | --- |
| Ridge density | `phases/phase5-v2/data/sqlite/storm_r_ridge_density_v1.sqlite` |
| P6.1 minute pairs | `phases/phase6/data/sqlite/swarm_a_phase6_1_l2_minute_pairs_v1.sqlite` |
| P6.1 `B_eff` | `phases/phase6/data/sqlite/swarm_a_phase6_1_beff_v1.sqlite` |
| P6.3 output | `phases/phase6/data/sqlite/swarm_a_phase6_3_ridge_decay_v1.sqlite` |

#### [P6.3.1] Phase 5 V2 Ridge + P6.1 -> storm-by-storm decay error [done]

```text
calc_phase6_3_ridge_decay.py -> run()

只處理 25 場磁暴 t0-2 days 至 t0+4 days 窗口；每場各自歸零。
以 time_us 精確連接 Ridge density 與 P6.1 POD minute semi-major axis。
固定 P6.1 B_eff；相鄰分鐘使用 60 s 梯形積分。
缺分鐘或 chunk_id 改變時切 block；不補值、不跨缺口積分。
```

```text
density_comparison (Phase 5 V2 derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691041800000000 (us),
    rho_ridge_phase_kg_m3: 6.103e-13 (kg/m^3),
    r_ridge: 8.533e-1,
    algorithm_version: storm_r_ridge_density_v1
  },
  ...,
]

phase6_1_l2_pod_minute_pair_v1 (derived；欄位節錄)
[
  {
    time_us: 1691041800000000 (us),
    chunk_id: 11,
    mean_semi_major_axis_m: 6.858e6 (m)
  },
  ...,
]

phase6_1_beff_fit_v1 (derived)
[
  {
    fit_id: all_three_year_minute_points,
    beta_eff_m2_kg: 9.229e-3 (m^2/kg)
  }
]
```

```text
phase6_3_ridge_decay_minute_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691041800000000 (us),
    block_index: 1,
    chunk_id: 11,
    observed_a_m: 6.858e6 (m),
    rho_ridge_kg_m3: 6.103e-13 (kg/m^3),
    predicted_ridge_delta_a_m: 0.000e0 (m),
    b_eff_m2_kg: 9.229e-3 (m^2/kg),
    algorithm_version: phase6_3_fixed_beff_ridge_decay_v1
  },
  ...,
]

phase6_3_ridge_decay_event_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    start_time_us: 1691041800000000 (us),
    stop_time_us: 1691562360000000 (us),
    minute_count: 8677,
    block_count: 1,
    observed_covered_delta_a_m: -2.314e2 (m),
    predicted_ridge_covered_delta_a_m: -1.610e2 (m),
    ridge_error_m: 7.043e1 (m),
    absolute_percentage_error: 3.044e1,
    algorithm_version: phase6_3_fixed_beff_ridge_decay_v1
  },
  ...,
]

phase6_3_ridge_decay_summary_v1 (derived)
[
  {
    summary_id: all_25_storms,
    event_count: 25,
    underestimated_count: 13,
    overestimated_count: 12,
    mean_error_m: 1.830e1 (m),
    mean_absolute_error_m: 5.308e1 (m),
    root_mean_square_error_m: 7.404e1 (m),
    mean_absolute_percentage_error: 1.182e1,
    algorithm_version: phase6_3_fixed_beff_ridge_decay_v1
  }
]
```

Ridge 的 214,907 個 minute rows 全部精確連接 P6.1，共 25 場、31 個 continuous blocks。`time_us` 是 UTC minute center。每場輸出一列獨立誤差；事件結果不包含缺口期間。

Ridge density 使用 Phase 5 V2 的留出 `R_k`、Phase 4 V2 共同 `tau`、`G` 與 response。特徵組合曾由同一 25 場選出，因此 P6.3 不構成獨立 forecast skill。
