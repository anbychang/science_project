# Phase 3 三年 25 場磁暴資料血緣

## 狀態與資料邊界

P3.1–P3.6 的主線結果與適用範圍見[Phase 3 結案報告](../../reports/phase_3_final_report.md)。本文件另記 P3.7–P3.12 診斷的 Input／Output；[Phase 3 計畫](../plans/PLAN.md)保留結案前的決策歷史。

狀態：[done]。25 場都有固定共同 $\tau=4.65$ 小時的回溯密度曲線；$R_k$ 已依最終採用的低活動段規則完成校準。Phase 2／2R 檢查點唯讀。Phase 3 不是 Phase 2 檢查點的 working copy，而是讀取 `phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_6_final.sqlite` 後，寫入九個獨立的衍生庫：

- `phases/phase3/data/sqlite/swarm_a_phase3_h_tau_phase_v1.sqlite`
- `phases/phase3/data/sqlite/swarm_a_phase3_quiet_density_v1.sqlite`
- `phases/phase3/data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite`
- `phases/phase3/data/sqlite/swarm_a_phase3_event_gain_tau465_diagnostic_v1.sqlite`
- `phases/phase3/data/sqlite/swarm_a_phase3_m0_ap_alignment_v1.sqlite`
- `phases/phase3/data/sqlite/swarm_a_phase3_tau_extended_diagnostic_v1.sqlite`
- `phases/phase3/data/sqlite/swarm_a_phase3_m2_residual_diagnostic_v1.sqlite`
- `phases/phase3/data/sqlite/swarm_a_phase3_m1a_zero_sme_v1.sqlite`
- `phases/phase3/data/sqlite/swarm_a_phase3_m1a_event_tau_v1.sqlite`

`r_candidate`、`r_near_zero_median_candidate` 與 `provisional_R_exploratory` 是產出時保存的欄名或狀態值；本 phase 已採用這套低活動段規則作為最終操作性 $R_k$，資料欄名不代表研究仍未結案。

前三個庫及第五個庫的分鐘表以 `{storm_id, time_us}` 為 key；逐場總覽、增益診斷及 M0 校正摘要以 `storm_id` 為 key，均保留各自的 `algorithm_version`。`time_us` 是 UTC 分鐘標籤；相位平均的數值以該分鐘為中心，使用前後 $u\pm\pi$ 的樣本。25 場事件起自 2023-08-05 至 2026-04-18。完整來源與已凍結的 Phase 2 步驟見 [Phase 2 lineage](../../../phase2/docs/lineage/phase_2_storm_dataset.md)。

```text
P2.6 final -> P3.1 最終 R_k 校準
          -> P3.2 SME 連續濾波與相位平均
DNSAPOD + weather -> P3.3 平靜 MSIS／L2 同樣本配對
P3.1 + P3.2 + P3.3 -> P3.4 共同 tau／G
                    -> P3.5 固定 tau 的逐分鐘密度曲線
                    -> P3.6 25 場索引與總覽
                    -> P3.7 固定共同 tau 的逐場 G 幅度診斷
DNSAPOD + weather + P2.6 -> P3.8 無擬合的 M0 Ap 歷史對齊
P2.6 + P3.3 + 已採用 R_k -> P3.9 七場延長 tau 診斷
P3.8 + P3.5 的 SME 響應 -> P3.10 M2 完整 MSIS 殘差診斷
P2.6 + P3.3 + 原事前窗口 -> P3.11 M1A 零 SME 基準與共同擬合
                              -> P3.12 M1A 逐場 tau 診斷
```

#### [P3.1] 暴前低活動段 -> 最終 $R_k$ [done]

```text
prep_phase3_rquiet_near_zero.py -> main()

連續 1-minute SME - 65 nT -> 41 個 tau=0..10 h 的濾波響應。
GFZ 3-hour ap 按原生時段對齊至分鐘，不把階梯值當獨立觀測。
候選分鐘須觀測 ap<=4、SME<=100 nT、全部 41 個 |H_tau|<=25 nT；連續至少 90 分鐘。
以第一個強 SYM-H 低點前最近的候選段，取同分鐘 L2／固定 ap=4 的 MSIS 密度比中位數。
```

