# P6.2 Phase 4 D-model density -> 半長軸下降資料血緣

狀態：[done]。P6.2 只讀 Phase 4 D-model、P6.1 minute pairs 與 P6.1 `B_eff`。輸出是 `swarm_a_phase6_2_phase4_decay_v1.sqlite`；Phase 4 與 P6.1 不修改。

#### [P6.2.1] Phase 4 + P6.1 -> fixed-`B_eff` decay [done]

```text
calc_phase6_2_phase4_decay.py -> run()

只處理 Phase 4 的 25 場磁暴 `-2` 至 `+4` 天窗口；每場各自歸零。
以 time_us 精確連接 Phase 4 D-model density 與 P6.1 POD minute semi-major axis。
固定 P6.1 B_eff；相鄰分鐘用 60 s 梯形積分。
事件內缺分鐘或 chunk_id 改變時切 block；不補值、不跨缺口積分。
```

```text
trial4_joint_fit_minute (derived；Phase 4；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691041800000000 (us),
    rho_l2_phase_kg_m3: 6.920e-13 (kg/m^3),
    rho_trial4_joint_phase_kg_m3: 6.805e-13 (kg/m^3),
    algorithm_version: trial4_joint_fit_tau15_v1,
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
phase6_2_phase4_decay_minute_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691041800000000 (us),
    block_index: 1,
    chunk_id: 11,
    observed_a_m: 6.858e6 (m),
    rho_l2_phase_kg_m3: 6.920e-13 (kg/m^3),
    rho_phase4_kg_m3: 6.805e-13 (kg/m^3),
    predicted_phase4_delta_a_m: 0.000e0 (m),
    b_eff_m2_kg: 9.229e-3 (m^2/kg),
    algorithm_version: phase6_2_fixed_beff_phase4_decay_v1,
  },
  ...,
]

phase6_2_phase4_decay_event_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    start_time_us: 1691041800000000 (us),
    stop_time_us: 1691562360000000 (us),
    minute_count: 8677,
    block_count: 1,
    observed_covered_delta_a_m: -2.314e2 (m),
    predicted_l2_covered_delta_a_m: -1.769e2 (m),
    predicted_phase4_covered_delta_a_m: -1.761e2 (m),
    phase4_covered_error_m: 5.534e1 (m),
    b_eff_m2_kg: 9.229e-3 (m^2/kg),
    algorithm_version: phase6_2_fixed_beff_phase4_decay_v1,
  },
  ...,
]
```

Phase 4 的 214,907 個 minute rows 全部精確連接 P6.1，共 25 場、31 個 continuous blocks。`time_us` 是 UTC minute center。每場輸出一列獨立結果；事件結果只加總該場有 Phase 4 density 支持的 blocks，不包含缺口期間。

Phase 4 是本專案的 retrospective D-model。P6.2 不把這個閉合寫成獨立模型驗證或 forecast skill。
