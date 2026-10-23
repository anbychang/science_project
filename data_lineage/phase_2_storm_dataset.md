# Phase 2 SME 分鐘資料血緣

## 狀態與邊界

現行三年主線已完成 P2.0–P2.4、P2.5 每圈地磁摘要及 P2.6 峰值時序稽核。P2.3 v2 的鐘錶時間窗口保留作歷史檢查點，不是 P2.4 的輸入。唯一的方法規格見 `plans/phase_2_density_validation/PHASE_2_SME_REPORT.md`。

Phase 2 檢查點位於 `data/sqlite/2023/`：P2.0 `swarm_a_phase2_sme_p2_0_v2.sqlite`、P2.1 `swarm_a_phase2_sme_p2_1_v2.sqlite`、P2.2 `swarm_a_phase2_sme_p2_2_v2.sqlite`、歷史 P2.3 v2 `swarm_a_phase2_sme_p2_3_minute_v2.sqlite`、現行 P2.3 v3 `swarm_a_phase2_sme_p2_3_full_orbit_v3.sqlite`、P2.4 v3 `swarm_a_phase2_sme_p2_4_density_v3.sqlite`、P2.5 `swarm_a_phase2_sme_p2_5_geomag_orbit_v1.sqlite`、P2.6 `swarm_a_phase2_sme_p2_6_peak_order_v1.sqlite`。P2.0–P2.4 逐步複製前一 SQLite；P2.5、P2.6 各是獨立的精簡 derived SQLite，以 metadata SHA-256 鎖定來源。P2.4 `storm_catalog_v3` 與 P2.6 `storm_peak_order_v1` 是正式表，不另存衍生 CSV。原始 CSV／ZIP、Phase 1 與舊檢查點不覆寫。

#### [P2.0] 來源稽核 JSON -> SQLite 檢查點 [done]

```text
prep_20_source_checkpoint.py -> write_source_checkpoint()

已稽核 JSON -> 封存完整原文與 SHA-256；不重寫原始 CSV，不產生分鐘觀測列。
```

```text
phase2_p2_0_source_audit.json (derived；欄位節錄)
{
  date_range_utc: [2023-07-01, 2026-06-30],
  sme: {
    valid_minutes: 1499195,
    invalid_minutes: 79045
  }
}
```

```text
source_audit_v2 (derived；欄位節錄)
[
  {
    audit_sha256: db225aaf7b2007ffffce64fd425af766f408e920f6e332e45821231c1ee323e3,
    algorithm_version: source_audit_v2
  }
]
```

完整 `audit_json` 存於同列；P2.0 SQLite SHA-256 為 `5b6261af40f00ac2b0f3f70af1965b497f46bf1b9e4e7511e1f28d3c003ddf10`。本步無 `time_us`：來源稽核的 UTC 範圍是 `2023-07-01` 至 `2026-06-30`，分鐘 key 從 P2.1 才開始。

#### [P2.1] raw SME／SYM-H／AE -> 1-minute 指數 [done]

```text
prep_21_geomag_1min.py -> write_geomag_1min()

複製 P2.0 SQLite；以封存的來源稽核 SHA-256 鎖定 CSV；同分鐘京都重疊檔已在 P2.0 確認值與版本一致。
SME 999999 且 SMEnum 0、京都 99999 -> NULL；不內插、不改 SYM-H 正負號。
SME tval + 60 s 與京都中心戳 + 30 s 僅作保守觀測完成界線，非發布時刻。
```

```text
source_audit_v2 (derived；欄位節錄)
[
  {
    audit_sha256: db225aaf7b2007ffffce64fd425af766f408e920f6e332e45821231c1ee323e3,
    algorithm_version: source_audit_v2
  }
]

SME_20230701.csv (raw；欄位節錄)
{
  tval: 1688169600 (s),
  SME: 7.471e1 (nT),
  SMEnum: 121
}

sym_h_2023-01-01_2023-12-31.csv (raw；欄位節錄)
{
  Time: 2023-07-01T00:00:00Z,
  symHValue: -14 (nT),
  versionCode: 10
}

ae_2023-01-01_2023-12-31.csv (raw；欄位節錄)
{
  Time: 2023-07-01T00:00:00Z,
  aeValue: 51 (nT),
  versionCode: 0
}
```

