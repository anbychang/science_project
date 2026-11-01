# Phase 5 V2 Ridge 資料血緣

狀態：[done: exploratory]。目標取自 Phase 4 V2 共同 $\tau$ 的回溯擬合值，Phase 3 原本 $R_k$ 是歷史輸入。Phase 4 V2 與 Phase 3 來源庫唯讀；Phase 5 V2 的兩個 SQLite 是獨立衍生輸出，不改上游 checkpoint。

| 角色 | SQLite 路徑 |
| --- | --- |
| Phase 4 V2 目標來源 | `phases/phase4-v2/data/sqlite/swarm_a_phase4_v2_shared_tau.sqlite` |
| Phase 3 原本 $R_k$ 來源 | `phases/phase4/data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite` |
| Phase 4 V2 目標快照 | `phases/phase5-v2/data/sqlite/phase4_v2_r_targets_v2.sqlite` |
| Ridge 研究輸出 | `phases/phase5-v2/data/sqlite/storm_r_ridge_v21.sqlite` |
| 密度比較輸出 | `phases/phase5-v2/data/sqlite/storm_r_ridge_density_v1.sqlite` |

磁場分鐘值另讀 `phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_2_v2.sqlite`；太陽活動讀 `phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite`；`ap` 原始輸入讀 `phases/phase0/data/raw/geomagnetic/gfz_ap_2023-07-01_2026-06-30.json`。這些來源均不寫入。

#### [P5V2.1] Phase 4 V2 事件 R -> 目標快照 [done]

```text
prep_phase4_v2_r_targets.py -> load_targets(), save_targets()
phase4_v2_events.r_fit -> 按 storm_id 原值複製 -> phase4_v2_r_target.r_fit
共同 tau 與 G 只作來源契約核對；R 無單位，保留 SQLite 浮點完整精度。
```

```text
phase4_v2_events (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    r_fit: 9.343e-1,
    tau_hours: 4.750e+0 (h),
    gain_per_nt: 6.898e-4 (1/nT),
    valid_phase_minutes: 8677
  },
  ...
]
```

```text
phase4_v2_r_target (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    r_fit: 9.343e-1,
    tau_hours: 4.750e+0 (h),
    gain_per_nt: 6.898e-4 (1/nT),
    source_algorithm_version: phase4_v2_shared_tau_475_v1,
    algorithm_version: phase4_v2_r_targets_v2
  },
  ...
]
```

此 $R_k$ 用同場 L2 密度擬合，屬回溯目標，不是預報時已知值。

#### [P5V2.2] Phase 3 校準段與天氣 -> 事件因素 [done]

```text
prep_storm_r_quiet_window_trials.py -> load_quiet_features()
prep_storm_r_ridge.py -> load_rows(), save_results()
Phase 3 r_candidate + 低活動段 + Phase 2 SME／SYM-H／AE + 原始 ap + Phase 1 F10.7A
  -> 每場 23 個因素，並與 P5V2.1 的 storm_id、r_fit 逐筆比對
校準段選在事件首次強 SYM-H 低點之前；F10.7A 取校準開始前最近值，落後不得超過 3 h。
```

```text
phase3_25storm_overview (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    t0_time_us: 1691214360000000 (us),
    r_candidate: 8.299e-1,
    r_pre_distance_days: 1.590e+1 (d)
  },
  ...
]

geomag_1min_v2 (derived；欄位節錄)
[
  {
    time_us: 1689823920000000 (us),
    sme_nt: 8.812e+1 (nT),
    symh_nt: -1 (nT),
    ae_nt: 42 (nT)
  },
  ...
]

space_weather (derived；欄位節錄)
[
  {
    time_us: 1689822000000000 (us),
    f107a_last81_sfu: 1.643e+2 (sfu)
  },
  ...
]
```

```text
event_input (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    t0_time_us: 1691214360000000 (us),
    quiet_start_time_us: 1689823920000000 (us),
    quiet_end_exclusive_time_us: 1689839880000000 (us),
    r_phase3: 8.299e-1,
    r_fit: 9.343e-1
  },
  ...
]

event_feature (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    feature: prequiet_sme_mean_nt,
    value: 8.649e+1
  },
  {
    storm_id: S20230805T0546,
    feature: quiet_f107a_last81_sfu,
    value: 1.643e+2
  },
  ...
]
```

`t0_time_us` 是事件起點，`quiet_start_time_us` 是校準段第一分鐘，`quiet_end_exclusive_time_us` 是校準段結束後第一分鐘；均為 UTC epoch microseconds。`event_feature.value` 的單位依 `feature` 名稱：SME 為 nT，F10.7A 為 sfu，$R_k$ 無單位。25 個事件對應 20 個不同校準段；一場事件一個 $R_k$ 標籤，分鐘值不增加標籤數。

#### [P5V2.3] 23 因素 -> 固定 Ridge 修正模型 [done]

```text
calc_storm_r_ridge.py -> evaluate(), search_features(), fit_model()
prep_storm_r_ridge.py -> save_results()
delta R = r_fit - r_phase3；每候選五次 20 訓練／5 算分，取五個 RMSE 的算術平均。
先評 23 個單因素，再保留前 8、合併與隨機替換；最多 3 因素，7 輪，seed 42。
每折標準化只 fit 20 場；Ridge alpha=1；共用校準段不跨訓練與算分組。
```

