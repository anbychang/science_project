# Phase 2 SME 分鐘資料血緣

## 狀態與邊界

Phase 2 已結案 [done]。F10.7A 採 CelesTrak `F10.7_OBS_CENTER81`，不自行計算前 81 日平均。P2.3 v5、P2.4 v5、P2.5 v2 與 P2.6 final 是唯一交付檢查點；P2.6 是已完成的描述性 peak QC，不包含 local pulse pairing 或延遲標籤。置中 81 日值含樣本日之後的觀測，只能用於離線回溯分析，不能當即時預報特徵。交付證據見[最終報告](../plans/phase_2_density_validation/PHASE_2_FINAL_REPORT.md)。

現行檢查點位於 `data/sqlite/2023/`：P2.0 `swarm_a_phase2_sme_p2_0_v2.sqlite`、P2.1 `swarm_a_phase2_sme_p2_1_v2.sqlite`、P2.2 `swarm_a_phase2_sme_p2_2_v2.sqlite`、P2.3 `swarm_a_phase2_sme_p2_3_t0_phase_v5.sqlite`、P2.4 `swarm_a_phase2_sme_p2_4_density_t0_phase_v5.sqlite`、P2.5 `swarm_a_phase2_sme_p2_5_minute_analysis_v2.sqlite`、P2.6 `swarm_a_phase2_sme_p2_6_final.sqlite`。每一步複製上游 SQLite 後只新增 derived table 或 view；raw observation table 不更新。

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

P2.0 沒有 `time_us`；資料範圍是 2023-07-01 至 2026-06-30 UTC。P2.0 SQLite SHA-256 為 `5b6261af40f00ac2b0f3f70af1965b497f46bf1b9e4e7511e1f28d3c003ddf10`。

#### [P2.1] raw SME／SYM-H／AE -> 1-minute 指數 [done]

```text
prep_21_geomag_1min.py -> write_geomag_1min()

複製 P2.0；SME 999999 且 SMEnum 0、京都 99999 -> NULL；不內插、不改 SYM-H 正負號。
SME tval + 60 s 與京都中心戳 + 30 s 只記錄保守觀測完成界線，不是發布時刻。
```

```text
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
```

```text
geomag_1min_v2 (derived；欄位節錄)
[
  {
    time_us: 1688169600000000 (us),
    sme_nt: 7.471e1 (nT),
    sme_station_count: 121,
    symh_nt: -14 (nT),
    sme_not_before_time_us: 1688169660000000 (us),
    kyoto_not_before_time_us: 1688169630000000 (us)
  }
]
```

`time_us` 是來源分鐘 UTC 標籤。京都標籤是觀測區間中心；SME 標籤位置尚未獲來源確認。P2.1 有 1,578,240 列，其中有效 SME 1,499,195 列；缺值保持 NULL。P2.1 SQLite SHA-256 為 `9e2aad566d1fb75ead1974351ff3f9ac438474f633d1de98148c97778100ffdd`。

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
    symh_nt: -1.030e2 (nT)
  }
]
```

```text
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
  }
]
```

`t0_time_us` 是 SYM-H UTC 分鐘中心。P2.2 保留 1,758 個最低點，合併為 25 場，其中 24 場 `compound = 1`。這些是候選事件，尚未經 L2 覆蓋篩選。

#### [P2.3 v5] P2.2 t0 + Phase 1 u -> 置中 F10.7A 分鐘特徵 [done]

```text
prep_23_t0_phase_window.py -> write_t0_phase_minutes()

事件窗、分鐘鍵與 v4 相同。F10.7 取前一 UTC 日 F10.7_OBS；F10.7A 直接取樣本 UTC 日的 F10.7_OBS_CENTER81，不自行平均。
只接受來源日 F10.7_DATA_TYPE 為 OBS／INT、兩個數值皆為正且有限的列。PRD／PRM 不進入資料集。
```

```text
SW-All.csv (raw；2023-08-03 分鐘樣本所需的兩個來源日)
[
  {
    DATE: 2023-08-02,
    F10.7_OBS: 1.729e2 (sfu),
    F10.7_DATA_TYPE: OBS
  },
  {
    DATE: 2023-08-03,
    F10.7_OBS_CENTER81: 1.624e2 (sfu),
    F10.7_DATA_TYPE: OBS
  }
]
```

```text
storm_minute_feature_v5 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    source_time_us: 1691038920000000 (us),
    f107_sfu: 1.729e2 (sfu),
    f107a_sfu: 1.624e2 (sfu),
    algorithm_version: storm_minute_t0_phase_v5
  }
]
```

`source_time_us` 是 2023-08-03T05:02:00Z 的分鐘標籤。置中平均含樣本日之後的資料；不得當成預報時已知的值。25 場、217,912 列；SHA-256 為 `1dc9034ecb781a9bf444f95f7f8c401e7166615d0c7faa4ab19e8eac7a846a89`。

#### [P2.4 v5] DNSAPOD／MSIS -> 置中 F10.7A 分鐘密度 [done]

```text
prep_24_density_t0_phase.py -> write_density_minutes()

