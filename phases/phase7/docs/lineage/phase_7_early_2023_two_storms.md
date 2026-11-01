# Phase 7 2023 年初兩場磁暴資料血緣

## 狀態與資料庫

狀態：[done: exploratory external-event validation]。

- Density SQLite：`phases/phase7/data/sqlite/swarm_a_phase7_density_v1.sqlite`
- Decay SQLite：`phases/phase7/data/sqlite/swarm_a_phase7_decay_v1.sqlite`

Phase 2／2R、Phase 3、Phase 4 V2、Phase 5 V2 與 Phase 6 都是唯讀來源。
Phase 7 只寫新的 derived table。`time_us` 是 UTC 分鐘錨點；兩場都是 compound storm。

#### [P7.0] Phase 0 raw source -> verified event and quiet-run files [done]

```text
down_phase7_dnsapod.py -> download_required_density()

Phase 2R event window + Phase 3 quiet-run rule -> required UTC days -> ESA DNSAPOD ZIP + SHA-256 manifest
```

```text
ESA DNSAPOD listing (raw index；欄位節錄)
[
  {
    name: SW_OPER_DNSAPOD_2__20230227T000000_20230227T235930_0301.ZIP,
    path: swarm/Level2daily/Entire_mission_data/DNS/POD/Sat_A/SW_OPER_DNSAPOD_2__20230227T000000_20230227T235930_0301.ZIP,
    size: 139786 (bytes)
  },
  ...
]
```

```text
manifest_dnsapod_early_2023_two_storms.json (raw index；files[] 欄位節錄)
[
  {
    name: SW_OPER_DNSAPOD_2__20230227T000000_20230227T235930_0301.ZIP,
    size_bytes: 139786,
    sha256: 3e77f30a1588ab82c67f9ebbeed76a084da67312f9557037282126fa6b901163
  },
  ...
]
```

Manifest 共 18 天。Phase 2R 已有 14 天；本步補入 quiet-run 所需的 2022-12-18、
2023-03-13、2023-05-17、2023-05-18。

#### [P7.1] Phase 1R mean elements -> complete POD minute means [done]

```text
calc_phase7_decay.py -> load_pod_minutes()

usable 10 s mean elements -> nearest UTC minute -> require one chunk and 6 samples -> mean semi-major axis
```

```text
swarm_a_mean_orbit_elements_v1 (derived；欄位節錄)
[
  {
    time_us: 1677328202000000,
    mean_semi_major_axis_m: 6.835e6 (m)
  },
  ...
]

swarm_a_pod_quality (derived；欄位節錄)
[
  {
    time_us: 1677328202000000,
    chunk_id: 10,
    is_usable: 1
  },
  ...
]
```

```text
phase7_decay_minute_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230227T1212,
    time_us: 1677328200000000,
    chunk_id: 10,
    mean_semi_major_axis_m: 6.835e6 (m)
  },
  ...
]
```

`1677328200000000` 是 2023-02-25T12:30:00Z 的分鐘錨點。

#### [P7.2] Phase 2R frozen event windows -> two-event snapshot [done]

```text
load_phase7_two_storms.py -> load_events()

fixed storm_id -> require Phase 2R event, phase window, 100% L2 coverage and 100% paired coverage
```

```text
storm_event_v2 (derived；欄位節錄)
[
  {
    storm_id: S20230227T1212,
    t0_time_us: 1677499920000000,
    symh_min_nt: -161 (nT)
  },
  ...
]

storm_event_coverage_v5 (derived；欄位節錄)
[
  {
    storm_id: S20230227T1212,
    l2_coverage: 1.000e0,
    paired_coverage: 1.000e0
  },
  ...
]
```

```text
phase7_density_event_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230227T1212,
    t0_time_us: 1677499920000000,
    symh_min_nt: -161 (nT),
    valid_phase_minutes: 8635
  },
  ...
]
```

#### [P7.3] Phase 3 quiet rule -> external-event quiet R and density [done]

```text
prep_phase7_density.py -> quiet_run_ratio() + phase_density_arrays()

12-year SME/ap -> nearest pre/post near-zero run -> native L2/quiet MSIS pairs -> median pre-event R
event native pairs -> centered u +/- pi phase density; require complete window and paired coverage >=80%
```

