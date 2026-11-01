# Phase 7 三事件批次資料血緣

狀態：[done]。輸出位於 `phases/phase7/runs/three_storms/data/sqlite/`；Phase 2R、Phase 1R、
Phase 4 V2、Phase 5 V2 與 Phase 6 一律唯讀。事件鍵是 `{storm_id, time_us}`，時間
均為 UTC。五場共同計分另存於 `phases/phase7/data/sqlite/`。

#### [P7.0] ESA DNSAPOD -> verified raw manifest [done]

```text
down_phase7_dnsapod.py -> download_required_density()

三場 phase window 與 Phase 3 pre/post quiet run 的 UTC 日檔 -> ESA 檔案大小、ZIP 結構與 SHA-256 核對 -> manifest
```

```text
SW_OPER_DNSAPOD_2__20221107T000000_20221107T235930_0301.ZIP (raw；欄位節錄)
[
  {
    size_bytes: 140015,
    sha256: 448fbc1e4a62a720d46027409e1db1d5b272f6ee982018bf803df7e021443539,
  },
  ...,
]
```

```text
manifest_dnsapod_late_2022_early_2023_three_storms.json (derived；欄位節錄)
[
  {
    name: SW_OPER_DNSAPOD_2__20221107T000000_20221107T235930_0301.ZIP,
    source_path: swarm/Level2daily/Entire_mission_data/DNS/POD/Sat_A/SW_OPER_DNSAPOD_2__20221107T000000_20221107T235930_0301.ZIP,
  },
  ...,
]
```

manifest 有 27 個 UTC 日檔；2022-10-26 與 2022-11-15 是第三場的 quiet 日檔。

#### [P7.1] Phase 1R mean elements -> complete POD minute means [done]

```text
calc_phase7_decay.py -> load_pod_minutes()

可用 10 s mean elements -> 最近 UTC 分鐘；只保留單一 chunk_id 且剛好 6 個樣本的分鐘 -> mean semi-major axis
```

```text
swarm_a_mean_orbit_elements_v1 (derived；欄位節錄)
[
  {
    time_us: 1667669702000000 (us),
    mean_semi_major_axis_m: 6.840e6 (m),
  },
  ...,
]
```

```text
phase7_decay_minute_v1 (derived；欄位節錄)
[
  {
    storm_id: S20221107T1720,
    time_us: 1667669700000000 (us),
    chunk_id: 8,
    mean_semi_major_axis_m: 6.840e6 (m),
  },
  ...,
]
```

`time_us=1667669700000000` 是 2022-11-05T17:35:00Z 的分鐘錨點；`chunk_id` 是不可跨越的
Phase 1R 連續資料段。

#### [P7.2] frozen Phase 2R event windows -> selected event snapshot [done]

```text
load_phase7_two_storms.py -> load_events()

指定 storm_id -> 要求 event、phase window、100% L2 coverage 與 100% paired coverage -> 三場 metadata
```

```text
storm_event_v2 (derived；欄位節錄)
[
  {
    storm_id: S20221107T1720,
    t0_time_us: 1667841600000000 (us),
    symh_min_nt: -117 (nT),
  },
  ...,
]
```

```text
phase7_density_event_v1 (derived；欄位節錄)
[
  {
    storm_id: S20221107T1720,
    t0_time_us: 1667841600000000 (us),
    valid_phase_minutes: 8644,
  },
  ...,
]
```

#### [P7.3] Phase 3 quiet rule -> quiet R and quiet density [done]

```text
prep_phase7_density.py -> select_quiet_runs() + quiet_run_ratio()

12-year SME/ap -> 最近 pre/post near-zero run；原生 L2 與 quiet MSIS 配對 -> pre-event R 的中位數
```

```text
storm_event_v2 (derived；欄位節錄)
[
  {
    storm_id: S20221107T1720,
    t0_time_us: 1667841600000000 (us),
  },
]
```

```text
phase7_density_event_v1 (derived；欄位節錄)
[
  {
    storm_id: S20221107T1720,
    quiet_pre_start_time_us: 1666758540000000 (us),
    r_phase3: 7.977e-1,
    r_post_diagnostic: 7.374e-1,
  },
]
```

near-zero 規則是 `ap<=4`、`SME<=100 nT`、所有 0–10 h 的 0.25 h 間隔濾波結果距 65 nT 不超過
25 nT，且連續至少 90 分鐘。quiet MSIS 使用同時間與位置，但七欄 `ap=4`。

#### [P7.4] fixed Phase 4 V2 tau/G -> retrospective R_fit density [done]

```text
prep_phase7_density.py -> event_result()

固定 tau=4.75 h、G 與 Phase 3 quiet density -> 中心 u±pi 相位平均 -> 同場 L2 回溯 R_fit
```

```text
phase7_density_event_v1 (derived；欄位節錄)
[
  {
    storm_id: S20221107T1720,
    r_fit_external: 1.006e0,
    fit_rmse_log_density: 1.475e-1,
  },
]
```

```text
phase7_density_minute_v1 (derived；欄位節錄)
[
  {
    storm_id: S20221107T1720,
    time_us: 1667669700000000 (us),
    h_phase_nt: 1.473e2 (nT),
    rho_l2_phase_kg_m3: 8.835e-13 (kg/m^3),
  },
  ...,
]
```

`R_fit` 使用同場 L2，只能作 retrospective answer，不是預報輸入。

#### [P7.5] frozen Phase 5 V2 Ridge -> external Ridge density [done]

```text
prep_phase7_density.py -> ridge_prediction()

{r_phase3, prequiet_sme_mean_nt, quiet_f107a_last81_sfu} + frozen standardization/coefficients -> R_ridge -> density
```

```text
phase7_density_event_v1 (derived；欄位節錄)
[
  {
    storm_id: S20221107T1720,
    r_ridge_external: 9.216e-1,
    ridge_minus_fit_r: -8.463e-2,
  },
]
```

```text
phase7_density_minute_v1 (derived；欄位節錄)
[
  {
    storm_id: S20221107T1720,
    time_us: 1667669700000000 (us),
    rho_ridge_external_kg_m3: 6.633e-13 (kg/m^3),
  },
  ...,
]
```

Ridge 沒有讀取三場新事件的 `R_fit`、重新選因素或重訓。

#### [P7.6] fixed Phase 6 B_eff -> POD/density decay closure [done]

```text
calc_phase7_decay.py -> integrated_rows()

完整 density/POD 分鐘 join -> 60 s trapezoid；缺分鐘或 chunk 改變時重設積分 -> event total
```

```text
phase7_density_minute_v1 (derived；欄位節錄)
[
  {
    storm_id: S20221107T1720,
    time_us: 1667669700000000 (us),
    rho_m0_full_phase_kg_m3: 7.620e-13 (kg/m^3),
  },
  ...,
]
```

```text
phase7_decay_event_v1 (derived；欄位節錄)
[
  {
    storm_id: S20221107T1720,
    paired_minute_count: 8644,
    observed_covered_delta_a_m: -1.986e2 (m),
    predicted_m0_covered_delta_a_m: -1.952e2 (m),
    predicted_ridge_covered_delta_a_m: -1.951e2 (m),
  },
  ...,
]
```

固定 `B_eff` 只提供 descriptive density-to-decay closure，不是完整 atmospheric-drag propagator。
