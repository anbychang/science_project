# P6.1 逐分鐘 L2 density -> `B_eff` 資料血緣

狀態：[done]。P6.1 只擬合一個全域 `B_eff`。輸出是 `swarm_a_phase6_1_l2_minute_pairs_v1.sqlite` 與 `swarm_a_phase6_1_beff_v1.sqlite`；raw DNSAPOD 與 Phase 1 checkpoint 不修改。

#### [P6.1.1] DNSAPOD + POD mean elements -> complete minute pairs [done]

```text
prep_phase6_1_l2_minute_pairs.py -> run()

DNSAPOD instantaneous density 與可用 POD mean semi-major axis 都四捨五入到最近 UTC minute。
每分鐘必須有 2 筆 density、6 筆 POD，且只能有一個 chunk_id；不補缺值。
```

```text
SW_OPER_DNSAPOD_2__20230701T000000_20230701T235930_0301.ZIP (raw；欄位節錄)
[
  {
    time_us: 1688169630000000 (us),
    rho_l2_kg_m3: 4.262e-13 (kg/m^3),
  },
  ...,
]

swarm_a_mean_orbit_elements_v1 + swarm_a_pod_quality (derived；欄位節錄)
[
  {
    time_us: 1688169662000000 (us),
    mean_semi_major_axis_m: 6.859e6 (m),
    is_usable: 1,
    chunk_id: 11,
  },
  ...,
]
```

```text
phase6_1_l2_pod_minute_pair_v1 (derived；欄位節錄)
[
  {
    time_us: 1688169660000000 (us),
    chunk_id: 11,
    mean_semi_major_axis_m: 6.859e6 (m),
    pod_sample_count: 6,
    rho_l2_kg_m3: 4.186e-13 (kg/m^3),
    density_sample_count: 2,
    algorithm_version: phase6_1_l2_pod_minute_pair_v1,
  },
  ...,
]
```

輸出 `time_us` 是 minute center。資料範圍為 2023-07-01T00:01:00Z 至 2026-06-30T23:59:00Z，共 1,575,708 個 complete paired minutes。

#### [P6.1.2] complete minute pairs -> one global `B_eff` [done]

```text
calc_phase6_1_beff.py -> run()

相鄰分鐘以 60 s 梯形法積分 rho*sqrt(mu*a)。缺分鐘或 chunk_id 改變就切新 block。
每個 block 的 K 與 Delta-a_POD 從零開始；全三年 cumulative points 共用一個 zero-intercept B_eff。
B_eff = -sum(K*Delta-a_POD)/sum(K^2)
```

```text
phase6_1_l2_pod_minute_pair_v1 (derived；引用上一步 key)
[
  {
    time_us: 1688169660000000 (us),
    chunk_id: 11,
    mean_semi_major_axis_m: 6.859e6 (m),
    rho_l2_kg_m3: 4.186e-13 (kg/m^3),
  },
  ...,
]
```

```text
phase6_1_l2_integral_minute_v1 (derived；欄位節錄)
[
  {
    time_us: 1688169720000000 (us),
    interval_start_time_us: 1688169660000000 (us),
    block_index: 1,
    chunk_id: 11,
    cumulative_kernel_kg_m: 1.268e0 (kg/m),
    observed_cumulative_delta_a_m: 9.496e0 (m),
    predicted_cumulative_delta_a_m: -1.170e-2 (m),
    residual_m: -9.508e0 (m),
    algorithm_version: phase6_1_global_minute_beff_v1,
  },
  ...,
]

phase6_1_beff_fit_v1 (derived)
[
  {
    fit_id: all_three_year_minute_points,
    beta_eff_m2_kg: 9.229e-3 (m^2/kg),
    paired_minute_count: 1575708,
    integral_point_count: 1575671,
    block_count: 37,
    mean_absolute_error_m: 6.847e1 (m),
    root_mean_square_error_m: 8.511e1 (m),
    mean_error_m: 1.299e0 (m),
    algorithm_version: phase6_1_global_minute_beff_v1,
  },
]
```

P6.1 的主結果只有 `B_eff=9.229e-3 m²/kg`。誤差欄位只用於 audit；逐分鐘 POD 抖動、共同 POD lineage 與 in-sample fitting 使它們不能作獨立準確率或 forecast skill。
