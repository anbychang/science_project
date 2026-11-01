# Phase 4 v2 共同 tau 資料血緣

狀態：[done]。v2 只讀 Phase 4 v1 目錄保存的 Phase 2/3 快照，另寫本目錄的三個衍生 SQLite：`data/sqlite/shared_tau_grid_v1.sqlite`、`data/sqlite/shared_tau_fine_v1.sqlite`、`data/sqlite/swarm_a_phase4_v2_shared_tau.sqlite`。v1 checkpoint 不回寫。25 場、214,907 個 UTC 分鐘錨點沿用來源 `{storm_id, time_us}`；密度與 SME 響應仍是中心 $u\pm\pi$ 相位平均。

#### [P4.v2.1] 共同 tau 粗掃 [done]

```text
prep_shared_tau_grid.py -> fit_shared_tau_grid()

0–15 h、每 0.1 h；每格重新擬合各場 0<R_k<2 和共同 G>0。
損失先算各場對數密度 MSE，再對 25 場等權平均。
```

```text
phase3_prediction_minute (唯讀快照；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691041800000000 (us),
    rho_l2_phase_kg_m3: 6.920e-13 (kg/m^3),
    rho_msis_quiet_phase_kg_m3: 6.530e-13 (kg/m^3)
  },
  ...
]

geomag_1min_v2 (Phase 2 raw-derived checkpoint；欄位節錄)
[
  {
    time_us: 1691041800000000 (us),
    sme_nt: 1.523e+2 (nT),
    sme_valid: 1
  },
  ...
]

storm_minute_feature_v5 (Phase 2；欄位節錄)
[
  {
    source_time_us: 1691041800000000 (us),
    u_rel_rad: -1.916e+2 (rad)
  },
  ...
]

storm_density_1min_v5 (Phase 2；欄位節錄)
[
  {
    source_time_us: 1691041800000000 (us),
    paired_sample_count: 2
  },
  ...
]
```

```text
shared_tau_grid (derived；欄位節錄)
[
  {
    tau_hours: 4.800e+0 (h),
    gain_per_nt: 6.911e-4 (1/nT),
    event_equal_rmse_log_density: 1.131e-1,
    algorithm_version: shared_tau_grid_v1
  },
  ...
]
```

`1691041800000000` 是 2023-08-03T05:50:00Z 的來源分鐘錨點；粗掃輸出以候選 `tau_hours` 為 key，不是逐分鐘表。

#### [P4.v2.2] 最佳區間細掃 [done]

```text
prep_shared_tau_fine.py -> fit_fine_grid()

4.6–4.9 h、每 0.01 h；原生 SME 重新濾波及相位平均。
每格重估各場 R_k 與共同 G，不內插粗掃結果。
```

```text
phase3_prediction_minute、geomag_1min_v2、storm_minute_feature_v5、storm_density_1min_v5
(同 P4.v2.1 的來源與 key；唯讀)
```

```text
shared_tau_fine (derived；欄位節錄)
[
  {
    tau_hours: 4.750e+0 (h),
    gain_per_nt: 6.898e-4 (1/nT),
    event_equal_rmse_log_density: 1.131e-1,
    algorithm_version: shared_tau_fine_v1
  },
  ...
]
```

粗掃有 151 筆，細掃有 31 筆。細掃最小誤差對應 4.75 h；這是同資料選模，不能當成物理時間常數或未見事件的最佳值。

#### [P4.v2.3] 固定共同 tau -> 逐分鐘密度 [done]

```text
prep_phase4_v2_density.py -> fitted_density() -> main()

固定 tau=4.75 h，重新擬合 25 個 R_k 與共同 G。
rho_v2 = rho_MSIS,q,phase * R_k * exp(G * H_tau,phase)。
```

```text
phase3_prediction_minute (唯讀快照；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691041800000000 (us),
    rho_l2_phase_kg_m3: 6.920e-13 (kg/m^3),
    rho_msis_quiet_phase_kg_m3: 6.530e-13 (kg/m^3)
  },
  ...
]

geomag_1min_v2、storm_minute_feature_v5、storm_density_1min_v5
(同 P4.v2.1 的來源與 key；唯讀)
```

```text
phase4_v2_minute (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691041800000000 (us),
    rho_phase4_v2_phase_kg_m3: 6.682e-13 (kg/m^3),
    residual_log_density: 3.506e-2,
    r_fit: 9.343e-1,
    tau_hours: 4.750e+0 (h),
    gain_per_nt: 6.898e-4 (1/nT),
    algorithm_version: phase4_v2_shared_tau_475_v1
  },
  ...
]
```

輸出沿用來源 `{storm_id, time_us}`；`time_us` 仍是同一 UTC 分鐘錨點。`phase4_v2_events` 保存每場 $R_k$、筆數、RMSE；metadata 保存選模與回溯界線。214,907 筆分鐘列、25 場，`PRAGMA integrity_check=ok`；逐分鐘重算的事件等權 RMSE 0.113058769603 與細掃一致。Phase 5／6 既有結果仍使用 v1，未由 v2 重算。