```text
geomag_1min_v2 (derived；欄位節錄)
[
  {
    time_us: 1688169600000000 (us),
    sme_nt: 7.471e1 (nT),
    sme_station_count: 121,
    sme_valid: 1,
    symh_nt: -14 (nT),
    symh_version: 10,
    ae_nt: 51 (nT),
    ae_version: 0,
    sme_not_before_time_us: 1688169660000000 (us),
    kyoto_not_before_time_us: 1688169630000000 (us)
  },
  ...
]
```

`time_us` 沿用來源分鐘的 UTC 標籤；京都標籤是觀測區間中心，SME 標籤位置未獲來源確認。P2.3 暫按同樣中心語意對齊，但不宣稱兩者測量窗口完全相同。實存 1,578,240 列；有效 SME 1,499,195 列，SYM-H／AE 各 1,578,240 列。其餘 79,045 列 SME 保留為 NULL，未補值。P2.0 缺口詳見 `phase2_p2_0_source_audit.json`；P2.1 metadata 記錄輸入 P2.0 SQLite 的 SHA-256。P2.1 SQLite SHA-256 為 `9e2aad566d1fb75ead1974351ff3f9ac438474f633d1de98148c97778100ffdd`。

#### [P2.2] 1-minute SYM-H -> 合併事件 [done]

```text
prep_22_storm_event.py -> write_storm_events()

只用未內插 SYM-H < -100 nT 的局部最低點；同值平台取最早分鐘，缺口兩側不跨越。
相鄰最低點 < 72 h 先群組；各最低點 [t - 48 h, t + 96 h) 窗口相交則再合併。
最深最低點為 t0，同深度取較早者；所有最低點保留在 storm_minimum_v2。
```

```text
geomag_1min_v2 (derived；欄位節錄)
[
  {
    time_us: 1691214360000000 (us),
    symh_nt: -103 (nT),
    symh_version: 10
  },
  ...
]
```

```text
storm_minimum_v2 (derived；欄位節錄)
[
  {
    minimum_time_us: 1691214360000000 (us),
    symh_min_nt: -103 (nT),
    storm_id: S20230805T0546,
    merge_reason: representative
  },
  ...
]

storm_event_v2 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    t0_time_us: 1691214360000000 (us),
    symh_min_nt: -103 (nT),
    window_start_time_us: 1691041080000000 (us),
    window_end_time_us: 1691562540000000 (us),
    compound: 1,
    n_minima: 6
  },
  ...
]
```

`minimum_time_us`／`t0_time_us` 都是 SYM-H 的 UTC 分鐘中心；窗口是左閉右開。P2.2 保留 1,758 個最低點，合併為 25 場，其中 24 場 `compound = 1`。P2.2 metadata 記錄輸入 P2.1 SHA-256；P2.2 SQLite SHA-256 為 `55e726b9bbf2bd0469e1f316bf2b81d80a05b752ea0b950ecaff56efb2585eb7`。這些是未經 L2／SME 覆蓋篩選的候選，不是最終可用事件。

#### [P2.3 v2] Phase 1 mean orbit／u／衰減率 + 分鐘指數 -> 鐘錶窗口每分鐘特徵 [retained]