```text
geomag_1min_v2 (derived；低活動段起點；欄位節錄)
[
  {
    time_us: 1714456800000000 (us),
    sme_nt: 4.601e+1 (nT),
    symh_nt: -4 (nT),
    sme_valid: 1
  },
  ...
]

phases/phase0/data/raw/geomagnetic/gfz_ap_2023-07-01_2026-06-30.json (raw；同索引 2434；欄位節錄)
{
  datetime: [2024-04-30T06:00:00Z],
  ap: [0.000e+0]
}

storm_event_t0_phase_v5 (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    t0_time_us: 1715393640000000 (us),
    symh_min_nt: -518 (nT)
  },
  ...
]

phases/phase0/data/raw/swarm_density_pod/SW_OPER_DNSAPOD_2__20240430T000000_20240430T235930_0301.ZIP (raw；load_dnsapod 解碼樣本；欄位節錄)
[
  {
    time_us: 1714456800000000 (us),
    rho_l2_kg_m3: 3.675e-13 (kg/m^3),
    latitude_deg: -7.945e+1 (deg),
    longitude_deg: 1.734e+1 (deg),
    altitude_m: 5.004e+5 (m)
  },
  ...
]
```

```text
phases/phase3/data/analysis/phase3_rquiet_near_zero_25.csv (analysis；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    near_zero_start_utc: 2024-04-30T06:00:00+00:00,
    near_zero_end_exclusive_utc: 2024-04-30T11:03:00+00:00,
    run_minutes: 303,
    r_near_zero_median_candidate: 6.462e-1,
    distance_before_first_minimum_days: 1.034e+1 (d),
    status: candidate_within_14d
  },
  ...
]
```

`1714456800000000` 是 2024-04-30T06:00:00Z 的觀測分鐘；該列是 303 分鐘採用段的起點。25 場都有最終 $R_k$，但只有 20 個不同暴前段；10 場的段落距第一個強低點超過 14 天，最遠 74.9 天。實際選用的 $\tau=4.65$ 小時在這 25 個採用段內最大 $|H_\tau|$ 為 23.64 nT。$R_k$ 取原生分鐘密度比的中位數，是本 phase 的最終平靜校準操作定義；它不是已驗證的事前 Forecast 輸入。

#### [P3.2] 連續 SME -> $u\pm\pi$ 相位響應 [done]

```text
prep_h_tau_phase.py -> main()

全時段 1-minute SME -> H_tau,j = alpha H_tau,j-1 + (1-alpha)(SME_j-65 nT)，alpha=exp[-1/(60 tau_h)]。
tau=0 時 H_0=SME-65 nT；事件間不重設。先濾波，再按分鐘錨點 u±pi 與 L2 原生配對數 0/1/2 加權平均。
只在相位窗口完整且配對樣本覆蓋至少 80% 時保存有效值；原有缺口不補成觀測。
```

```text
geomag_1min_v2 (derived；欄位節錄)
[
  {
    time_us: 1715393640000000 (us),
    sme_nt: 1.665e+3 (nT),
    sme_valid: 1
  },
  ...
]

storm_minute_feature_v5 (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    source_time_us: 1715393640000000 (us),
    u_rel_rad: 0.000e+0 (rad)
  },
  ...
]
```

```text
phase3_h_tau_minute (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    time_us: 1715393640000000 (us),
    paired_sample_count: 2,
    phase_paired_coverage: 1.000e+0,
    phase_is_valid_80pct: 1,
    h_phase_tau_00_nt: 1.877e+3 (nT),
    h_phase_tau_19_nt: 1.628e+3 (nT),
    algorithm_version: phase3_h_tau_phase_v1
  },
  ...
]
```

`1715393640000000` 是 2024-05-11T02:14:00Z 的事件 $t_0$ 分鐘。欄位索引 19 代表 $\tau=19/4=4.75$ 小時；本表的 41 點格線沒有 4.65 小時。25 場共 217,912 個分鐘錨點，其中 214,907 個有效、3,005 個無效；後者仍保留原始 key 與有效性標記。逐分鐘遞迴只讀當下與過去 SME；中心相位平均另外讀取錨點之後的濾波值，因此相位輸出本身不具因果預報性。

#### [P3.3] 原生 L2／MSIS -> 同樣本相位密度 [done]

```text
prep_quiet_msis.py -> main()

DNSAPOD 原生 30-second L2／POD 與 Phase 2 weather -> 七欄 ap 全固定 4 的 NRLMSIS 2.0。
F10.7 用前一 UTC 日實際值；F10.7A 用當日置中 81 日值。
只對同時有 L2 的原生樣本配對，再依 P3.2 相同的 u±pi 及配對數平均 L2、平靜 MSIS 和完整 MSIS。
```

