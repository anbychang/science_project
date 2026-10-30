# Trial5 恢復起始項與恢復項資料血緣

## 狀態與資料邊界

狀態：[working]。Trial5 讀取唯讀 Trial4 SQLite `phases/phase3-trial4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite`，將結果寫入 `phases/phase3-trial5/data/sqlite/swarm_a_trial5_recovery_v1.sqlite`。Trial4 與凍結 Phase 3 都是唯讀輸入。Trial5 以 SYM-H 最低點 $t_0$ 作恢復項的數學錨點；這不是經驗證的物理恢復開始時刻。

```text
Trial4 D-model minute residuals
  -> P5.1 common recovery-time grid and per-event amplitude
  -> P5.2 Trial5 minute table, overview, CSV, figure
```

#### [P5.1] Trial4 minute rows -> shared recovery time and $A_k$ [done]

```text
prep_trial5_recovery.py -> main()

固定 Trial4 的 R_k、tau_k、G。對每場加 A_k*exp[-(t-t0)/T_rec]，只在 t>=t0 生效。
A_k>=0；T_rec=0.1..96.0 h、每 0.1 h 格點。每一格先解析估 A_k，
再以 25 場等權對數密度 MSE 選共同 T_rec。
```

```text
trial4_joint_fit_minute (derived；Trial4 唯讀；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    time_us: 1715393640000000 (us),
    residual_log_density: 1.887e-1,
    r_fit: 6.212e-1,
    tau_hours: 3.000e+0 (h),
  },
  ...
]
```

```text
phases/phase3-trial5/data/analysis/trial5_recovery_models.csv (analysis；欄位節錄)
[
  {
    model: E_trial5_recovery,
    recovery_time_hours: 1.430e+1 (h),
    event_equal_rmse_log_density: 1.013e-1,
  },
  ...
]
```

`1715393640000000` 是 2024-05-11T02:14:00Z 的 $t_0$ 相位分鐘。最佳共同 $T_{\mathrm{rec}}$ 為 14.3 h；這是指定格點、指定 Trial4 基線下的訓練最低值，不是物理冷卻時間量測。

#### [P5.2] Trial4 minute rows + recovery fit -> Trial5 SQLite and diagnostics [done]

```text
prep_trial5_recovery.py -> write_sqlite(), draw_residual_overview()

rho_trial5 = rho_trial4 * exp(recovery_term)。寫入前後檢查 25 場、214907 個 minute rows、
A_k>=0、T_rec>0、逐場分鐘數與 PRAGMA integrity_check。圖每 30 分鐘取一點只影響顯示。
```

```text
trial4_joint_fit_minute (derived；Trial4 唯讀；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    time_us: 1715393640000000 (us),
    rho_trial4_joint_phase_kg_m3: 3.689e-12 (kg/m^3),
    residual_log_density: 1.887e-1,
  },
  ...
]
```

```text
trial5_recovery_minute (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    time_us: 1715393640000000 (us),
    hours_from_t0: 0.000e+0 (h),
    recovery_term_log_density: 2.252e-2,
    rho_trial5_recovery_phase_kg_m3: 3.773e-12 (kg/m^3),
    trial5_residual_log_density: 1.662e-1,
    recovery_time_hours: 1.430e+1 (h),
    algorithm_version: trial5_recovery_v1,
  },
  ...
]
```

Trial5 minute 的 `time_us` 延續 Trial4 key。`recovery_term_log_density` 是額外的對數密度項；`trial5_residual_log_density=ln(rho_l2_phase/rho_trial5_recovery_phase)`。完整 SQLite 的 `integrity_check` 為 `ok`，分鐘表有 214,907 列，總覽有 25 列。

#### [P5.3] 留一事件時間選擇 + 前段振幅 -> 後段驗證 [done]

```text
prep_trial5_recovery_validation.py -> main()
prep_trial5_recovery_horizon_check.py -> main()

每場以其餘 24 場選共同 T_rec。被留出的場只用 t0 後前 6、12、24 或 36 h
估 A_k；只在相應時間之後評分。正值 A_k 是正式檢查；signed A_k 只作限制敏感度診斷。
```

```text
trial4_joint_fit_minute (derived；Trial4 唯讀；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    time_us: 1715480040000000 (us),
    residual_log_density: -2.747e-1,
  },
  ...
]
```

```text
phases/phase3-trial5/data/analysis/trial5_recovery_horizon_models.csv (analysis；欄位節錄)
[
  {
    fit_end_hours: 2.400e+1 (h),
    model: E_positive_recovery_tail,
    event_equal_tail_rmse_log_density: 9.078e-2,
    events_improved: 2,
  },
  ...
]
```

這個 24 h 比較中，Trial4 baseline 的後段 RMSE 為 0.089270，而正值恢復項為 0.090781。共同 $T_{\mathrm{rec}}$ 的留一事件範圍是 11.8–14.7 h；它穩定但不能使 24 h 後殘差泛化改善。因此 P5.1 的 14.3 h 訓練最低點只保留為診斷，不採用為共同恢復常數。