```text
prep_23_minute_features.py -> write_minute_features()

複製 P2.2 SQLite；對每場窗口的每個 UTC 分鐘保留一列，沿用 P2.1 的 SME、SYM-H 原值，不在本步補缺。
以 P2.1 來源 UTC 整分標籤為 target；名義時間支持區間取 [標籤 - 30 s, 標籤 + 30 s)。這與京都 SYM-H 的中心戳相符；SME `tval` 暫比照處理，仍是未經 SuperMAG 確認的假設。前後 Phase 1 10 s mean elements 同 chunk、皆可用且間距 <= 20 s 時，線性內插 mean semi-major axis 與圓周相位 u。u = (mean_argument_of_perigee_rad + mean_anomaly_rad) modulo 2pi，跨 2pi/0 時走短角距。
Phase 1 raw B-L、joint H2/H3 的 3 圈、5 圈回溯衰減率取 target 以前的左端 10 s 列，保留各自速率、1sigma、樣本數與拒絕原因；不跨缺口外推，也不選單一方法。
跨 u=0 的前後 10 s POD 內插圈界；只把完整、同 chunk 的相位圈連到分鐘。整圈 phase-weighted mean 是事後摘要，來源圈尾時間另存；不可當成分鐘 target 時已知的 predictor。
ap 取分鐘標籤前最後已完成的 3 h 區間；F10.7 用前一日 OBS。`core_ready_time_us` 是分鐘指數和相位來源的保守觀測完成界線，不含整圈 mean；不代表官方資料發布時刻。
```

```text
storm_event_v2 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    t0_time_us: 1691214360000000 (us),
    window_start_time_us: 1691041080000000 (us),
    window_end_time_us: 1691562540000000 (us)
  },
  ...
]

geomag_1min_v2 (derived；欄位節錄)
[
  {
    time_us: 1691041080000000 (us),
    sme_nt: 1.536e2 (nT),
    symh_nt: -2.000e0 (nT)
  },
  ...
]

swarm_a_mean_orbit_elements_v1 (derived；來源標籤前後 10 s，欄位節錄)
[
  {
    time_us: 1691041072000000 (us),
    mean_semi_major_axis_m: 6.858e6 (m),
    mean_argument_of_perigee_rad: -5.473e0 (rad),
    mean_anomaly_rad: 3.068e0 (rad)
  },
  {
    time_us: 1691041082000000 (us),
    mean_semi_major_axis_m: 6.858e6 (m),
    mean_argument_of_perigee_rad: -5.462e0 (rad),
    mean_anomaly_rad: 3.069e0 (rad)
  }
]

swarm_a_phase_orbit_mean_v2 (derived；欄位節錄)
[
  {
    time_us: 1691043232000000 (us),
    orbit_start_time_us: 1691037582000000 (us),
    phase_weighted_mean_semi_major_axis_m: 6.858e6 (m),
    chunk_id: 11
  },
  ...
]

swarm_a_phase_harmonic_decay_raw_b_l_sets_v2 (derived；欄位節錄)
[
  {
    time_us: 1691041072000000 (us),
    orbit_3_decay_rate_m_s: 1.948e-4 (m/s),
    orbit_5_decay_rate_m_s: -3.782e-4 (m/s)
  },
  ...
]

swarm_a_phase_harmonic_decay_joint_h2_h3_sets_v2 (derived；欄位節錄)
[
  {
    time_us: 1691041072000000 (us),
    orbit_3_decay_rate_m_s: -2.336e-4 (m/s),
    orbit_5_decay_rate_m_s: -5.739e-4 (m/s)
  },
  ...
]
```

```text
storm_minute_feature_v2 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    source_time_us: 1691041080000000 (us),
    assumed_support_start_time_us: 1691041050000000 (us),
    assumed_support_end_time_us: 1691041110000000 (us),
    target_time_us: 1691041080000000 (us),
    sme_nt: 1.536e2 (nT),
    symh_nt: -2.000e0 (nT),
    mean_semi_major_axis_m: 6.858e6 (m),
    orbit_phase_u_rad: 3.887e0 (rad),
    phase_left_time_us: 1691041072000000 (us),
    phase_right_time_us: 1691041082000000 (us),
    orbit_id: 1691043232000000,
    phase_weighted_orbit_mean_a_m: 6.858e6 (m),
    orbit_mean_source_end_time_us: 1691043232000000 (us),
    decay_source_time_us: 1691041072000000 (us),
    raw_3_rate_m_s: 1.948e-4 (m/s),
    raw_5_rate_m_s: -3.782e-4 (m/s),
    joint_3_rate_m_s: -2.336e-4 (m/s),
    joint_5_rate_m_s: -5.739e-4 (m/s),
    ap_step: 5.000e0,
    f107_sfu: 1.729e2 (sfu),
    f107a_sfu: 1.661e2 (sfu),
    t_rel_h: -4.813e1 (h),
    core_ready_time_us: 1691041140000000 (us),
    chunk_id: 11,
    algorithm_version: storm_minute_feature_v2
  },
  ...
]
```

