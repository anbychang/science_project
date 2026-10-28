# Phase 2R 12 年同方法重現資料血緣

## 狀態與路徑

Phase 2R 於 2026-10-25 完成。範圍是
`2014-07-01T00:00:00Z <= time < 2026-07-01T00:00:00Z`，原樣重現已封存的
Phase 2 final 方法。新檢查點位於 `research_workspace/phases/phase2r/data/sqlite/`；`research_workspace/phases/phase2/data/sqlite/`
的 Phase 2 檢查點不是本鏈的寫入目標。

```text
P2R.0 -> P2R.1 -> P2R.2 -> P2R.3 -> P2R.4 -> P2R.5 -> P2R.6
source     geomag    storms    phase     density   view      peak QC
```

#### [P2R.0] 12 年 raw source -> 來源稽核檢查點 [done]

```text
prep_2r0_source_audit.py -> write_source_audit()
prep_2r0_source_checkpoint.py -> write_source_checkpoint()

SME 逐日 hash／分鐘格 + Kyoto SYM-H／AE + GFZ ap + CelesTrak -> 內嵌 audit JSON
不補值；SME 來源填充值計入 invalid minute。
```

```text
research_workspace/phases/phase0/data/raw/sme/SME_20150317.csv (raw；UTC；欄位節錄)
[
  {
    tval: 1426632420 (s),
    SME: 9.715e2 (nT),
    SMEnum: 147
  },
  ...
]
```

```text
source_audit_v2 (derived；欄位節錄)
[
  {
    audit_sha256: 9ed2dcd2cfac86ec622c94f2b33dfd9e561aaa2a95206190c6fbe9219e4d2f2b,
    algorithm_version: source_audit_12year_v1
  }
]
```

P2R.0 稽核 4,383 天、6,311,520 個分鐘格。SYM-H 與 AE 各有
6,311,520 個觀測分鐘；SME 有 79,045 個 invalid minute。SQLite SHA-256 為
`db72986f74f27450044c925c652d75cc701e7553908ef3a9e5b5f27c13d067d8`。

#### [P2R.1] 來源稽核 + raw geomagnetic -> 1-minute 地磁 [done]

```text
prep_2r1_geomag_1min.py -> write_geomag_1min()

P2R.0 固定範圍 -> 只選 manifest 中 2014-07-01 至 2026-06-30 的 SME 日檔
Kyoto 重疊列必須數值與 version 一致；缺值保留 NULL，不內插。
```

```text
source_audit_v2 (derived；以 audit_sha256 為 key)
[
  {
    audit_sha256: 9ed2dcd2cfac86ec622c94f2b33dfd9e561aaa2a95206190c6fbe9219e4d2f2b,
    algorithm_version: source_audit_12year_v1
  }
]
```

```text
geomag_1min_v2 (derived；UTC 分鐘標籤；欄位節錄)
[
  {
    time_us: 1426632420000000 (us),
    sme_nt: 9.715e2 (nT),
    sme_station_count: 147,
    sme_valid: 1,
    symh_nt: -234 (nT),
    ae_nt: 331 (nT),
    sme_not_before_time_us: 1426632480000000 (us),
    kyoto_not_before_time_us: 1426632450000000 (us),
    algorithm_version: geomag_1min_raw_v2
  },
  ...
]
```

P2R.1 有 6,311,520 列，其中 6,232,475 列 SME 有效。SQLite SHA-256 為
`723439b466da2dd7ff601d325b15e20a24c816101b129a569b147be97abea87e`。

#### [P2R.2] 1-minute SYM-H -> 12 年事件 [done]

```text
prep_22_storm_event.py -> write_storm_events()

重用 Phase 2 final `storm_event_symh_v2`：SYM-H < -100 nT 局部最小值
72 小時內合併；事件視窗仍記錄 t0 - 48 h 至 t0 + 96 h。
```

```text
geomag_1min_v2 (derived；欄位節錄)
[
  {
    time_us: 1426632420000000 (us),
    symh_nt: -234 (nT)
  },
  ...
]
```

