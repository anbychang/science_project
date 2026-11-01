# Phase 6 三年 L2 integral -> POD semi-major axis 資料血緣

狀態：[retained]。本步是 P6.1 逐分鐘擬合的逐圈 sensitivity，不是現行主輸入。輸出是本機 `swarm_a_phase6_l2_three_year_pairs_v1.sqlite` 與 `swarm_a_phase6_l2_three_year_fit_v1.sqlite`；raw DNSAPOD、Phase 1 與舊 Phase 6 輸出不修改。

#### [P6.11] 三年 DNSAPOD + POD orbit means -> paired orbit series [retained]

```text
prep_phase6_l2_three_year_pairs.py -> run()

三年 manifest 的 1,096 個 DNSAPOD daily ZIP -> 排除 validity flag 與 CDF FILLVAL -> density_orbitmean
Phase 1 complete phase orbit -> 最近 L2 sample；abs(density_time-orbit_time) <= 60 s
不選 quiet day，不看 storm ID，不補缺值。
```

```text
SW_OPER_DNSAPOD_2__20230701T000000_20230701T235930_0301.ZIP (raw；欄位節錄)
[
  {
    density_time_us: 1688178900000000 (us),
    rho_l2_orbitmean_kg_m3: 5.693e-13 (kg/m^3),
  },
  ...,
]

swarm_a_phase_orbit_mean_v2 (derived；欄位節錄)
[
  {
    time_us: 1688178902000000 (us),
    orbit_start_time_us: 1688173252000000 (us),
    phase_weighted_mean_semi_major_axis_m: 6.859e6 (m),
    chunk_id: 11,
  },
  ...,
]
```

```text
phase6_l2_three_year_pair_v1 (derived；欄位節錄)
[
  {
    time_us: 1688178902000000 (us),
    orbit_start_time_us: 1688173252000000 (us),
    mean_semi_major_axis_m: 6.859e6 (m),
    chunk_id: 11,
    density_time_us: 1688178900000000 (us),
    rho_l2_orbitmean_kg_m3: 5.693e-13 (kg/m^3),
    density_offset_s: -2.000e0 (s),
    density_source_file: SW_OPER_DNSAPOD_2__20230701T000000_20230701T235930_0301.ZIP,
    algorithm_version: phase6_l2_three_year_nearest_orbitmean_v1,
  },
  ...,
]
```

`time_us` 是 Phase 1 orbit end；`density_time_us` 是最近的 DNSAPOD sample。三年 Phase 1 有 16,844 圈，成功配對 16,792 圈；52 圈沒有 60 秒內的有效 `density_orbitmean`。CDF 正值缺值 `9.99e32` 依變數 `FILLVAL` 排除，不當成 density。

#### [P6.12] 三年 paired orbit series -> one global integral scale [retained]

```text
calc_phase6_l2_three_year_fit.py -> run()

每個 continuous block 由零開始：
K_j = sum_k rho_L2,k*sqrt(mu*a_k)*delta_t_k
Delta-a_POD,j = a_j-a_block_start

所有三年 cumulative points 共用：
beta_eff = -sum_j(K_j*Delta-a_POD,j)/sum_j(K_j^2)
Delta-a_L2,j = -beta_eff*K_j

chunk 改變或相鄰 orbit interval 不在 (0,6000] s 時切 block，不跨缺口積分。
```

```text
phase6_l2_three_year_pair_v1 (derived；引用上一步 key)
[
  {
    time_us: 1688178902000000 (us),
    mean_semi_major_axis_m: 6.859e6 (m),
    rho_l2_orbitmean_kg_m3: 5.693e-13 (kg/m^3),
    chunk_id: 11,
  },
  ...,
]
```

```text
phase6_l2_three_year_integral_v1 (derived；欄位節錄)
[
  {
    time_us: 1688184562000000 (us),
    interval_start_time_us: 1688178902000000 (us),
    block_index: 1,
    chunk_id: 11,
    cumulative_kernel_kg_m: 1.685e2 (kg/m),
    observed_cumulative_delta_a_m: 6.153e0 (m),
    beta_eff_m2_kg: 9.214e-3 (m^2/kg),
    predicted_cumulative_delta_a_m: -1.552e0 (m),
    predicted_a_m: 6.859e6 (m),
    residual_m: -7.705e0 (m),
    algorithm_version: phase6_l2_three_year_global_cumulative_fit_v1,
  },
  ...,
]

phase6_l2_three_year_fit_v1 (derived)
[
  {
    fit_id: all_three_year_cumulative_points,
    beta_eff_m2_kg: 9.214e-3 (m^2/kg),
    point_count: 16755,
    block_count: 35,
    mean_absolute_error_m: 2.078e1 (m),
    root_mean_square_error_m: 3.142e1 (m),
    mean_error_m: 4.898e-1 (m),
    algorithm_version: phase6_l2_three_year_global_cumulative_fit_v1,
  },
]
```

這是全三年 in-sample scale fit。L2 與 semi-major axis 都使用 POD 資訊；小 residual 不代表獨立密度驗證、物理 `C_D*A/m` 測量或 forecast skill。
