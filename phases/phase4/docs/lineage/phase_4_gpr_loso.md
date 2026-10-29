# Phase 4 一圈 GPR 資料血緣

## 狀態與資料邊界

狀態：[working]。25 場留一場驗證與逐場圖已產出；使用者看圖後判斷目前四特徵 GPR 效果不理想。[結果報告](../../reports/phase_4_gpr_loso_report.md)記錄數值、失效診斷與限制。Phase 4 讀取下列凍結來源，寫自己的衍生庫；來源庫不是工作副本，沒有回寫。

- `phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_6_final.sqlite`
- `phases/phase3/data/sqlite/swarm_a_phase3_quiet_density_v1.sqlite`
- `phases/phase3/data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite`
- `phases/phase4/data/sqlite/swarm_a_phase4_gpr_loso_v1.sqlite`

正式折次 checkpoint 在 `phases/phase4/data/analysis/folds_default_optimizer/`。每折 JSON 保留預測、指標、標準化與核參數；最終 SQLite 由這 25 個 checkpoint 彙整。較早的 `folds/` 是已停止的最佳化試跑，不是正式結果。專案 `.gitignore` 排除各 Phase 的 SQLite；GitHub 保存本 Phase 的程式、checkpoint、CSV／JSON 與圖，重新計算仍須本機上游 SQLite。

```text
P2.6 相位 u、連續 SME、配對數 + P3 一圈密度、R_k
  -> P4.0 一圈／兩圈資料單位 QC
  -> P4.1 一圈錨點、逐折 M1／GPR、留出場 SQLite／CSV／JSON／圖
```

#### [P4.0] 一圈／兩圈資料單位目視 QC [done]

```text
prep_one_cycle_figures.py -> main()
prep_two_cycle_figures.py -> main()

以 t0 為 u=0，對完整且配對覆蓋率至少 80% 的中心作資料單位比較。
一圈取 u±pi、中心格點 2pi*j；兩圈取 u±2pi、中心格點 4pi*j。
兩者均選距格點不超過 0.01 圈的最近有效分鐘中心。
使用者看圖後採一圈；兩圈候選只保留 QC，不進正式 GPR。
```

```text
storm_minute_feature_v5 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    source_time_us: 1691044560000000 (us),
    u_rel_rad: -1.885e+2 (rad)
  },
  ...
]

phase3_quiet_density_minute (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691044560000000 (us),
    paired_sample_count: 2,
    rho_l2_phase_kg_m3: 6.728e-13 (kg/m^3),
    phase_is_valid_80pct: 1
  },
  ...
]

phase3_25storm_overview (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    t0_time_us: 1691214360000000 (us)
  },
  ...
]
```

```text
phase4_one_cycle_anchor_qc.csv (analysis；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    phase3_valid_minute_anchors: 8677,
    phase4_one_cycle_anchors: 92,
    first_anchor_hours_from_t0: -4.717e+1 (h),
    last_anchor_hours_from_t0: 9.590e+1 (h)
  },
  ...
]

phase4_two_cycle_anchor_qc.csv (analysis；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    phase3_valid_minute_anchors: 8677,
    phase4_two_cycle_anchors: 45,
    first_anchor_hours_from_t0: -4.402e+1 (h),
    last_anchor_hours_from_t0: 9.433e+1 (h)
  },
  ...
]
```

`1691044560000000` 是 2023-08-03T06:36:00Z 的觀測分鐘與一圈相位窗口中心。QC CSV 的逐場計數可追溯至該場所有有效分鐘中心；25 場一圈合計 2,295 個代表錨點，兩圈候選合計 1,131 個。[一圈圖](../../reports/phase_4_one_cycle_anchor_qc.md)與[兩圈對照圖](../../reports/phase_4_two_cycle_window_qc.md)保存目視決定。

#### [P4.1] 凍結相位資料 -> 留一場 GPR 預測 [working]

```text
prep_gpr_loso.py -> main()

以 P2.6 的 t0 為相位原點；取 P4.0 採用的一圈中心，密度、SME、SYM-H
與濾波響應按原生配對樣本數加權。不跨連續 SME 的缺口補值。
每折排除一場；24 場在 tau=0..10 h、間距 0.05 h 的格點上重估 G 與 tau。
G_tau=sum(H_tau*z)/sum(H_tau^2)；z=ln(rho_L2_phase/(rho_quiet_phase*R_k))。
測試場的 R_k 只取其 Phase 3 暴前低活動窗口；不使用其磁暴窗口 L2 訓練。
訓練場 StandardScaler -> 零均值 GPR：H_tau、H_24h、SME、SYM-H 四欄。
核函數 ConstantKernel*RBF(ARD)+WhiteKernel；預設 L-BFGS-B、5 次重啟。
每折輸出 JSON checkpoint；25 折彙整成版本化 SQLite、CSV、scaler JSON 與圖。
```

