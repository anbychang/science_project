# Phase4 Trial4：時間、Trial4 tau、季節 GPR 資料血緣

## 狀態與資料界線

狀態：[done]。Phase4 Trial4 只讀取 Phase4 Trial1 的保存錨點與固定 Phase3 Trial4 D-model，不回寫 Trial1--Trial3、Phase3 Trial4、Phase 3 或 Phase 2。SQLite 為 `phases/phase4-trial4/data/sqlite/swarm_a_phase4_trial4_time_tau_season_nested_v4.sqlite`；它的 2,295 個 prediction rows 都是 outer held-out GPR 預測。`tau_hours` 是固定的 Phase3 Trial4 event fit，只允許 retrospective 解讀。

```text
Phase4 Trial1 anchors
  -> P4.6 relative time, fixed tau, cyclic season
  -> inner 15/5 kernel selection -> outer 20/5 held-out prediction
```

#### [P4.6] Phase4 Trial1 錨點 -> Trial4 時間、tau、季節 held-out GPR 預測 [done]

```text
prep_phase4_trial4_time_tau_season.py -> add_predictions()

storm_id 的 UTC event time -> relative_time_hours。time_us 的 UTC annual angle ->
season_sin, season_cos。固定 seed 的五個 outer GroupKFold(5) 20/5 splits 中，
各 outer training split 再以 GroupKFold(4) 的 15/5 inner splits 選 RBF 或 Matérn 3/2。
固定 Phase3 Trial4 tau 不在任何 split 重估；outer test storm 只作 predict。
```

```text
phase4_trial4_gpr_prediction (derived；Phase4 Trial1；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691044560000000 (us),
    tau_hours: 6.200e+0 (h),
    residual_log_density: -3.295e-3,
  },
  ...,
]
```

```text
phase4_trial4_prediction (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691044560000000 (us),
    outer_fold_index: 4,
    selected_candidate_name: time_tau_season_matern32,
    relative_time_hours: -4.717e+1 (h),
    tau_hours: 6.200e+0 (h),
    season_sin: -5.201e-1,
    season_cos: -8.541e-1,
    rho_trial4_phase_kg_m3: 6.750e-13 (kg/m^3),
    rho_gpr_median_kg_m3: 6.355e-13 (kg/m^3),
    gp_log_residual_mean: -6.036e-2,
    gp_log_residual_std: 1.072e-1,
    algorithm_version: phase4_trial4_time_tau_season_nested_v4,
  },
  ...,
]
```

`1691044560000000` 是 2023-08-03T06:36:00Z 的相位窗口中心。`phase4_trial4_inner_selection` 保存每個 outer fold 的兩個 inner score 與 selected flag；`phase4_trial4_fold_storm` 保存每折 20 個 outer `train` 與 5 個 outer `test` storm。每場在 outer `test` 恰好一次。全部 held-out anchors 的 Trial4／Phase4 Trial4 RMSE 是 0.11005／0.11323；沒有泛化改善。
