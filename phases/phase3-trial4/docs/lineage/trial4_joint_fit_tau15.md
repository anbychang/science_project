# Trial4 三年 25 場自由 $R_k$／$\tau_k$ 資料血緣

## 狀態與資料邊界

狀態：[working]。Trial4 是獨立的描述性擬合輸出，不會更新已凍結的 Phase 2 或 Phase 3。它讀取 Trial4 目錄內唯讀保存的 Phase 3 相位密度與 tau-grid 快照，以及 Phase 2 P2.6 事件／SME 來源，將自己的結果寫入：

- `phases/phase3-trial4/data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite`
- `phases/phase3-trial4/data/analysis/phase3_tau_grid_005h_exploratory.csv`
- `phases/phase3-trial4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite`

此庫的 `trial4_joint_fit_minute` 以 `{storm_id, time_us}` 為 key，`trial4_25storm_overview` 以 `storm_id` 為 key；兩表都保存 `algorithm_version`。`time_us` 是 UTC 分鐘錨點；密度與 $H_\tau$ 都是以該分鐘為中心的 $u\pm\pi$ 相位平均，不是獨立原生觀測或即時 Forecast。

```text
Trial4-held Phase 3 phase-density snapshot + Phase 2 SME/event metadata
  -> P4.1 event-equal A--D joint fit
  -> P4.2 D-model minute table and 25-storm overview
  -> P4.3 analysis CSV and retrospective figures
```

#### [P4.1] Trial4 保存的 Phase 3 密度快照 -> A--D joint-fit 參數 [done]

```text
prep_trial4_joint_fit.py -> main()

讀取 Trial4 保存的 Phase 3 L2／quiet MSIS／full MSIS 相位密度、R_RQ 與 4.65 h gain。
由連續 SME 重新計算 tau=0.0..15.0 h、每 0.1 h 的 H_tau，再作同一 u±pi 相位平均。
目標為 25 場等權的對數密度 MSE。每輪固定 tau 更新 25 個 0<R_k<2 與共同 G>0，
再固定 R_k,G 掃每場 tau；平手保留原 tau，最多 20 輪。
```

```text
phase3_prediction_minute (derived；Trial4 保存的 Phase 3 唯讀快照；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    time_us: 1715393640000000 (us),
    rho_l2_phase_kg_m3: 4.455e-12 (kg/m^3),
    rho_msis_quiet_phase_kg_m3: 1.702e-12 (kg/m^3),
    rho_msis_full_phase_kg_m3: 3.338e-12 (kg/m^3),
    h_phase_nt: 1.772e+3 (nT),
  },
  ...
]

phase3_25storm_overview (derived；Trial4 保存的 Phase 3 唯讀快照；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    r_candidate: 6.462e-1,
  },
  ...
]
```

```text
phases/phase3-trial4/data/analysis/trial4_joint_fit_tau15_models.csv (analysis；欄位節錄)
[
  {
    model: D_free_r_tau,
    gain_per_nt: 7.051e-4 (1/nT),
    event_equal_rmse_log_density: 1.100e-1,
    outer_iterations: 5,
  },
  ...
]

phases/phase3-trial4/data/analysis/trial4_joint_fit_tau15_events.csv (analysis；欄位節錄)
[
  {
    model: D_free_r_tau,
    storm_id: S20240511T0214,
    r_rq: 6.462e-1,
    r_fit: 6.212e-1,
    tau_hours: 3.000e+0 (h),
    tau_within_1pct_low_hours: 2.600e+0 (h),
    tau_within_1pct_high_hours: 3.300e+0 (h),
  },
  ...
]
```

`1715393640000000` 是 2024-05-11T02:14:00Z 的事件 $t_0$ 分鐘。所有對數使用自然對數；SQLite 的 `log()` 不參與此擬合。A 使用凍結 Phase 3 參數，B 只自由 $R_k$，C 只自由 $\tau_k$，D 同時自由 $R_k,\tau_k$。D 的 25 場 $\tau_k$ 都在 3.0–10.1 h，沒有到 15 h 搜尋上界。