```text
phases/phase0/data/raw/swarm_density_pod/SW_OPER_DNSAPOD_2__20240511T000000_20240511T235930_0301.ZIP (raw；load_dnsapod 解碼樣本；欄位節錄)
[
  {
    time_us: 1715393640000000 (us),
    rho_l2_kg_m3: 4.046e-12 (kg/m^3),
    latitude_deg: -8.735e+1 (deg),
    longitude_deg: -1.675e+1 (deg),
    altitude_m: 5.007e+5 (m)
  },
  ...
]

storm_minute_feature_v5 (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    source_time_us: 1715393640000000 (us),
    f107_sfu: 2.234e+2 (sfu),
    f107a_sfu: 1.771e+2 (sfu)
  },
  ...
]

storm_density_1min_v5 (derived；L2 與完整 MSIS 核對；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    source_time_us: 1715393640000000 (us),
    paired_sample_count: 2,
    rho_l2_kg_m3: 4.047e-12 (kg/m^3),
    rho_msis_kg_m3: 2.720e-12 (kg/m^3)
  },
  ...
]
```

```text
phase3_quiet_density_minute (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    time_us: 1715393640000000 (us),
    rho_l2_phase_kg_m3: 4.455e-12 (kg/m^3),
    rho_msis_quiet_phase_kg_m3: 1.702e-12 (kg/m^3),
    rho_msis_full_phase_kg_m3: 3.338e-12 (kg/m^3),
    log_l2_over_quiet_phase: 9.621e-1,
    phase_is_valid_80pct: 1,
    algorithm_version: phase3_quiet_density_v1
  },
  ...
]
```

原生分鐘密度與相位密度不可混用；同一 `time_us` 的相位列含前後約一圈資料。176 個 DNSAPOD 日檔產生 217,912 個鍵，435,214 個原生配對樣本；相位有效標記與 P3.2 全鍵一致。F10.7A 含未來資料。

#### [P3.4] 25 場密度異常 -> 共用 $\tau,G$ [done]

```text
prep_exploratory_fit.py -> main()
prep_tau_refinement.py -> main()

對每個有效相位錨點，z=ln(rho_L2,phase/rho_MSIS,q,phase)-ln(R_k)。
連續 1-minute SME 重新計算 tau=0,0.05,...,10 h 共 201 條 H_tau，再各取相同 u±pi 平均。
每條格點以 G=sum(zH)/sum(H^2) 過原點擬合；選 25 場全部有效分鐘的最小對數密度 RMSE。
```

```text
geomag_1min_v2 (derived；欄位節錄)
[
  {
    time_us: 1715393640000000 (us),
    sme_nt: 1.665e+3 (nT),
    sme_valid: 1
  },
  ...
]

phase3_h_tau_minute (derived；相位配對定義；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    time_us: 1715393640000000 (us),
    phase_is_valid_80pct: 1
  },
  ...
]

phase3_quiet_density_minute (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    time_us: 1715393640000000 (us),
    log_l2_over_quiet_phase: 9.621e-1,
    phase_is_valid_80pct: 1
  },
  ...
]

phases/phase3/data/analysis/phase3_rquiet_near_zero_25.csv (analysis；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    r_near_zero_median_candidate: 6.462e-1
  },
  ...
]
```

```text
phases/phase3/data/analysis/phase3_tau_grid_005h_exploratory.csv (analysis；欄位節錄)
[
  {
    tau_hours: 4.650e+0 (h),
    gain_per_nt: 7.032e-4 (1/nT),
    train_rmse_log_density: 2.065e-1,
    fit_minutes: 214907,
    status: provisional_R_exploratory
  },
  ...
]
```

201 點的共同最低值為 $\tau=4.65$ 小時、$G=0.0007032326071208369\,\mathrm{nT}^{-1}$；5% RMSE 範圍 1.95–9.25 小時。41 個與原格線重合的點逐點核對。這是同一批資料的訓練最低點，不是逐場 $\tau_k$ 的平均，也不是精確的物理延遲。

#### [P3.5] 固定共同 $\tau$ -> 逐分鐘密度曲線 [done]

```text
prep_prediction_tau465.py -> main()

H_4.65,phase + 同樣本平靜 MSIS + 已採用 R_k -> rho_M1=rho_MSIS,q,phase * R_k * exp(G H_4.65,phase)。
另固定共同 tau，對每一場只排除該場對 G 的估計，產生 G-excluded 曲線；tau 仍由全部 25 場選出。
完整 MSIS M0 原始相位曲線一起保存供診斷，不在此步作公平勝負宣稱。
```

