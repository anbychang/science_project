# Phase4 Trial6 資料血緣

狀態：[done]。只讀既有 Phase 2、Phase 3 Trial4、Phase4 Trial1 與 DNSAPOD 來源；新輸出留在 `phases/phase4-trial6/`。Phase4 Trial1 SQLite 只提供原始整圈錨點與固定 Trial4 密度，不讀其 GPR 預測。此 Trial 沒有改寫任何 checkpoint。`time_us` 為 UTC 微秒：原生樣本是觀測時刻，分鐘 key 是來源分鐘標籤，錨點 key 是整圈相位窗口中心。

來源與輸出路徑：

```text
phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_6_final.sqlite
phases/phase3-trial4/data/sqlite/swarm_a_phase3_quiet_density_v1.sqlite
phases/phase4-trial1/data/sqlite/swarm_a_phase4_trial4_altitude_gpr_v1.sqlite
phases/phase0/data/raw/swarm_density_pod/manifest_dnsapod_20230701_20260630.json
phases/phase4-trial6/data/sqlite/swarm_a_trial6_day_fraction.sqlite
phases/phase4-trial6/data/analysis/trial6_block_predictions.csv
phases/phase4-trial6/data/analysis/trial6_block_metrics.csv
phases/phase4-trial6/data/analysis/trial6_event_metrics.csv
phases/phase4-trial6/data/analysis/trial6_stress_predictions.csv
phases/phase4-trial6/data/analysis/trial6_stress_metrics.csv
phases/phase4-trial6/data/analysis/trial6_interpolation_rule_blocks.csv
phases/phase4-trial6/data/analysis/trial6_interpolation_rule_predictions.csv
phases/phase4-trial6/data/analysis/trial6_interpolation_rule_summary.csv
```

#### [P4.8.1] 原生樣本與整圈錨點 -> 日側比例 [done]

```text
prep_trial6_day_fraction.py -> main()

P2 分鐘相位 + quiet-MSIS 配對數 + DNSAPOD 原生位置
  -> 相同有效配對樣本的日側旗標
  -> 中心 u +/- pi 窗口內日側數 / 全部配對數

日側：UTC 與地理位置的太陽高度角 > 0 deg；無大氣折射。
每分鐘原生數須等於既有 quiet-MSIS 配對數；全部 25 場通過。
```

```text
storm_minute_feature_v5 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    source_time_us: 1691041740000000 (us),
    u_rel_rad: -1.916e+2 (rad)
  },
  ...
]

phase3_quiet_density_minute (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691041740000000 (us),
    paired_sample_count: 2
  },
  ...
]

SW_OPER_DNSAPOD_2__20230803T000000_20230803T235930_0301.ZIP (raw；欄位節錄)
[
  {
    time_us: 1691041740000000 (us),
    latitude_deg: -8.416e+1 (deg),
    longitude_deg: -1.147e+2 (deg),
    rho_l2_kg_m3: 3.687e-13 (kg/m^3)
  },
  ...
]

phase4_trial4_gpr_prediction (derived；只讀 Trial4 欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691044560000000 (us),
    rho_l2_phase_kg_m3: 6.728e-13 (kg/m^3),
    rho_trial4_phase_kg_m3: 6.750e-13 (kg/m^3),
    residual_log_density: -3.295e-3
  },
  ...
]
```

```text
trial6_anchor_feature (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691044560000000 (us),
    elapsed_hours: 0.000e+0 (h),
    day_count: 95,
    paired_count: 190,
    day_fraction: 5.000e-1,
    support_start_us: 1691041740000000 (us),
    support_end_us: 1691047380000000 (us),
    residual_log_density: -3.295e-3,
    algorithm_version: phase4_trial6_day_fraction_v1
  },
  ...
]
```

#### [P4.8.2] 整圈殘差 -> 六小時遮住補值 [done]

```text
calc_trial6_ridge.py -> evaluate_storm()

每場每 12 h 遮住 6 h 錨點；訓練錨點的相位支撐不得碰到遮住區。
同一目標點比較零修正、前後線性內插、時間 Ridge、時間加日側比例 Ridge。
Ridge 固定每 12 h 轉折與 alpha=1.0；僅訓練區標準化。
輸出 key 為 {storm_id, block_start_us, time_us}；同一 time_us 在本試驗只評一次。
```

```text
trial6_anchor_feature (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691067180000000 (us),
    elapsed_hours: 6.283e+0 (h),
    day_count: 94,
    paired_count: 190,
    day_fraction: 4.947e-1,
    support_start_us: 1691064360000000 (us),
    support_end_us: 1691070000000000 (us),
    residual_log_density: -6.583e-3
  },
  ...
]
```

```text
trial6_block_predictions.csv (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    block_start_us: 1691066160000000 (us),
    time_us: 1691067180000000 (us),
    residual_true: -6.583e-3,
    trial4: 0.000e+0,
    interpolation: 1.369e-2,
    ridge_time: 1.275e-2,
    ridge_time_day: 1.356e-2
  },
  ...
]
```

#### [P4.8.3] 遮住點 -> 逐段與逐場分數 [done]

```text
calc_trial6_ridge.py -> score(), main()

對數殘差預測與實測相減，逐段及逐場計算 RMSE、MAE。
25 場合併分數以 1,051 個被遮住錨點直接計算；275 段非獨立樣本。
Trial4 本身已用全部 25 場 L2 擬合；此處只檢查固定基線上的殘差補值。
```