```text
storm_minute_feature_v5 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    source_time_us: 1691044560000000 (us),
    u_rel_rad: -1.885e+2 (rad),
    symh_nt: -2.000e+0 (nT)
  },
  ...
]

storm_density_1min_v5 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    source_time_us: 1691044560000000 (us),
    paired_sample_count: 2
  },
  ...
]

geomag_1min_v2 (derived；連續 SME；欄位節錄)
[
  {
    time_us: 1691044560000000 (us),
    sme_nt: 1.787e+2 (nT),
    sme_valid: 1
  },
  ...
]

phase3_quiet_density_minute (derived；同一分鐘的原生配對值；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691044560000000 (us),
    paired_sample_count: 2,
    rho_l2_kg_m3: 9.705e-13 (kg/m^3),
    rho_msis_quiet_kg_m3: 8.512e-13 (kg/m^3),
    phase_is_valid_80pct: 1
  },
  ...
]

phase3_25storm_overview (derived；逐場最終 R_k；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    t0_time_us: 1691214360000000 (us),
    r_candidate: 8.299e-1
  },
  ...
]
```

```text
folds_default_optimizer/S20230805T0546.json (analysis；欄位節錄)
{
  metrics: {
    storm_id: S20230805T0546,
    test_anchors: 92,
    train_anchors: 2203
  },
  hyperparameters: {
    n_restarts_optimizer: 5,
    normalize_y: false,
    convergence_warning_count: 0
  },
  scaler: {
    train_anchors: 2203
  }
}

phase4_gpr_prediction (derived；留出場一圈錨點；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691044560000000 (us),
    u_rel_rad: -1.885e+2 (rad),
    rho_l2_phase_kg_m3: 6.728e-13 (kg/m^3),
    rho_phys_phase_kg_m3: 5.886e-13 (kg/m^3),
    rho_gpr_median_kg_m3: 5.322e-13 (kg/m^3),
    gp_log_residual_mean: -1.006e-1,
    gp_log_residual_std: 1.632e-1,
    rho_95_lower_kg_m3: 3.865e-13 (kg/m^3),
    rho_95_upper_kg_m3: 7.328e-13 (kg/m^3),
    algorithm_version: phase4_gpr_loso_v1
  },
  ...
]

phase4_loso_event_metrics.csv (analysis；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    test_anchors: 92,
    train_anchors: 2203,
    tau_hours: 4.600e+0 (h),
    gain_per_nt: 6.957e-4 (1/nT),
    m1_rmse_log_density: 1.369e-1,
    gpr_rmse_log_density: 1.305e-1,
    gpr_coverage_95: 9.891e-1
  },
  ...
]

gpr_hyperparams.csv (analysis；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    length_scale_h_tau_phase_nt: 9.236e-1,
    length_scale_h_24h_phase_nt: 5.935e-1,
    length_scale_sme_phase_nt: 3.387e+0,
    length_scale_symh_phase_nt: 5.781e-1,
    signal_variance: 3.736e-2,
    noise_variance: 2.619e-2,
    convergence_warning_count: 0
  },
  ...
]

scaler_params.json (analysis；欄位節錄)
{
  algorithm_version: phase4_gpr_loso_v1,
  folds: {
    S20230805T0546: {
      feature_names: [
        h_tau_phase_nt,
        h_24h_phase_nt,
        sme_phase_nt,
        symh_phase_nt
      ],
      mean: [
        3.187e+2,
        3.159e+2,
        3.822e+2,
        -4.376e+1
      ],
      scale: [
        3.099e+2,
        2.123e+2,
        3.737e+2,
        4.681e+1
      ],
      train_anchors: 2203
    }
  }
}
```

`1691044560000000` 是 2023-08-03T06:36:00Z 的觀測分鐘，也是一圈窗口的中心與輸出 key。輸出密度是中心前後各半圈的加權值，不能當該分鐘瞬時密度。`r_candidate` 是 Phase 3 留下的欄名；$R_k$ 已是 Phase 3 最終採用的操作性平靜倍率。正式 25 個 checkpoint、25 場 CSV 列及 SQLite 的 2,295 列使用相同的 `storm_id`；最終輸出時段為 2023-08-03T06:36:00Z 至 2026-04-22T06:26:00Z。中心窗口及置中 F10.7A 使用後續資料，因此此結果只適用條件式離線回放。