`source_time_us` 是 P2.1 的來源 UTC 分鐘標籤，也是軌道 `target_time_us`。樣本的來源標籤與 target 均為 2023-08-03 05:38:00 UTC，名義支持區間為 05:37:30–05:38:30 UTC。`assumed_support_*` 是 P2.3 的模型假設，不是 P2.1 原始欄位，也不是 SME 來源方已確認的觀測區間。`orbit_id` 沿用 Phase 1 完整圈表的 `time_us` key，即該圈最後一筆 POD epoch；圈界另存 `orbit_start_time_us`／`orbit_end_time_us`。

25 場候選共 280,055 分鐘，280,055 列有相位與完整圈連結，四種 rate 皆有值；`phase_status` 全為 `interpolated`，沒有跨 chunk 補值。四種 rate 是 Phase 1 既有估計，可能正也可能負，本步不截斷。279,924 列的整圈 mean 來源時間晚於分鐘 target，這一欄只供事後描述；分鐘因果模型只能使用已達觀測完成界線的局部 mean axis、rate 和驅動量。`core_ready_time_us` 保留 P2.1 的 SME 標籤 + 60 s 保守界線，不含整圈 mean，也不能推斷外部檔案的實際發布時間。

P2.3 SQLite SHA-256 為 `0aa7021f92a6b7d89272a11980f60df309a72a765f04c9db60d301f2f0b170a3`；metadata 記錄 P2.2、Phase 1、GFZ、CelesTrak SHA-256 及兩種指數的時間語意。SQLite integrity 與 foreign key 檢查通過。重現時執行 `python -m satellite_orbit.phase2.prep_23_minute_features P2_2_DB PHASE1_DB GFZ_JSON SOLAR_CSV NEW_OUTPUT_DB`；新輸出路徑必須不存在。這仍是未經 L2 覆蓋篩選的候選事件分鐘表，沒有完成延遲核、密度比或實測軌道衰減標籤。

#### [P2.3 v3] 事件候選 + Phase 1 完整圈 -> 完整圈每分鐘檢查點 [done]

```text
prep_23_full_orbit.py -> write_full_orbit_minutes()

複製 P2.2；包含 t0 的相位圈為第 0 圈，取前 31 圈與後 61 圈，共 93 個完整圈。
若兩場的完整圈集合相交，按聯集合併；代表 t0 取較深 SYM-H 最低點，同深度取較早者。
用 P2.3 v2 的相同分鐘對齊、u、mean axis、四種回溯 rate 與天氣規則重新建表；不裁半圈。
```

```text
storm_event_v2 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    t0_time_us: 1691214360000000 (us),
    symh_min_nt: -103 (nT)
  },
  ...
]

swarm_a_phase_orbit_mean_v2 (derived；欄位節錄)
[
  {
    time_us: 1691043232000000 (us),
    phase_weighted_mean_semi_major_axis_m: 6.858e6 (m),
    chunk_id: 11
  },
  ...
]

geomag_1min_v2 (derived；欄位節錄)
[
  {
    time_us: 1691041080000000 (us),
    sme_nt: 1.536e2 (nT),
    symh_nt: -2.000e0 (nT)
  },
  ...
]
```