```text
phase3_quiet_density_minute (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    time_us: 1715393640000000 (us),
    rho_l2_phase_kg_m3: 4.455e-12 (kg/m^3),
    rho_msis_quiet_phase_kg_m3: 1.702e-12 (kg/m^3)
  },
  ...
]

phases/phase3/data/analysis/phase3_tau_grid_005h_exploratory.csv (analysis；欄位節錄)
[
  {
    tau_hours: 4.650e+0 (h),
    gain_per_nt: 7.032e-4 (1/nT)
  },
  ...
]

phases/phase3/data/analysis/phase3_rquiet_near_zero_25.csv (analysis；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    r_near_zero_median_candidate: 6.462e-1
  },
  ...
]
```

```text
phase3_prediction_minute (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    time_us: 1715393640000000 (us),
    h_phase_nt: 1.637e+3 (nT),
    rho_l2_phase_kg_m3: 4.455e-12 (kg/m^3),
    rho_msis_quiet_phase_kg_m3: 1.702e-12 (kg/m^3),
    rho_msis_full_phase_kg_m3: 3.338e-12 (kg/m^3),
    rho_m1_pooled_phase_kg_m3: 3.479e-12 (kg/m^3),
    rho_m1_held_out_phase_kg_m3: 3.557e-12 (kg/m^3),
    algorithm_version: phase3_prediction_tau465_exploratory_v1
  },
  ...
]
```

25 場共 214,907 列，所有密度為正。全樣本 M1 的對數密度 RMSE 為 0.20651751524484063，與 P3.4 訓練格點差小於 $10^{-15}$。排除單場估 $G$ 的曲線按分鐘合併 RMSE 為 0.2105。此處明確定義的是「相位平均平靜密度乘上相位平均響應的指數」，一般不等於「先在每個原生樣本算 M1 密度、再取相位平均」；兩者差異尚未驗證。中心相位窗、置中 F10.7A、事後事件界線選出的 $R_k$，以及以全部事件選出的 $\tau$，都使這份輸出只能稱回溯試算；$\tau=4.65$ 小時本身不提供 4.65 小時的預報提前量。

#### [P3.6] 逐分鐘預測 -> 25 場索引與總覽 [done]

```text
prep_25storm_overview.py -> main()

以 storm_id 連接 P2 事件、P3 已採用 R_k 與固定 tau 的逐場誤差，寫入預測 SQLite 的獨立 25 場索引表。
逐場核對索引表的有效分鐘數與逐分鐘預測列數。
25 格圖按各場 t0 排列，只為檢查 L2／M0／M1 曲線；M0 未獲與 M1 同等的暴前倍率校準。
```

```text
phase3_prediction_minute (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    time_us: 1715393640000000 (us),
    rho_l2_phase_kg_m3: 4.455e-12 (kg/m^3),
    rho_m1_held_out_phase_kg_m3: 3.557e-12 (kg/m^3)
  },
  ...
]

storm_event_t0_phase_v5 (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    t0_time_us: 1715393640000000 (us),
    symh_min_nt: -518 (nT)
  },
  ...
]

phases/phase3/data/analysis/phase3_prediction_tau465_exploratory.csv (analysis；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    valid_minutes: 8653,
    m1_held_out_rmse_log_density: 2.129e-1,
    full_rmse_log_density: 4.764e-1
  },
  ...
]

phases/phase3/data/analysis/phase3_rquiet_near_zero_25.csv (analysis；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    distance_before_first_minimum_days: 1.034e+1 (d),
    r_near_zero_median_candidate: 6.462e-1
  },
  ...
]
```

```text
phase3_25storm_overview (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    t0_time_us: 1715393640000000 (us),
    symh_min_nt: -518 (nT),
    valid_phase_minutes: 8653,
    tau_hours: 4.650e+0 (h),
    r_candidate: 6.462e-1,
    m1_excluding_this_storm_g_rmse_log_density: 2.129e-1,
    m0_uncalibrated_rmse_log_density: 4.764e-1,
    algorithm_version: phase3_25storm_overview_v1
  },
  ...
]
```

逐場索引與逐分鐘預測同在 Phase 3 預測 SQLite；索引表有 25 列、`t0_time_us` 唯一，且與事件 ID 完全一致。有效分鐘介於 8,320–8,677，每場計數與逐分鐘表一致。按分鐘合併的 G-excluded M1 RMSE 是 0.2105，未校準 M0 是 0.2343；前者在 15／25 場較低，但校準機會不等，不能據此宣稱 M1 優於 M0。本機資料庫為 `phases/phase3/data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite`；GitHub 可讀的總覽入口是[25 格曲線圖](../../figures/prediction_tau465_25storm_overview.png)。

