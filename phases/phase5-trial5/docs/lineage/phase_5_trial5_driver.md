# Phase5 Trial5：新 geomagnetic driver GPR 資料血緣

## 狀態與資料界線

狀態：[done]。Trial5 只讀取 Phase5 Trial1 anchors 與 Phase2.6 minute driver，不回寫任何既有 Trial 或 Phase2。feature SQLite 是 `phases/phase5-trial5/data/sqlite/swarm_a_phase4_trial5_driver_features_v5.sqlite`；prediction SQLite 是 `phases/phase5-trial5/data/sqlite/swarm_a_phase4_trial5_driver_gpr_v5.sqlite`。2,295 個 prediction rows 都是 outer held-out 預測。

#### [P4.7] Trial1 anchors 加 Phase2 minute drivers -> Trial5 held-out GPR [done]

```text
prep_phase5_trial5_driver_features.py -> attach_new_drivers()
prep_phase5_trial5_gpr.py -> add_predictions()

同一 storm_id,time_us 對回 P2.6。相鄰分鐘 SYM-H 的 backward difference -> symh_rate_nt_s；
ap_step 與前一日 f107_sfu 直接沿用。outer GroupKFold(5) 20/5 中，outer training
再做 GroupKFold(4) 15/5 選 RBF 或 Matérn 3/2；outer test 只作 predict。
```

```text
phase4_trial5_driver_feature (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691044560000000 (us),
    symh_rate_nt_s: 0.000e+0 (nT/s),
    ap_step: 6.000e+0,
    f107_sfu: 1.729e+2 (sfu),
    residual_log_density: -3.295e-3,
  },
  ...,
]
```

```text
phase4_trial5_prediction (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691044560000000 (us),
    outer_fold_index: 4,
    selected_candidate_name: new_drivers_rbf,
    residual_log_density: -3.295e-3,
    algorithm_version: phase4_trial5_driver_gpr_v5,
  },
  ...,
]
```

`1691044560000000` 是 2023-08-03T06:36:00Z 的相位窗口中心。每場在 outer `test` 恰好一次。全部 held-out anchors 的 Trial4／Trial5 RMSE 是 0.11005／0.13203；沒有泛化改善。