#### [P4.2] D-model 參數 + Trial4 保存的 Phase 3 密度快照 -> Trial4 SQLite [done]

```text
prep_trial4_joint_prediction.py -> main()

讀取 P4.1 的 D-model CSV；每場按保存的 R_fit、tau_hours 與共同 G 重建
rho_trial4_joint = rho_MSIS,q,phase * R_fit * exp(G * H_tau)。
寫入新 SQLite 前檢查 25 場、214907 個分鐘、0<R_fit<2、0<=tau<=15、G>0；
寫後檢查每場分鐘數、table key 與 PRAGMA integrity_check。來源 SQLite 全以 ro URI 開啟。
```

```text
P4.1 D-model event CSV (analysis；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    r_fit: 6.212e-1,
    tau_hours: 3.000e+0 (h),
  },
  ...
]

phase3_prediction_minute (derived；Trial4 保存的 Phase 3 唯讀快照；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    time_us: 1715393640000000 (us),
    rho_l2_phase_kg_m3: 4.455e-12 (kg/m^3),
    rho_msis_quiet_phase_kg_m3: 1.702e-12 (kg/m^3),
  },
  ...
]
```

```text
trial4_joint_fit_minute (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    time_us: 1715393640000000 (us),
    h_phase_nt: 1.772e+3 (nT),
    rho_l2_phase_kg_m3: 4.455e-12 (kg/m^3),
    rho_msis_quiet_phase_kg_m3: 1.702e-12 (kg/m^3),
    rho_trial4_joint_phase_kg_m3: 3.689e-12 (kg/m^3),
    residual_log_density: 1.887e-1,
    r_fit: 6.212e-1,
    tau_hours: 3.000e+0 (h),
    gain_per_nt: 7.051e-4 (1/nT),
    algorithm_version: trial4_joint_fit_tau15_v1,
  },
  ...
]

trial4_25storm_overview (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    t0_time_us: 1715393640000000 (us),
    valid_phase_minutes: 8653,
    r_fit: 6.212e-1,
    tau_hours: 3.000e+0 (h),
    trial4_joint_rmse_log_density: 1.934e-1,
    algorithm_version: trial4_joint_fit_tau15_v1,
  },
  ...
]
```

分鐘列的 `time_us` 延續 Phase 3 相位密度 key。`residual_log_density=ln(rho_l2_phase/rho_trial4_joint_phase)`；它是回溯模型殘差，不是獨立測試誤差。庫內另有 `trial4_joint_fit_metadata` 保存共同 $G$、tau 格點與唯讀來源界線。

#### [P4.3] Trial4 SQLite -> 分析總覽與圖 [done]

```text
prep_trial4_joint_prediction.py -> save_overview_csv(), draw_examples(), draw_overview()

以 P4.2 同一組 D-model minute rows 寫 25 場總覽 CSV。
兩場圖比較 L2、Phase 3 full-MSIS M0 與 Trial4 D；25 場圖用相同三條曲線與 t0 垂線。
每 30 分鐘畫一點只影響顯示，不改 SQLite 或任何 estimator。
```

```text
trial4_joint_fit_minute (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    time_us: 1715393640000000 (us),
    rho_trial4_joint_phase_kg_m3: 3.689e-12 (kg/m^3),
  },
  ...
]
```

```text
phases/phase3-trial4/data/analysis/trial4_joint_fit_tau15_overview.csv (analysis；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    t0_time_us: 1715393640000000 (us),
    r_fit_over_r_rq: 9.612e-1,
    tau_hours: 3.000e+0 (h),
    trial4_joint_rmse_log_density: 1.934e-1,
  },
  ...
]

phases/phase3-trial4/figures/trial4_joint_fit_tau15_25storm_overview.png (figure)
```

圖是訓練資料的回溯檢查。中心相位平均的窗口重疊，而且會用錨點之後的資料；因此圖不能當成即時預報或獨立 25 場外測證據。