```text
storm_minute_feature_v5 (derived；欄位節錄)
[
  {
    storm_id: S20230227T1212,
    source_time_us: 1677328200000000,
    u_rel_rad: -1.916e2 (rad),
    paired_sample_count: 2
  },
  ...
]

SW_OPER_DNSAPOD_2_ (raw；欄位節錄)
[
  {
    time_us: 1677328170000000,
    rho_l2_kg_m3: 8.027e-13 (kg/m^3)
  },
  ...
]
```

```text
phase7_density_event_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230227T1212,
    r_phase3: 7.263e-1,
    r_post_diagnostic: 1.060e0,
    quiet_pre_density_coverage: 1.000e0
  },
  ...
]

phase7_density_minute_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230227T1212,
    time_us: 1677328200000000,
    rho_l2_phase_kg_m3: 1.098e-12 (kg/m^3),
    rho_msis_quiet_phase_kg_m3: 1.433e-12 (kg/m^3),
    rho_m0_full_phase_kg_m3: 1.472e-12 (kg/m^3)
  },
  ...
]
```

#### [P7.4] fixed Phase 4 V2 tau/G -> external retrospective R target [done]

```text
prep_phase7_density.py -> event_result()

tau=4.75 h + G=6.898e-4 1/nT -> centered phase H -> fit only event R against same-event L2
```

```text
Phase 4 V2 fixed parameters + Phase 7 L2/quiet density (derived；欄位節錄)
{
  tau_hours: 4.750e0 (h),
  gain_per_nt: 6.898e-4 (1/nT),
  storm_id: S20230227T1212
}
```

```text
phase7_density_event_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230227T1212,
    r_fit_external: 8.160e-1,
    fit_rmse_log_density: 2.387e-1
  },
  ...
]

phase7_density_minute_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230227T1212,
    time_us: 1677328200000000,
    h_phase_nt: 1.345e2 (nT),
    rho_fit_external_kg_m3: 1.283e-12 (kg/m^3)
  },
  ...
]
```

`r_fit_external` 使用同場 L2，只是外部事件回溯答案，不是預報輸入。

#### [P7.5] frozen Phase 5 V2 Ridge -> external R and density [done]

```text
load_phase7_two_storms.py -> ridge_prediction()
prep_phase7_density.py -> event_result()

fixed three factors + saved mean/scale/coefficient/intercept -> external R -> fixed Phase 4 V2 density equation
```

```text
Phase 5 V2 final_parameter + Phase 7 event factors (derived；欄位節錄)
{
  r_phase3: 7.263e-1,
  prequiet_sme_mean_nt: 7.560e1 (nT),
  quiet_f107a_last81_sfu: 1.329e2 (sfu)
}
```

```text
phase7_density_event_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230227T1212,
    r_ridge_external: 9.335e-1,
    ridge_rmse_log_density: 2.740e-1
  },
  ...
]

phase7_density_minute_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230227T1212,
    time_us: 1677328200000000,
    rho_ridge_external_kg_m3: 1.468e-12 (kg/m^3)
  },
  ...
]
```

新事件不參與因素選擇、標準化、係數或截距擬合。

#### [P7.6] fixed Phase 6 B_eff -> M0/Ridge decay comparison [done]

```text
calc_phase7_decay.py -> integrated_rows()

require 2 DNSAPOD samples and 6 POD samples -> exact minute join -> 60 s trapezoid -> reset at missing minute or chunk change -> event total
```

```text
phase7_density_minute_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230227T1212,
    time_us: 1677328200000000,
    rho_m0_full_phase_kg_m3: 1.472e-12 (kg/m^3),
    rho_ridge_external_kg_m3: 1.468e-12 (kg/m^3)
  },
  ...
]

phase6_1_beff_fit_v1 (derived；欄位節錄)
{
  beta_eff_m2_kg: 9.229e-3 (m^2/kg)
}
```

```text
phase7_decay_event_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230227T1212,
    paired_minute_count: 8635,
    block_count: 1,
    observed_covered_delta_a_m: -4.061e2 (m),
    predicted_m0_covered_delta_a_m: -4.760e2 (m),
    predicted_ridge_covered_delta_a_m: -4.570e2 (m),
    closer_model: ridge
  },
  ...
]
```

`B_eff` 沿用 Phase 6 三年 in-sample fit。這是 density-to-decay closure，不是獨立 drag
propagation，也沒有 quiet counterfactual。