```text
trial6_block_predictions.csv (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    block_start_us: 1691066160000000 (us),
    time_us: 1691067180000000 (us),
    residual_true: -6.583e-3,
    interpolation: 1.369e-2
  },
  ...
]
```

```text
trial6_event_metrics.csv (derived；欄位節錄)
[
  {
    storm_id: all_storms,
    block_count: 275,
    heldout_count: 1051,
    trial4_rmse: 1.059e-1,
    interpolation_rmse: 4.737e-2,
    ridge_time_rmse: 7.002e-2,
    ridge_time_day_rmse: 7.094e-2
  }
]
```

#### [P4.8.4] $t_0$ 與強變化區 -> 定點遮住補值 [done]

```text
calc_trial6_stress.py -> load_activity(), most_variable_start(), run_stress(), main()

每場先遮 t0 - 3 h 到 t0 + 3 h。
再以 1 h 步長尋找不與 t0 區段重疊的 6 h 窗；每個窗的 12 個半小時
SYM-H 中位數之相鄰絕對差加總，選總變化量最大者。
選段只讀 P2 SYM-H，不讀 L2 殘差。兩窗沿用 P4.8.2 的相位支撐隔離與四種補值。
後者只表示 SYM-H 起伏大，不等於物理上最複雜的磁暴脈衝。
```

```text
storm_event_t0_phase_v5 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    t0_time_us: 1691214360000000 (us),
    symh_min_nt: -103 (nT)
  },
  ...
]

storm_minute_feature_v5 (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    source_time_us: 1691164920000000 (us),
    symh_nt: 1.300e+1 (nT)
  },
  ...
]

trial6_anchor_feature (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691169060000000 (us),
    elapsed_hours: 3.458e+1 (h),
    day_fraction: 5.000e-1,
    residual_log_density: 8.511e-2
  },
  ...
]
```

```text
trial6_stress_predictions.csv (derived；欄位節錄)
[
  {
    selection: symh_variation_outside_t0,
    storm_id: S20230805T0546,
    t0_time_us: 1691214360000000 (us),
    block_start_us: 1691164920000000 (us),
    time_us: 1691169060000000 (us),
    symh_variation_nt: 6.900e+1 (nT),
    residual_true: 8.511e-2,
    interpolation: 6.281e-2,
    ridge_time: 5.455e-2,
    ridge_time_day: 5.274e-2
  },
  ...
]

trial6_stress_metrics.csv (derived；欄位節錄)
[
  {
    selection: symh_variation_outside_t0,
    storm_id: all_storms,
    heldout_count: 95,
    trial4_rmse: 1.291e-1,
    interpolation_rmse: 9.889e-2,
    ridge_time_rmse: 9.470e-2,
    ridge_time_day_rmse: 9.420e-2
  },
  ...
]
```

#### [P4.8.5] 缺口外偏差 -> 事前內插選擇 [done]

```text
calc_trial6_interpolation_rule.py -> decide(), same_sign_decision(), main()

規則一只比較真正缺口前後最近可用錨點的殘差正負號。
規則二把真正缺口 s..s+6 h 外的 s-12..s-6 h、s+12..s+18 h
各當假缺口；兩段內插 RMSE 都低於零修正才補真正缺口。
每次假缺口訓練同時排除真正缺口的原生相位支撐。
真正缺口的 L2 殘差只在選擇完成後用於評分；缺側資料不足則保留 Trial4。
定期、t0 與 SYM-H 強變化三類各自計分；同批事件探索，非確認性驗證。
```

```text
trial6_anchor_feature (derived；缺口外錨點；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691055900000000 (us),
    elapsed_hours: 3.150e+0 (h),
    residual_log_density: 2.410e-2,
    support_start_us: 1691053080000000 (us),
    support_end_us: 1691058720000000 (us)
  },
  {
    storm_id: S20230805T0546,
    time_us: 1691089860000000 (us),
    elapsed_hours: 1.258e+1 (h),
    residual_log_density: -7.260e-3,
    support_start_us: 1691087040000000 (us),
    support_end_us: 1691092680000000 (us)
  }
]

trial6_block_predictions.csv (derived；真正缺口；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    block_start_us: 1691066160000000 (us),
    time_us: 1691067180000000 (us),
    residual_true: -6.583e-3,
    interpolation: 1.369e-2
  },
  ...
]
```

```text
trial6_interpolation_rule_predictions.csv (derived；欄位節錄)
[
  {
    selection: regular_grid,
    storm_id: S20230805T0546,
    block_start_us: 1691066160000000 (us),
    time_us: 1691067180000000 (us),
    residual_true: -6.583e-3,
    always_interpolate: 1.369e-2,
    same_sign_apply: 0,
    same_sign_prediction: 0.000e+0,
    algorithm_version: phase4_trial6_interpolation_rules_v1
  },
  ...
]

trial6_interpolation_rule_summary.csv (derived；欄位節錄)
[
  {
    selection: regular_grid,
    block_count: 275,
    heldout_count: 1051,
    apply_count: 148,
    same_sign_apply_count: 191,
    trial4_rmse: 1.059e-1,
    always_interpolate_rmse: 4.737e-2,
    rule_rmse: 6.888e-2,
    same_sign_rmse: 5.755e-2,
    algorithm_version: phase4_trial6_interpolation_rules_v1
  },
  ...
]
```
