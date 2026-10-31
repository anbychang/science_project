# Phase 5 跨場逐圈 GPR 資料血緣

狀態：[done]，只供描述性回溯分析。Phase 5 唯讀 Phase 4 已固定的 `phases/phase4/data/sqlite/swarm_a_phase3_h_tau_phase_v1.sqlite` 與 `phases/phase4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite`。衍生輸出是本機 `phases/phase5/data/sqlite/swarm_a_phase5_pooled_orbit_gpr_v1.sqlite`；原始表與 Phase 4 的擬合參數不回寫。先前的 CSV 保留在 `data/retained_csv_v1/` 供比對，不是現行資料來源。

`time_us` 是 UTC 微秒，沿用 Phase 4 的分鐘 key，代表該分鐘的來源時刻；相位平均以該分鐘的 `u_rel_rad` 為中心。下面示例的 `1691078520000000` 是 2023-08-03T16:02:00Z；輸出仍用同一個 `{storm_id,time_us}`。模型檔另存 `data/models/`，不放進 SQLite；資料表可用 SQL 查詢。

## 逐圈錨點 [done]

```text
load_phase5_trial4_orbits.py -> load_events()
prep_phase5_gpr_sqlite.py -> write_sqlite()

Phase 4 的有效分鐘 -> 每個 2pi 相位格點選最近一分鐘 -> 逐圈錨點
只用 phase_is_valid_80pct=1，距離格點不得超過 0.02pi；每場依 time_us 排序。
```

```text
phase3_h_tau_minute (Phase 4 唯讀快照；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691078520000000 (us),
    u_rel_rad: -1.508e2 (rad),
    phase_is_valid_80pct: 1,
    phase_paired_coverage: 1.000e0
  }
]

trial4_joint_fit_minute (Phase 4 D-model；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691078520000000 (us),
    rho_l2_phase_kg_m3: 6.660e-13 (kg/m^3),
    rho_trial4_joint_phase_kg_m3: 6.813e-13 (kg/m^3),
    residual_log_density: -2.273e-2
  }
]
```

```text
phase5_orbit_anchor (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691078520000000 (us),
    u_rel_rad: -1.508e2 (rad),
    rho_l2_phase_kg_m3: 6.660e-13 (kg/m^3),
    rho_trial4_phase_kg_m3: 6.813e-13 (kg/m^3),
    residual_log_density: -2.273e-2,
    algorithm_version: phase4_direct_trial4_pooled_orbit_gpr_v1
  }
]
```

## 跨場逐圈殘差修正 [done]

```text
prep_phase5_direct_gpr.py -> run()
prep_phase5_gpr_sqlite.py -> write_sqlite()

同一場的相鄰錨點 -> 四個 GPR 輸入 -> 預測誤差變化 -> 修正當圈 D-model
輸入為 log(D_n), log(D_{n-1}), log(L2_{n-1}), e_{n-1}。
目標為 e_n - e_{n-1}，其中 e=log(L2/D)。
五折各以 20 場訓練、5 場完整留出；測試時當圈 L2 只供評分。
```

```text
phase5_orbit_anchor (derived；上一圈與當圈，欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691072880000000 (us),
    rho_l2_phase_kg_m3: 6.836e-13 (kg/m^3),
    rho_trial4_phase_kg_m3: 6.890e-13 (kg/m^3),
    residual_log_density: -7.907e-3
  },
  {
    storm_id: S20230805T0546,
    time_us: 1691078520000000 (us),
    rho_trial4_phase_kg_m3: 6.813e-13 (kg/m^3)
  }
]
```

```text
phase5_orbit_prediction (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691078520000000 (us),
    previous_time_us: 1691072880000000 (us),
    fold_index: 4,
    comparable_2115: 1,
    actual_log_residual: -2.273e-2,
    previous_log_residual: -7.907e-3,
    pooled_gpr_log_residual: -4.360e-3,
    rho_pooled_gpr_kg_m3: 6.784e-13 (kg/m^3),
    algorithm_version: phase4_direct_trial4_pooled_orbit_gpr_v1
  }
]

phase5_summary_metric (derived；欄位節錄)
[
  {
    scope: comparable_trial9_positions,
    orbit_count: 2115,
    trial4_log_rmse: 1.101e-1,
    previous_orbit_log_rmse: 4.211e-2,
    pooled_gpr_log_rmse: 3.926e-2,
    algorithm_version: phase4_direct_trial4_pooled_orbit_gpr_v1
  }
]
```

`phase5_fold`、`phase5_fold_storm` 保存五折及場次；`phase5_event_metric` 保存 25 場分數；`phase5_metadata` 保存來源路徑、版本和限制。這是固定 Phase 4 D-model 之上的回溯殘差檢查：Phase 4 的事件參數曾由完整事件 L2 擬合，不能把這份留場 GPR 分數稱為端到端預報分數。
