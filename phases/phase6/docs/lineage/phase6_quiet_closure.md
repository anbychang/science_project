# Phase 6 平靜期經驗閉合資料血緣

狀態：[retained]。本步是舊的平靜窗方法，不是目前 P6.1。輸出是本機 `phases/phase6/data/sqlite/swarm_a_phase6_quiet_closure_v4.sqlite`。

#### [P6.retained-quiet] 平靜期 orbit-density pairs -> 留一窗經驗閉合 [retained]

```text
calc_phase6_quiet_closure.py -> run()

每個 `selection_status=candidate` 窗的前六圈與後六圈各作線性擬合，得到兩端的 candidate mean semi-major axis 差 `observed_delta_a_m`。
相鄰圈以左端 DNSAPOD `rho_l2_orbitmean_kg_m3` 積分 rho*sqrt(mu*a)*delta_t；圈距必須在 (0, 6000] s。
若觀測差為負，建立該窗的經驗尺度。留出一窗時，尺度取其他下降且與被留出窗時間不重疊的窗之中位數，再預測被留出窗的 `predicted_delta_a_m`。
```

```text
phase6_quiet_orbit_pair_v1 (derived；Phase 6 平靜期稽核；欄位節錄)
[
  {
    window_id: Q20230910,
    time_us: 1694308752000000 (us),
    mean_semi_major_axis_m: 6.857e6 (m),
    rho_l2_orbitmean_kg_m3: 7.605e-13 (kg/m^3),
  },
  ...,
]
```

```text
phase6_quiet_closure_window_v4 (derived；欄位節錄)
[
  {
    window_id: Q20230910,
    first_time_us: 1694308752000000 (us),
    last_time_us: 1694472852000000 (us),
    observed_delta_a_m: -4.859e1 (m),
    density_kernel_kg_m: 6.909e3 (kg/m),
    empirical_scale_m2_kg: 7.033e-3 (m^2/kg),
    calibration_window_count: 9,
    predicted_delta_a_m: -6.784e1 (m),
    prediction_error_m: -1.925e1 (m),
    status: evaluated,
  },
  ...,
]
```

`first_time_us` 與 `last_time_us` 是候選窗可配對第一圈與最後一圈的 UTC 時刻。`empirical_scale_m2_kg` 只由該窗的 candidate mean-element 下降量反推，用於留一窗比較；它不是 Swarm 的已校準 ballistic coefficient。