```text
storm_event_full_orbit_v3 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    t0_time_us: 1691214360000000 (us),
    symh_min_nt: -103 (nT),
    window_start_time_us: 1691037578044234 (us),
    window_end_time_us: 1691563961046782 (us),
    compound: 1,
    n_minima: 6,
    n_orbits: 93,
    algorithm_version: storm_minute_feature_v3
  },
  ...
]

storm_event_orbit_v3 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    orbit_id: 1691043232000000,
    orbit_index: 0,
    orbit_start_time_us: 1691037578044234 (us),
    orbit_end_time_us: 1691043238214418 (us),
    phase_weighted_mean_semi_major_axis_m: 6.858e6 (m),
    chunk_id: 11,
    algorithm_version: storm_minute_feature_v3
  },
  ...
]

storm_minute_feature_v3 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    source_time_us: 1691041080000000 (us),
    target_time_us: 1691041080000000 (us),
    orbit_id: 1691043232000000,
    sme_nt: 1.536e2 (nT),
    symh_nt: -2.000e0 (nT),
    mean_semi_major_axis_m: 6.858e6 (m),
    orbit_phase_u_rad: 3.887e0 (rad),
    raw_3_rate_m_s: 1.948e-4 (m/s),
    raw_5_rate_m_s: -3.782e-4 (m/s),
    joint_3_rate_m_s: -2.336e-4 (m/s),
    joint_5_rate_m_s: -5.739e-4 (m/s),
    t_rel_h: -4.813e1 (h),
    algorithm_version: storm_minute_feature_v3
  },
  ...
]
```

`t0_time_us` 是 SYM-H 來源 UTC 分鐘中心；`source_time_us` 是來源 UTC 分鐘標籤，範例為 2023-08-03T05:38:00Z；`orbit_id` 是 Phase 1 圈尾 POD epoch key。窗口為圈界左閉右開。選圈時以含 `t0` 的圈為相對第 0 圈；儲存欄位 `orbit_index` 則從窗口第一圈編 0–92，含 `t0` 的圈為 31。三年共有 25 場、2,325 個不重複完整圈、217,912 個分鐘列；這批事件的完整圈窗口沒有新增重疊合併。P2.3 v3 SQLite SHA-256 為 `acda2fac9710dc076b0128c491b7f78a0c3d5fb4966e4860153e8b5c33a43599`；SQLite integrity 與 foreign key 檢查通過。這是描述性事件來源，不是衰減標籤。

#### [P2.4 v3] 完整圈分鐘 + DNSAPOD／MSIS -> 分鐘密度與覆蓋率 [done]

```text
prep_24_density_minute.py -> write_density_minutes()

複製 P2.3 v3；逐檔核對三年 DNSAPOD manifest、ZIP SHA-256 及 baseline 0301。
validity_flag = 0 且有限正值的 density 才算主 L2；density_orbitmean 單獨保留，不能代填。
在每個 L2 原生 30 s 時刻及位置計算 MSIS 2.0；F10.7 用前一日 OBS，F10.7A 用此前完整 81 個 OBS 日，ap 用已完成 3 h 區間及歷史。缺 weather 或模型值保留缺值。
原生樣本按 [來源分鐘標籤 - 30 s, 標籤 + 30 s) 彙整；比值為 ln(同組配對 L2 平均 / 同組配對 MSIS 平均)。不另存 30 s 衍生表。
每圈以預期 30 s 時點為分母：L2 與配對覆蓋率各 >= 80% 才合格。每場以不重複完整圈為分母，合格圈 >= 80% 才標 used；93 圈至少 75 圈。
```

```text
storm_minute_feature_v3 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    source_time_us: 1691041080000000 (us),
    orbit_id: 1691043232000000,
    sme_nt: 1.536e2 (nT)
  },
  ...
]

manifest_dnsapod_20230701_20260630.json (derived；欄位節錄)
{
  collection: SW_OPER_DNSAPOD_2_,
  verified_at_utc: 2026-10-22T17:49:46.091195+00:00,
  files: [
    {
      name: SW_OPER_DNSAPOD_2__20230803T000000_20230803T235930_0301.ZIP,
      sha256: ec5874a8a4ee05eaa98b5aa572ba8da47010b23360b980477002bbafe1ecb6bc
    }
  ]
}

SW_OPER_DNSAPOD_2__20230803T000000_20230803T235930_0301.ZIP (raw CDF；欄位節錄)
[
  {
    time_us: 1691041080000000 (us),
    density: 5.129e-13 (kg/m^3),
    density_orbitmean: 6.966e-13 (kg/m^3),
    latitude: -4.300e1 (deg),
    longitude: -1.363e2 (deg),
    altitude: 5.010e5 (m),
    validity_flag: 0
  },
  ...
]
```