```text
storm_event_v2 (derived；欄位節錄)
[
  {
    storm_id: S20150317T2247,
    t0_time_us: 1426632420000000 (us),
    symh_min_nt: -234 (nT),
    window_start_time_us: 1426412220000000 (us),
    window_end_time_us: 1427012280000000 (us),
    compound: 1,
    n_minima: 93,
    algorithm_version: storm_event_symh_v2
  },
  ...
]
```

2,461 個 local minima 合併為 49 場事件，46 場 `compound = 1`。SQLite SHA-256
為 `4d3d2d00da0a962576448a19e0c55456d32f86543c0ab6cbb6781182509b055f`。

#### [P2R.3] 事件 t0 + Phase 1 u -> 同相位分鐘窗 [done]

```text
prep_2r3_t0_phase_window.py -> write_t0_phase_minutes()

重用 Phase 2 final 相位內插與分鐘 feature；t0 前 31 圈、後 62 圈
只用包含 t0 的單一連續 chunk_id；不跨缺口，窗口不足時記入 exclusion table。
```

```text
storm_event_v2 (derived；欄位節錄)
[
  {
    storm_id: S20150317T2247,
    t0_time_us: 1426632420000000 (us)
  },
  ...
]
```

```text
swarm_a_mean_orbit_elements_v1 (derived；欄位節錄)
[
  {
    time_us: 1426632420000000 (us),
    mean_semi_major_axis_m: 6.830e6 (m)
  },
  ...
]
```

```text
swarm_a_pod_quality (raw；欄位節錄)
[
  {
    time_us: 1426632420000000 (us),
    chunk_id: 2
  },
  ...
]
```

```text
storm_event_t0_phase_v5 (derived；欄位節錄)
[
  {
    storm_id: S20150317T2247,
    t0_time_us: 1426632420000000 (us),
    phase_t0_rad: 2.424e2 (rad),
    phase_orbits_before: 31,
    phase_orbits_after: 62
  },
  ...
]
```

```text
storm_minute_feature_v5 (derived；欄位節錄)
[
  {
    storm_id: S20150317T2247,
    source_time_us: 1426632420000000 (us),
    t_rel_h: 0.000e0 (h),
    u_rel_rad: 0.000e0 (rad),
    mean_semi_major_axis_m: 6.830e6 (m),
    raw_3_rate_m_s: 8.921e-4 (m/s),
    raw_5_rate_m_s: -7.339e-4 (m/s),
    joint_3_rate_m_s: -7.594e-4 (m/s),
    joint_5_rate_m_s: -1.219e-3 (m/s),
    sme_nt: 9.715e2 (nT),
    symh_nt: -2.340e2 (nT)
  },
  ...
]
```

46 場事件產生 400,696 分鐘列。3 場分別因 t0 前相位不足、t0 後相位不足、
t0 沒有連續相位而寫入 `storm_event_phase_exclusion_p2r_v1`。SQLite SHA-256 為
`b5d37b2f03dcc393df1fc46e40814899e62d2ee287fc8e33a68b4b1b9ab48b20`。

#### [P2R.4] DNSAPOD + NRLMSIS -> 分鐘密度 [done]

```text
down_2r4_dnsapod.py -> download_required_density()
prep_24_density_t0_phase.py -> write_density_minutes()

只下載 P2R.3 事件分鐘觸及的 324 個 UTC 日
DNSAPOD 原生 30 秒位置／時間 -> NRLMSIS 2.0 -> 同分鐘配對；L2 與 paired coverage 各 >= 80%。
```

```text
manifest_dnsapod_phase2r_event_days.json (raw 索引；files[] 欄位節錄)
[
  {
    name: SW_OPER_DNSAPOD_2__20150317T000000_20150317T235930_0301.ZIP,
    size_bytes: 140293,
    sha256: 826a755d50825f532d8fc4aba5980d20216f647de9a25b56d52a1fe8964c5f12
  },
  ...
]
```

```text
storm_density_1min_v5 (derived；欄位節錄)
[
  {
    storm_id: S20150317T2247,
    source_time_us: 1426632420000000 (us),
    rho_l2_kg_m3: 2.430e-12 (kg/m^3),
    rho_msis_kg_m3: 1.443e-12 (kg/m^3),
    rho_l2_orbitmean_kg_m3: 2.518e-12 (kg/m^3),
    log_ratio_obs: 5.214e-1
  },
  ...
]
```