```text
event_input (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    r_phase3: 8.299e-1,
    r_fit: 9.343e-1
  },
  ...
]

event_feature (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    feature: r_phase3,
    value: 8.299e-1
  },
  ...
]
```

```text
candidate_score (derived；欄位節錄)
[
  {
    features: r_phase3,prequiet_sme_mean_nt,quiet_f107a_last81_sfu,
    five_fold_mean_rmse_r: 1.155e-1,
    selected: 1
  },
  ...
]

fold_score (derived；欄位節錄)
[
  {
    fold_index: 1,
    train_count: 20,
    score_count: 5,
    train_rmse_r: 8.650e-2,
    five_event_rmse_r: 1.620e-1
  },
  ...
]

heldout_prediction (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    fold_index: 2,
    r_phase3: 8.299e-1,
    r_fit: 9.343e-1,
    r_pred: 8.533e-1
  },
  ...
]

final_parameter (derived；欄位節錄)
[
  {
    feature: r_phase3,
    train_mean: 8.783e-1,
    train_scale: 1.744e-1,
    coefficient: -5.959e-2
  },
  ...
]
```

每個 `heldout_prediction` 由該折的 20 場擬合，不使用該場標籤訓練模型。`final_parameter` 則在選完因素後用全 25 場重新擬合，僅供後續研究。五組算分標籤已參與特徵搜尋，所以 0.115458 是搜尋分數；沒有新事件的獨立外測，也沒有即時預報證據。

#### [P5V2.4] 留出 Ridge R + V2 響應 -> 密度比較表 [done]

```text
prep_storm_r_ridge_density.py -> calculate_event(), save_results()
V1 與 V2 以 {storm_id, time_us} 完全對齊，逐分鐘核對 L2 與 quiet MSIS 密度相同。
rho_ridge = rho_msis_quiet_v2 * r_pred_heldout * exp(G_v2 * H_v2)。
每場以 log(L2/model density) 計算 V1、V2、Ridge 的 RMSE；Ridge 不用同場 L2 重估 R。
```

```text
trial4_joint_fit_minute (Phase 4 V1 derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691041800000000 (us),
    rho_l2_phase_kg_m3: 6.920e-13 (kg/m^3),
    rho_msis_quiet_phase_kg_m3: 6.530e-13 (kg/m^3),
    rho_trial4_joint_phase_kg_m3: 6.805e-13 (kg/m^3)
  },
  ...
]

phase4_v2_minute (Phase 4 V2 derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691041800000000 (us),
    rho_l2_phase_kg_m3: 6.920e-13 (kg/m^3),
    rho_msis_quiet_phase_kg_m3: 6.530e-13 (kg/m^3),
    rho_phase4_v2_phase_kg_m3: 6.682e-13 (kg/m^3),
    h_phase_nt: 1.319e+2 (nT),
    gain_per_nt: 6.898e-4 (1/nT)
  },
  ...
]

heldout_prediction (Phase 5 V2 derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    fold_index: 2,
    r_pred: 8.533e-1
  },
  ...
]
```

```text
density_comparison (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691041800000000 (us),
    rho_l2_phase_kg_m3: 6.920e-13 (kg/m^3),
    rho_phase4_v1_phase_kg_m3: 6.805e-13 (kg/m^3),
    rho_phase4_v2_phase_kg_m3: 6.682e-13 (kg/m^3),
    rho_ridge_phase_kg_m3: 6.103e-13 (kg/m^3)
  },
  ...
]

event_density_score (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    minute_count: 8677,
    v1_rmse_log_density: 6.578e-2,
    v2_rmse_log_density: 7.048e-2,
    ridge_rmse_log_density: 1.148e-1
  },
  ...
]
```

`time_us` 是沿用 Phase 4 的 UTC 分鐘錨點，例值對應 2023-08-03T05:50:00Z；214,907 個 `{storm_id, time_us}` 在 V1、V2、比較庫完全一致。V1 與 V2 使用同場 L2 回溯擬合，Ridge 曲線使用該場留出的 $R_k$；三者 log RMSE 不是相同校準機會下的預報比較。

#### [P5V2.5] L2、Ridge、V1 擬合密度 -> 25 格圖 [done]

```text
prep_storm_r_ridge_density_figure.py -> load_events(), draw_figure()
每場只畫 L2、留出 Ridge R 的密度、V1 同場擬合 tau_k 與 R_k 的密度。
每場使用原始分鐘點；橫軸為相對 t0 的小時，縱軸為 1e-12 kg/m^3。
25 場按 storm_id 排序排成 5×5；每格縱軸依該場範圍獨立設定。
```

```text
density_comparison (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691041800000000 (us),
    t0_time_us: 1691214360000000 (us),
    rho_l2_phase_kg_m3: 6.920e-13 (kg/m^3),
    rho_phase4_v1_phase_kg_m3: 6.805e-13 (kg/m^3),
    rho_ridge_phase_kg_m3: 6.103e-13 (kg/m^3)
  },
  ...
]
```

```text
figures/ridge_density_25_storms_5x5_v3.png (PNG；4500×3600 px；25 個事件子圖)
```