```text
storm_density_1min_v3 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    source_time_us: 1691041080000000 (us),
    orbit_id: 1691043232000000,
    l2_valid_sample_count: 2,
    paired_sample_count: 2,
    orbitmean_valid_sample_count: 2,
    rho_l2_kg_m3: 5.153e-13 (kg/m^3),
    rho_msis_kg_m3: 5.376e-13 (kg/m^3),
    rho_l2_orbitmean_kg_m3: 6.968e-13 (kg/m^3),
    log_ratio_obs: -4.227e-2,
    algorithm_version: storm_density_1min_v3
  },
  ...
]

storm_orbit_coverage_v3 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    orbit_id: 1691043232000000,
    expected_30s_sample_count: 188,
    l2_valid_sample_count: 188,
    paired_sample_count: 188,
    l2_coverage: 1.000e0,
    paired_coverage: 1.000e0,
    is_valid: 1,
    algorithm_version: storm_density_1min_v3
  },
  ...
]

storm_catalog_v3 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    t0_time_us: 1691214360000000 (us),
    symh_min_nt: -103 (nT),
    compound: 1,
    n_orbits: 93,
    n_valid_orbits: 93,
    orbit_coverage: 1.000e0,
    status: used,
    algorithm_version: storm_density_1min_v3
  },
  ...
]
```

DNSAPOD `time_us` 是 CDF `time` 解碼後的 UTC 觀測時刻；範例為 2023-08-03T05:38:00Z。`source_time_us` 沿用 P2.3 v3 的 UTC 分鐘標籤。`orbit_id` 仍是 Phase 1 圈尾 POD epoch key。三年 175 個事件涉及日檔共有 504,000 筆來源樣本；輸出 217,912 個分鐘列、2,325 個圈列與 25 個事件列。

有效 L2 原生圈內樣本 435,220／預期 435,830；成功配對 365,664。分鐘表的對應合計為 435,202 與 365,648；少的 18／16 筆是圈邊界原生樣本，其四捨五入分鐘鍵不在 P2.3 選取分鐘內。圈覆蓋率用原生圈內樣本，P2.6 密度比用分鐘表；兩種計數不可直接當成相同母體，邊界規則待下個版本統一。

21 場為 `used`，4 場為 `excluded_coverage`。4 場的 L2 覆蓋仍約 99–100%，配對覆蓋為 0，原因是 81 日歷史窗碰到 CelesTrak `INT` 非 `OBS` 日；此處不放寬已定來源契約。P2.4 SQLite SHA-256 為 `4fc0085035f268fc8fd3ec6798856018760ee5eb2cc43a50873f13e20118e214`；SQLite integrity 與 foreign key 檢查通過。密度比仍是描述性比較，DNSAPOD 與 Phase 1 POD 軌道量同源，不構成獨立衰減驗證。

#### [P2.5] 每分鐘 SME／SYM-H -> 每圈地磁摘要 [done]

```text
prep_25_geomag_orbit.py -> write_geomag_orbit()

P2.4 內的 P2.3 v3 分鐘列 -> 同一 storm_id、orbit_id 分組 -> 每圈 Q、SYM-H 與 SMEnum。
預期分鐘以完整圈 [start, end) 內的 UTC 整分中心為分母；SME、SYM-H 各 >= 80% 才標 is_valid。
dsymh_dt = (本圈 symh_mean - 前一圈 symh_mean) / 兩圈中點時間差；首圈或任一圈無效時為 NULL，不跨事件。
三年事件窗口沒有 SME／SYM-H 缺分鐘；本步不做指數內插，P2.3 原值不改。
```

```text
storm_minute_feature_v3 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    source_time_us: 1691041080000000 (us),
    orbit_id: 1691043232000000,
    sme_nt: 1.536e2 (nT),
    symh_nt: -2.000e0 (nT),
    sme_station_count: 117
  },
  ...
]

storm_event_orbit_v3 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    orbit_id: 1691043232000000,
    orbit_start_time_us: 1691037578044234 (us),
    orbit_end_time_us: 1691043238214418 (us)
  },
  ...
]
```