```text
storm_event_coverage_v5 (derived；欄位節錄)
[
  {
    storm_id: S20150317T2247,
    l2_coverage: 9.725e-1,
    paired_coverage: 9.725e-1,
    is_valid_80pct: 1,
    status: used
  },
  ...
]
```

324 個日檔有 933,120 個 30 秒樣本。46 場全數通過，最低 L2 與 paired coverage
均為 `9.345e-1`。400,696 列中 399,365 列 `log_ratio_obs` 有效。SQLite SHA-256 為
`3a0c5ffb103808b521cd480401c99bc935376fe07e125503e42a4bf3034143b9`。

#### [P2R.5] 分鐘 feature + 分鐘密度 -> 分析 view [done]

```text
prep_25_minute_analysis.py -> write_minute_analysis()

{storm_id, source_time_us} 一對一連接 P2R.3 與 P2R.4
只建 SQL view；不平滑、不取 peak、不複製分鐘列。
```

```text
storm_minute_feature_v5 (derived；join key)
[
  {
    storm_id: S20150317T2247,
    source_time_us: 1426632420000000 (us)
  },
  ...
]
```

```text
storm_density_1min_v5 (derived；join key)
[
  {
    storm_id: S20150317T2247,
    source_time_us: 1426632420000000 (us)
  },
  ...
]
```

```text
storm_minute_analysis_v2 (derived view；欄位節錄)
[
  {
    storm_id: S20150317T2247,
    source_time_us: 1426632420000000 (us),
    sme_nt: 9.715e2 (nT),
    symh_nt: -2.340e2 (nT),
    log_ratio_obs: 5.214e-1
  },
  ...
]
```

view 有 400,696 列、46 場；雙向 minute key mismatch 都是 0。SQLite SHA-256 為
`2eb117bd77af53d90f34d120db25fae770a89e69f8e6423189a97a530f3e4448`。

#### [P2R.6] 分析 view -> 平滑 peak QC [done]

```text
prep_26_smoothed_peak_qc.py -> write_smoothed_peak_qc()

重用 Phase 2 final：SME 15-minute centered mean；density 用 u_rel_rad +/- pi centered one-orbit mean
完整窗且有效比例 >= 80%；只在 t0 - 12 h 至 t0 + 24 h 取最大值。
```

```text
storm_minute_analysis_v2 (derived view；欄位節錄)
[
  {
    storm_id: S20150317T2247,
    source_time_us: 1426632420000000 (us),
    t_rel_h: 0.000e0 (h),
    sme_nt: 9.715e2 (nT),
    log_ratio_obs: 5.214e-1
  },
  ...
]
```

```text
storm_minute_smooth_v4 (derived；欄位節錄)
[
  {
    storm_id: S20150317T2247,
    source_time_us: 1426632420000000 (us),
    sme_smooth_nt: 9.835e2 (nT),
    log_ratio_smooth: 4.673e-1
  },
  ...
]
```

```text
storm_minute_peak_qc_v4 (derived；欄位節錄)
[
  {
    storm_id: S20150317T2247,
    sme_peak_t_rel_h: -9.150e0 (h),
    density_peak_t_rel_h: -7.850e0 (h),
    sme_to_density_lag_h: 1.300e0 (h),
    sme_precedes_density: 1
  },
  ...
]
```

99,406 個候選分鐘中，SME 平滑值有效 99,406 列，density 平滑值有效
98,946 列。46 場中 33 場 SME peak 較早，13 場反序。反序只是描述性 QC，
不是負延遲證據。SQLite SHA-256 為
`d201583de003713a28f9fd1276d33ac45ea247af5e0634d7c3f608115b43c42e`。

`research_workspace/phases/phase2r/figures/P2R.6/` 有 46 張 `YYYY-MM-DD.png`，與 46 場 QC 的 UTC t0 日期
一對一，無缺圖、重複日期或額外圖檔。