#### [P3.7] 固定共同時間常數 -> 逐場增益診斷 [done]

```text
prep_event_gain_tau465.py -> main()

只讀 P3.5 的有效相位分鐘、P3.6 的逐場已採用 R_k 與 P3.4 的共同 G 格點；tau 固定 4.65 h，不重選延遲。
z_i = ln(rho_L2,phase,i / rho_MSIS,q,phase,i) - ln(R_k)。
每場只用該場全部事件分鐘估 G_k = sum(H_i z_i) / sum(H_i^2)。
同場比較共同 G 和 G_k 的對數密度 RMSE；結果僅是樣本內幅度診斷。
```

```text
phase3_prediction_minute (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    time_us: 1715393640000000 (us),
    h_phase_nt: 1.637e+3 (nT),
    rho_l2_phase_kg_m3: 4.455e-12 (kg/m^3),
    rho_msis_quiet_phase_kg_m3: 1.702e-12 (kg/m^3),
    rho_m1_pooled_phase_kg_m3: 3.479e-12 (kg/m^3)
  },
  ...
]

phase3_25storm_overview (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    t0_time_us: 1715393640000000 (us),
    valid_phase_minutes: 8653,
    tau_hours: 4.650e+0 (h),
    r_candidate: 6.462e-1
  },
  ...
]

phases/phase3/data/analysis/phase3_tau_grid_005h_exploratory.csv (analysis；欄位節錄)
[
  {
    tau_hours: 4.650e+0 (h),
    gain_per_nt: 7.032e-4 (1/nT)
  },
  ...
]
```

```text
phase3_event_gain_tau465_diagnostic (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    t0_time_us: 1715393640000000 (us),
    valid_phase_minutes: 8653,
    tau_hours: 4.650e+0 (h),
    gain_pooled_per_nt: 7.032e-4 (1/nT),
    gain_event_fit_per_nt: 6.230e-4 (1/nT),
    gain_ratio_to_pooled: 8.859e-1,
    rmse_pooled_log_density: 2.091e-1,
    rmse_event_fit_log_density: 1.982e-1,
    rmse_reduction_pct: 5.202e+0 (%),
    algorithm_version: phase3_event_gain_tau465_diagnostic_v1
  },
  ...
]
```

`1715393640000000` 是 2024-05-11T02:14:00Z 的事件 SYM-H 最低點時間；輸出一列對應整場有效相位分鐘，保留同一 `storm_id` 與來源 `t0_time_us`。25 場全部算出正的 $G_k$，共用 $G$ 的合併對數密度 RMSE 0.20652 降到逐場 $G_k$ 的 0.15251。逐場 $G_k$ 使用各場磁暴期間的 L2；降低的是樣本內誤差，不能拿來評分 Forecast，也不能據此證明各場物理增益不同。[診斷圖](../../figures/event_gain_tau465_diagnostic.png)只呈現共同與逐場增益及其誤差。

#### [P3.8] MSIS `Ap` 歷史對齊 -> 無擬合的回溯 M0 [done]

```text
prep_m0_ap_alignment.py -> main()
calc_m0_ap.py -> msis_ap_history()

只讀 P2.6、原始 DNSAPOD、GFZ ap 與太陽通量；DNSAPOD 日檔依 manifest 核對。
七欄 MSIS Ap = 當日八個三小時 ap 的平均、當下三小時槽、前 3/6/9 小時槽、前 12-33/36-57 小時的八槽平均。
F10.7 與 P2.4 相同：前一 UTC 日 F10.7、置中 81 日 F10.7A；僅更換 Ap 歷史，不從 L2 估參數。
只在有 L2 的原生樣本計算 M0，再按相同 u±pi、配對樣本數權重及 80% coverage 取置中相位平均。
原生樣本數及 L2 逐鍵與 P2.6 核對；舊 M0 相位值逐鍵與 P3.3 核對。
```

```text
storm_density_1min_v5 (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    source_time_us: 1715393640000000 (us),
    paired_sample_count: 2,
    rho_l2_kg_m3: 4.047e-12 (kg/m^3),
    rho_msis_kg_m3: 2.720e-12 (kg/m^3)
  },
  ...
]

phases/phase0/data/raw/geomagnetic/gfz_ap_2023-07-01_2026-06-30.json (raw；索引 2520；欄位節錄)
{
  datetime: [2024-05-11T00:00:00Z],
  ap: [4.000e+2],
  status: [def]
}

phase3_quiet_density_minute (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    time_us: 1715393640000000 (us),
    rho_l2_phase_kg_m3: 4.455e-12 (kg/m^3),
    rho_msis_full_phase_kg_m3: 3.338e-12 (kg/m^3),
    phase_is_valid_80pct: 1
  },
  ...
]
```

