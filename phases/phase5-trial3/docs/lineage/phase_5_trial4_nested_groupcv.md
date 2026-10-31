# Phase5 Trial3：nested storm-group 四特徵 GPR 資料血緣

## 狀態與資料邊界

狀態：[done]。Phase5 Trial3 只讀取 Phase5 Trial1 的已保存錨點與固定 Trial4 D-model，不回寫 Trial1、Trial2、Trial4、Phase 3 或 Phase 2。SQLite 為 `phases/phase5-trial3/data/sqlite/swarm_a_phase4_trial4_nested_groupcv_v3.sqlite`；它的 2,295 個 prediction rows 都是 outer held-out GPR 預測。Trial3 的 kernel 選擇只使用每個 outer training split 的 20 場 storm。

```text
Phase5 Trial1 anchors
  -> P4.5 inner 15/5 kernel selection
  -> outer 20/5 held-out prediction SQLite and CSV
```

#### [P4.5] Phase5 Trial1 五特徵錨點 -> Trial3 nested 四特徵 held-out GPR 預測 [done]

```text
prep_phase5_trial4_trial3.py -> add_predictions()

以 storm_id 做固定 seed 的五個 outer GroupKFold(5) 20/5 splits。每個 outer
training split 再做 GroupKFold(4) 15/5 inner splits，依 inner RMSE 選擇
geomagnetic_rbf 或 geomagnetic_matern32。兩個候選只使用 H_tau_k、H_24h、SME、
SYM-H；outer test storm 只作 predict。Trial4 D-model 固定，不在任何 split 重估。
```

```text
phase4_trial4_gpr_prediction (derived；Phase5 Trial1；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691044560000000 (us),
    h_tau_phase_nt: 1.504e+2 (nT),
    h_24h_phase_nt: 2.287e+2 (nT),
    sme_phase_nt: 1.249e+2 (nT),
    symh_phase_nt: -3.547e+0 (nT),
    altitude_phase_m: 4.956e+5 (m),
    residual_log_density: -3.295e-3,
  },
  ...,
]
```

```text
phase4_trial3_prediction (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691044560000000 (us),
    outer_fold_index: 4,
    selected_candidate_name: geomagnetic_matern32,
    rho_trial4_phase_kg_m3: 6.750e-13 (kg/m^3),
    rho_gpr_median_kg_m3: 5.803e-13 (kg/m^3),
    gp_log_residual_mean: -1.512e-1,
    gp_log_residual_std: 8.002e-2,
    algorithm_version: phase4_trial4_nested_groupcv_v3,
  },
  ...,
]
```

`1691044560000000` 是 2023-08-03T06:36:00Z 的相位窗口中心。`phase4_trial3_inner_selection` 保存每個 outer fold 的兩個 inner RMSE 與 selected flag；`phase4_trial3_fold_storm` 保存每折 20 個 outer `train` 與 5 個 outer `test` storm。每場在 outer `test` 恰好一次。全部 held-out anchors 的 Trial4／Trial3 RMSE 是 0.11005／0.12014；Trial3 沒有泛化改善。
