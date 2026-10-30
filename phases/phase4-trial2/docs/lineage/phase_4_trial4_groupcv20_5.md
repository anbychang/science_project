# Phase4 Trial2：20/5 storm-group GPR 資料血緣

## 狀態與資料邊界

狀態：[done]。Phase4 Trial2 只讀取 Phase4 Trial1 的已保存錨點與固定 Trial4 D-model，不回寫 Trial1、Trial4、Phase 3 或 Phase 2。SQLite 為 `phases/phase4-trial2/data/sqlite/swarm_a_phase4_trial4_altitude_groupcv20_5_v2.sqlite`；它的 2,295 個 prediction rows 都是 held-out GPR 預測。Trial4 本身已見過全部 25 場，因此 Trial2 只驗證 GPR 跨 storm 泛化。

```text
Phase4 Trial1 anchors
  -> P4.4 five storm-group 20/5 GPR fits
  -> held-out prediction SQLite, CSV, figure
```

#### [P4.4] Phase4 Trial1 五特徵錨點 -> Trial2 20/5 held-out GPR 預測 [done]

```text
prep_phase4_trial4_groupcv.py -> add_held_out_predictions()

以 storm_id 做固定 seed 的 GroupKFold(5)。每折 20 場 fit StandardScaler 和
zero-mean GPR；5 場完整 storm 只作 predict。每個 anchor 僅出現在一折測試集。
Trial4 D-model 固定，不在折內重估。
```

```text
phase4_trial4_gpr_prediction (derived；Phase4 Trial1；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    time_us: 1715224320000000 (us),
    h_tau_phase_nt: 1.449e+1 (nT),
    h_24h_phase_nt: 7.276e+1 (nT),
    sme_phase_nt: 9.827e+1 (nT),
    symh_phase_nt: 2.611e+0 (nT),
    altitude_phase_m: 4.828e+5 (m),
    residual_log_density: -9.280e-3,
  },
  ...
]
```

```text
phase4_groupcv20_5_prediction (derived；欄位節錄)
[
  {
    storm_id: S20240511T0214,
    time_us: 1715224320000000 (us),
    fold_index: 4,
    rho_trial4_phase_kg_m3: 1.085e-12 (kg/m^3),
    rho_gpr_median_kg_m3: 1.085e-12 (kg/m^3),
    gp_log_residual_mean: -3.458e-5,
    gp_log_residual_std: 1.193e-1,
    algorithm_version: phase4_trial4_altitude_groupcv20_5_v2,
  },
  ...
]
```

`1715224320000000` 是 2024-05-09T03:12:00Z 的相位窗口中心。每折的 `phase4_groupcv20_5_fold_storm` 保存 20 個 `train` 與 5 個 `test` storm；每場在 `test` 恰好一次。全部 held-out anchors 的 Trial4／GPR RMSE 是 0.11005／0.11028，沒有泛化改善。