沿用 v4 的 30 s 配對、MSIS 2.0、缺值與 80% coverage 規則；模型 F10.7A 改用來源的 F10.7_OBS_CENTER81。
只寫新的 derived table，不更新 raw DNSAPOD 或舊密度表。
```

```text
storm_minute_feature_v5 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    source_time_us: 1691041080000000 (us),
    f107_sfu: 1.729e2 (sfu),
    f107a_sfu: 1.624e2 (sfu)
  }
]
```

```text
storm_density_1min_v5 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    source_time_us: 1691041080000000 (us),
    l2_valid_sample_count: 2,
    paired_sample_count: 2,
    rho_l2_kg_m3: 5.153e-13 (kg/m^3),
    rho_msis_kg_m3: 5.210e-13 (kg/m^3),
    log_ratio_obs: -1.098e-2,
    algorithm_version: storm_density_t0_phase_v5
  }
]
```

`source_time_us` 是 2023-08-03T05:38:00Z 的分鐘標籤。176 個 DNSAPOD 日檔產生 217,912 列；25 場 coverage 都通過。SHA-256 為 `5f5423b426ec0bd556f9e8f7378135b59ce9d3a1ae60f82f332f5b0e17493e7e`。

#### [P2.5 v2] 分鐘特徵 + 分鐘密度 -> 分析 view [done]

```text
prep_25_minute_analysis.py -> write_minute_analysis()

以 {storm_id, source_time_us} 一對一連接 v5 特徵與密度；只建立 view，不另算平均或峰值。
```

```text
storm_minute_feature_v5 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    source_time_us: 1691041080000000 (us),
    f107a_sfu: 1.624e2 (sfu)
  }
]

storm_density_1min_v5 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    source_time_us: 1691041080000000 (us),
    log_ratio_obs: -1.098e-2
  }
]
```

```text
storm_minute_analysis_v2 (derived view；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    source_time_us: 1691041080000000 (us),
    f107a_sfu: 1.624e2 (sfu),
    rho_msis_kg_m3: 5.210e-13 (kg/m^3),
    log_ratio_obs: -1.098e-2,
    algorithm_version: storm_minute_analysis_v2
  }
]
```

217,912 列、25 場；minute key mismatch 雙向均為 0。SHA-256 為 `fbabfaab3035fab2301e7da55d720692ec9659a210b9aa7949d74c616de9c0cd`。

#### [P2.6 final] 完整事件平滑 -> 限定候選窗 peak QC [done]

```text
prep_26_smoothed_peak_qc.py -> write_smoothed_peak_qc()

直接從 P2.5 v2 建立單一最終檢查點。SME 採 15-minute centered mean；密度採 u_rel_rad +/- pi centered one-orbit mean，窗口須完整且至少 80% 有效值。
只在 t0 - 12 h 至 t0 + 24 h 的閉區間取平滑最大值，同值取較早分鐘；SYM-H t0 保持原始最低點。這個 peak 候選窗小於 P2.3 的完整資料保存窗。
```

```text
storm_minute_analysis_v2 (derived view；欄位節錄)
[
  {
    storm_id: S20231105T1654,
    source_time_us: 1699198680000000 (us),
    sme_nt: 1.808e3 (nT),
    log_ratio_obs: 7.683e-1
  }
]
```

```text
storm_minute_smooth_v4 (derived；欄位節錄)
[
  {
    storm_id: S20231105T1654,
    source_time_us: 1699198680000000 (us),
    sme_smooth_nt: 1.884e3 (nT),
    log_ratio_smooth: 6.880e-1,
    algorithm_version: storm_minute_peak_qc_v4
  }
]

storm_minute_peak_qc_v4 (derived；欄位節錄)
[
  {
    storm_id: S20231105T1654,
    sme_peak_time_us: 1699198680000000 (us),
    density_peak_time_us: 1699208220000000 (us),
    sme_to_density_lag_h: 2.650e0 (h),
    algorithm_version: storm_minute_peak_qc_v4
  }
]
```

25 場、54,025 筆候選分鐘；16 場 SME 峰較早，9 場相反。`source_time_us` 沿用來源 UTC 分鐘中心標籤。`output/image/Phase2/P2.6/` 直接保存 25 張逐場圖，沒有圖版本子目錄。SHA-256 為 `ab49465ab672d98dd513c1169cb37c6fcb4488b98cade7b6ed66b151398c30de`。全域峰可能配錯脈衝，不能解讀為因果延遲。