```text
storm_geomag_orbit_v1 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    orbit_id: 1691043232000000,
    t_mid_time_us: 1691040408129326 (us),
    expected_minute_count: 94,
    minute_count: 94,
    sme_valid_count: 94,
    symh_valid_count: 94,
    sme_coverage: 1.000e0,
    symh_coverage: 1.000e0,
    q_sme_nt: 1.832e2 (nT),
    symh_mean_nt: -3.489e0 (nT),
    dsymh_dt_nt_h: null,
    sme_station_count_mean: 1.170e2,
    is_valid: 1,
    algorithm_version: storm_geomag_orbit_v1
  },
  ...
]
```

`source_time_us` 是來源 UTC 分鐘標籤；`t_mid_time_us` 是相位圈兩個內插圈界的中點，範例為 2023-08-03T05:26:48.129326Z。`orbit_id` 沿用 Phase 1 圈尾 key。三年 25 場共 2,325 圈，SME／SYM-H 分鐘覆蓋率均為 100%，全部 `is_valid = 1`；事件窗口測站數範圍 71–133。首圈導數為 NULL。P2.5 SQLite SHA-256 為 `c0221fe1f7c368aa1f25b753d2105bcc6d0956e12f7b7964c278e7cc8a41a005`；metadata 記錄 P2.4 SHA-256。

#### [P2.6] 每圈 SME／密度差 + SYM-H t0 -> 峰值時序稽核 [done]

```text
prep_26_peak_order.py -> write_peak_order()

只查 P2.4 status = used 的事件；每圈 Q 與同組配對密度比的自然對數在 [t0 - 24 h, t0 + 24 h] 各取最大值。
以 P2.5 圈中點標記兩個峰；同值取較早圈。expected_order = 1 僅當 SME 峰 < 密度差峰 < 精確 SYM-H t0。
這是描述性時序稽核，不是事件篩選、物理因果證據或延遲模型的訓練標籤。
```

```text
storm_catalog_v3 (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    t0_time_us: 1715393640000000 (us),
    symh_min_nt: -518 (nT),
    compound: 1,
    status: used
  },
  ...
]

storm_geomag_orbit_v1 (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    orbit_id: 1715440202000000,
    t_mid_time_us: 1715437384874999 (us),
    q_sme_nt: 2.613e3 (nT),
    is_valid: 1
  },
  ...
]

storm_density_1min_v3 (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    source_time_us: 1715434620000000 (us),
    orbit_id: 1715440202000000,
    paired_sample_count: 2,
    rho_l2_kg_m3: 3.827e-12 (kg/m^3),
    rho_msis_kg_m3: 4.262e-12 (kg/m^3)
  },
  ...
]
```

```text
storm_peak_order_v1 (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    t0_time_us: 1715393640000000 (us),
    sme_peak_time_us: 1715437384874999 (us),
    density_peak_time_us: 1715397875507548 (us),
    sme_peak_t_rel_h: 1.215e1 (h),
    density_peak_t_rel_h: 1.177e0 (h),
    sme_to_density_lag_h: -1.097e1 (h),
    expected_order: 0,
    algorithm_version: storm_peak_order_v1
  },
  ...
]
```

P2.6 三個 `time_us` 都是 UTC 時刻：`t0` 為 SYM-H 來源分鐘中心，兩個峰為完整相位圈中點。範例 t0 是 2024-05-11T02:14:00Z；SME 峰在 14:23:04.874999Z，密度差峰在 03:24:35.507548Z。21 場密度合格事件中，只有 5 場符合這個嚴格峰值順序；20 場為複合事件，因此不能把「取整段最大值」等同單一能量脈衝的物理延遲。P2.6 SQLite SHA-256 為 `3172340c4a38a98aca462afead59c3eb9f055d422fc8f760029c421244045465`；metadata 記錄 P2.4 與 P2.5 SHA-256。逐場 UTC 日期命名圖存於 `output/image/Phase2/P2.6/`，共 21 張 PNG；峰值時刻與相對時間以本表為準。其中的「密度峰」明確指 `ln(L2/MSIS)` 的峰，不是原始 L2 密度峰。原有 F2-3 案例與總覽圖仍位於 `output/image/`。