```text
phase3_m0_ap_alignment_minute (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    time_us: 1715393640000000 (us),
    paired_sample_count: 2,
    rho_l2_kg_m3: 4.047e-12 (kg/m^3),
    rho_m0_legacy_kg_m3: 2.720e-12 (kg/m^3),
    rho_m0_aligned_kg_m3: 3.272e-12 (kg/m^3),
    rho_l2_phase_kg_m3: 4.455e-12 (kg/m^3),
    rho_m0_legacy_phase_kg_m3: 3.338e-12 (kg/m^3),
    rho_m0_aligned_phase_kg_m3: 3.922e-12 (kg/m^3),
    phase_is_valid_80pct: 1,
    algorithm_version: phase3_m0_ap_alignment_v1
  },
  ...
]

phase3_m0_ap_alignment_storm (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    valid_phase_minutes: 8653,
    rmse_legacy_log_density: 4.764e-1,
    rmse_aligned_log_density: 4.599e-1,
    median_aligned_over_legacy: 9.928e-1,
    algorithm_version: phase3_m0_ap_alignment_v1
  },
  ...
]
```

`1715393640000000` 是 2024-05-11T02:14:00Z 的來源觀測分鐘；同一 key 保留至新衍生表。GFZ `datetime` 是三小時槽的 UTC 起點。新庫含 217,912 個分鐘鍵、214,907 個有效相位錨點與 25 場，`integrity_check=ok`。與 L2 比較的合併對數密度 RMSE 由 0.23433 降至 0.22699，23／25 場逐場降低。這只是在 MSIS 既有經驗模型內修正回溯輸入，沒有建立第一原理熱層模型；當日 `Ap`、置中 F10.7A 和置中相位窗口可能使用錨點後資訊，結果不可稱即時預報。

#### [P3.9] 10 小時邊界事件 -> 延長 $\tau$ 診斷 [done]

```text
prep_tau_extended_diagnostic.py -> main()

只取原逐場擬合卡在 10 h 的 7 場。連續 1-minute SME - 65 nT 用同一指數核濾波；每個 tau 再按相同 u±pi、配對樣本權重與 80% coverage 取相位平均。
tau=10..72 h 每 0.5 h、73..240 h 每 1 h。固定同一套 R_k，每場每個 tau 過原點重新估 G_k 與 RMSE。
10 h 的每場 RMSE 與原 41 格點結果交叉核對。輸出以 {storm_id, tau_seconds} 為 key；不產生新的逐分鐘資料。
```

```text
geomag_1min_v2 (derived；欄位節錄)
[
  {
    time_us: 1688169600000000 (us),
    sme_nt: 7.471e+1 (nT),
    sme_valid: 1
  },
  ...
]

phase3_quiet_density_minute (derived；欄位節錄)
[
  {
    storm_id: S20231201T1330,
    time_us: 1701437400000000 (us),
    log_l2_over_quiet_phase: 7.967e-1,
    phase_is_valid_80pct: 1
  },
  ...
]

phases/phase3/data/analysis/phase3_rquiet_near_zero_25.csv (已採用倍率；歷史欄名；欄位節錄)
[
  {
    storm_id: S20231201T1330,
    r_near_zero_median_candidate: 9.055e-1
  },
  ...
]
```

```text
phase3_tau_extended_grid (derived；欄位節錄)
[
  {
    storm_id: S20231201T1330,
    tau_seconds: 46800 (s),
    gain_per_nt: 2.691e-3 (1/nT),
    rmse_log_density: 1.350e-1,
    fit_minutes: 8667,
    algorithm_version: phase3_tau_extended_diagnostic_v1
  },
  ...
]

phase3_tau_extended_summary (derived；欄位節錄)
[
  {
    storm_id: S20231201T1330,
    best_tau_seconds: 46800 (s),
    best_rmse_log_density: 1.350e-1,
    rmse_at_10h: 1.393e-1,
    best_hits_240h_boundary: 0,
    algorithm_version: phase3_tau_extended_diagnostic_v1
  },
  ...
]
```

