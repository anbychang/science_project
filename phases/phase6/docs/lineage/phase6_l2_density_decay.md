# Phase 6 L2 density -> semi-major-axis decay 資料血緣

狀態：[retained]。本步把 Phase 5 保存的 25 場 Swarm L2 centered one-orbit density 轉成候選半長軸下降。它使用 2024 quiet windows 擬合比例，已由不選窗口的三年全域方法取代；輸出保留作歷史比較，不再是現行判定輸入。

#### [P6.10] L2 centered orbit density -> `beta_eff` candidate decay [done]

```text
calc_phase6_l2_density_decay.py -> run()

Phase 5 每個 L2 anchor -> Phase 1 u=unwrap(omega+M) -> 同一 [u-pi,u+pi] window 的 phase-weighted mean a
2024 三個 quiet closure windows -> zero-intercept OLS -> beta_eff=9.793e-3 m^2/kg
每圈 da/dt=-beta_eff*rho*sqrt(mu*a)；乘同圈 phase-window period得到 delta-a。

只在同一 usable chunk 內插 phase boundary。每圈至少 500 個 source samples、phase coverage 為 2*pi、最大 POD gap 不超過 10 s。相鄰 phase grid 缺圈時切開 cumulative block，不跨缺圈積分。
```

```text
phase5_orbit_anchor (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691044560000000 (us),
    u_rel_rad: -1.885e2 (rad),
    rho_l2_phase_kg_m3: 6.728e-13 (kg/m^3),
  },
  ...,
]

swarm_a_mean_orbit_elements_v1 + swarm_a_pod_quality (derived；欄位節錄)
[
  {
    time_us: 1691041729954173 (us；interpolated window boundary),
    chunk_id: 11,
    mean_semi_major_axis_m: 6.858e6 (m),
  },
  ...,
]

phase6_quiet_closure_window_v4 (derived；固定 calibration rows)
[
  {
    window_id: Q20240202,
    observed_delta_a_m: -8.254e1 (m),
    density_kernel_kg_m: 8.405e3 (kg/m),
  },
  ...,
]
```

```text
phase6_l2_decay_orbit_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691044560000000 (us),
    phase_grid: -30,
    window_start_time_us: 1691041729954173 (us),
    window_stop_time_us: 1691047390068724 (us),
    rho_l2_phase_kg_m3: 6.728e-13 (kg/m^3),
    mean_semi_major_axis_m: 6.858e6 (m),
    orbit_period_s: 5.660e3 (s),
    beta_eff_m2_kg: 9.793e-3 (m^2/kg),
    predicted_decay_rate_m_day: -2.976e1 (m/day),
    predicted_orbit_delta_a_m: -1.950e0 (m),
    source_sample_count: 566,
    phase_coverage_rad: 6.283e0 (rad),
    maximum_pod_gap_s: 1.000e1 (s),
    chunk_id: 11,
    algorithm_version: phase6_l2_centered_orbit_beta_eff_v1,
  },
  ...,
]

phase6_l2_decay_event_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    first_time_us: 1691044560000000 (us),
    last_time_us: 1691559600000000 (us),
    accepted_orbit_count: 92,
    rejected_anchor_count: 0,
    block_count: 1,
    predicted_delta_a_m: -1.872e2 (m),
    observed_delta_a_m: -1.994e2 (m),
    prediction_error_m: 1.223e1 (m),
    algorithm_version: phase6_l2_centered_orbit_beta_eff_v1,
  },
  ...,
]
```

`time_us` 是 Phase 5 UTC minute anchor；`window_start_time_us` 與 `window_stop_time_us` 是 Phase 1 在同一 centered phase window 的插值邊界。2,295 個 anchors 全部通過 Phase 1 window gate；`phase6_l2_decay_reject_v1` 目前為空。

此輸出是 total candidate decay，不是 storm-excess decay。`beta_eff` 由 L2 quiet density 與 Phase 1 candidate decay 擬合，L2 本身也由 POD aerodynamic acceleration 反算；因此 event error 只作 retrospective closure，不能稱為獨立物理驗證或 forecast。