`1688169600000000` 是 2023-07-01T00:00:00Z 的 SME 觀測分鐘；`1701437400000000` 是 2023-12-01T13:30:00Z 的相位錨點。診斷表按 `storm_id` 彙集所有有效錨點，另以 `tau_seconds` 區分候選。7 場共 2,051 個格點，`integrity_check=ok`。5 場在搜尋內有最低點；另 2 場的最佳值落在 240 小時邊界，不能把邊界當作已量到的熱層時間常數。這是樣本內、逐場可調 $G_k$ 的診斷；主線 $\tau$ 與報告未改。

#### [P3.10] 完整 MSIS -> M2 修正前的殘差 [done]

```text
prep_m2_residual_diagnostic.py -> main()

使用 P3.8 已對齊實際 Ap 歷史的回溯 M0，與同相位、同有效錨點的 L2 計算 r=ln(rho_L2/rho_M0)。
只把 P3.5 的 H_4.65 並列作時間形狀診斷；不套用 M1 的 R_k、G 或其他修正。
全部 25 場沿用置中 u±pi 相位、L2 同樣本配對及至少 80% coverage；輸出以 {storm_id,time_us} 為 key。
```

```text
phase3_m0_ap_alignment_minute (derived；欄位節錄)
[
  {
    storm_id: S20231201T1330,
    time_us: 1701437400000000 (us),
    rho_l2_phase_kg_m3: 1.966e-12 (kg/m^3),
    rho_m0_aligned_phase_kg_m3: 1.341e-12 (kg/m^3),
    phase_is_valid_80pct: 1
  },
  ...
]

phase3_prediction_minute (derived；欄位節錄)
[
  {
    storm_id: S20231201T1330,
    time_us: 1701437400000000 (us),
    h_phase_nt: 5.951e+2 (nT)
  },
  ...
]
```

```text
phase3_m2_residual_minute (derived；欄位節錄)
[
  {
    storm_id: S20231201T1330,
    time_us: 1701437400000000 (us),
    h_tau465_phase_nt: 5.951e+2 (nT),
    residual_log_density: 3.826e-1,
    algorithm_version: phase3_m2_residual_diagnostic_v1
  },
  ...
]

phase3_m2_residual_storm (derived；欄位節錄)
[
  {
    storm_id: S20231201T1330,
    t0_time_us: 1701437400000000 (us),
    valid_minutes: 8667,
    median_residual_log_density: 4.370e-2,
    positive_residual_fraction: 5.987e-1,
    correlation_with_h: 6.642e-1,
    algorithm_version: phase3_m2_residual_diagnostic_v1
  },
  ...
]
```

`1701437400000000` 是 2023-12-01T13:30:00Z 的相位錨點與該場 SYM-H 最低點。診斷庫有 214,907 個有效分鐘、25 個事件摘要，`integrity_check=ok`。[七場邊界事件殘差與 SME 響應圖](../../figures/m2_full_msis_residual_7_boundary.png)沿用原 M1 的 4.65 小時只作並列觀察。以完整事件中心化得到的相關與斜率使用事件期間 L2，不能用作 M2 校準或 Forecast。M2 尚無修正公式或預測密度。

#### [P3.11] 平靜 MSIS + 原事前窗口 -> M1A [done]

```text
prep_m1a_zero_sme.py -> main()

連續 1-minute SME 經 tau 濾波後保留原值 F_tau，不減 65 nT。原 P3.1 事前窗口只保留時間位置；重新取該窗口原生配對 L2／固定 ap=4 平靜 MSIS。
每個候選 G,tau 先從窗口算 R_A,k=median[(L2/MSISq) exp(-G F_tau)]，再對各場有效相位分鐘的 log-density 誤差作最小平方。
tau=0..10 h 每 0.25 h，加上最低格點附近每 0.05 h 細分；輸出是樣本內回溯曲線。
```

```text
phases/phase3/data/analysis/phase3_rquiet_near_zero_25.csv (候選窗口；欄位節錄)
[
  {
    storm_id: S20231201T1330,
    near_zero_start_utc: 2023-11-20T00:59:00+00:00,
    near_zero_end_exclusive_utc: 2023-11-20T04:42:00+00:00,
    run_minutes: 223
  },
  ...
]

phase3_quiet_density_minute (derived；欄位節錄)
[
  {
    storm_id: S20231201T1330,
    time_us: 1701437400000000 (us),
    rho_l2_phase_kg_m3: 1.966e-12 (kg/m^3),
    rho_msis_quiet_phase_kg_m3: 8.865e-13 (kg/m^3),
    phase_is_valid_80pct: 1
  },
  ...
]
```

```text
phase3_m1a_grid (derived；欄位節錄)
[
  {
    tau_seconds: 17280 (s),
    gain_per_nt: 7.075e-4 (1/nT),
    rmse_log_density: 2.081e-1,
    algorithm_version: phase3_m1a_zero_sme_v1
  },
  ...
]

phase3_m1a_event (derived；欄位節錄)
[
  {
    storm_id: S20231201T1330,
    tau_seconds: 17280 (s),
    r_zero_sme_extrapolated: 8.613e-1,
    quiet_minutes: 223,
    fit_minutes: 8667,
    algorithm_version: phase3_m1a_zero_sme_v1
  },
  ...
]

phase3_m1a_prediction_minute (derived；欄位節錄)
[
  {
    storm_id: S20231201T1330,
    time_us: 1701437400000000 (us),
    sme_filtered_phase_nt: 6.517e+2 (nT),
    rho_m1a_phase_kg_m3: 1.211e-12 (kg/m^3),
    algorithm_version: phase3_m1a_zero_sme_v1
  },
  ...
]
```

`1701437400000000` 是 2023-12-01T13:30:00Z 的事件相位錨點。223 個事前分鐘的 UTC 標籤用原生 L2 配對重算；49 個候選 tau 格點中，共同最佳值為 4.80 小時。輸出有 214,907 個有效相位分鐘、25 場，`integrity_check=ok`。$R_{A,k}$ 由事件資料估出的 $G,\tau$ 反推，表示 SME=0 的模型截距，不是獨立觀測到的平靜比值；窗口仍沿用以 65 nT 近零條件選出的舊窗口。

#### [P3.12] M1A -> 逐場 $\tau_k$ 格點 [done]

```text
prep_m1a_event_tau.py -> main()

沿用 P3.11 的窗口、同一個零 SME 參考與相位配對；每場單獨對 0..10 h、0.25 h 格點重算 G_k 與 R_A,k。
只作樣本內時間常數診斷，不回寫 P3.11 的共同參數或 M1 主線。
```

```text
phase3_quiet_density_minute (derived；欄位節錄)
[
  {
    storm_id: S20231201T1330,
    time_us: 1701437400000000 (us),
    log_l2_over_quiet_phase: 7.967e-1,
    phase_is_valid_80pct: 1
  },
  ...
]

phases/phase3/data/analysis/phase3_rquiet_near_zero_25.csv (候選窗口；欄位節錄)
[
  {
    storm_id: S20231201T1330,
    near_zero_start_utc: 2023-11-20T00:59:00+00:00,
    near_zero_end_exclusive_utc: 2023-11-20T04:42:00+00:00
  },
  ...
]
```

```text
phase3_m1a_event_tau_grid (derived；欄位節錄)
[
  {
    storm_id: S20231201T1330,
    tau_seconds: 36000 (s),
    gain_per_nt: 2.574e-3 (1/nT),
    r_zero_sme_extrapolated: 7.585e-1,
    rmse_log_density: 1.435e-1,
    algorithm_version: phase3_m1a_event_tau_v1
  },
  ...
]

phase3_m1a_event_tau_summary (derived；欄位節錄)
[
  {
    storm_id: S20231201T1330,
    best_tau_seconds: 36000 (s),
    hits_10h_boundary: 1,
    algorithm_version: phase3_m1a_event_tau_v1
  },
  ...
]
```

輸出共 1,025 個事件與 tau 格點、25 個逐場摘要，`integrity_check=ok`。原 M1 卡 10 小時的 7 場在 M1A 仍全卡，另有 1 場新卡；10 小時是搜尋邊界，不是量到的時間常數。逐場 $G_k,R_{A,k},\tau_k$ 都使用該場事件 L2，不能當留出事件預測。

## 結案範圍與保留診斷

- $R_k$ 已依 P3.1 的低活動段規則完成校準；其事件距離、穩定性與 onset 關係是校準適用範圍的記錄，不是待處理事項。
- M0 的回溯 `Ap` 時間對齊已於 P3.8 校正。M0/M1 的輸出是本 phase 的離線比較；不延伸為即時 Forecast 的優劣主張。
- 真正的即時預報須另立研究，使用當時已知的輸入、僅看過去的相位窗口及事前固定的參數；不得回寫本文件的回溯曲線。
- 逐場 $\tau_k$ 的邊界與寬範圍是保留診斷，不修改共同 $\tau$ 或 Phase 3 最終結果。
