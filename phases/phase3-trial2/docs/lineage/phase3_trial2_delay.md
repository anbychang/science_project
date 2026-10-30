# Phase 3 Trial 2：共用有效時間位移資料血緣

狀態：[done]。此試驗只讀 Phase 2 與 Phase 3 的既有 checkpoint，另建 Trial 2 working output。來源為 `phases/phase2/data/sqlite/swarm_a_phase2_sme_p2_6_final.sqlite`、`phases/phase3/data/sqlite/swarm_a_phase3_h_tau_phase_v1.sqlite`、`phases/phase3/data/sqlite/swarm_a_phase3_prediction_tau465_exploratory.sqlite`；輸出為 `phases/phase3-trial2/data/sqlite/swarm_a_phase3_trial2_delay_v1.sqlite`。重算入口是 `phases/phase3-trial2/code/prep_trial2_delay.py`，完整選參數規則與結果見[計畫](../plans/PLAN.md)和[報告](../../reports/phase3_trial2_delay_report.md)。

#### [T2.1] 來源配對與平衡切分 [done]

```text
load_trial2_inputs.py -> load_continuous_sme(), load_events()
calc_trial2_delay.py -> balanced_splits()

Phase 2 連續有效 SME + Phase 3 有效中心相位錨點與既定 R_k
  -> 固定種子 20261029；20 輪各將 25 場分成五組 20/5
  -> trial2_split
```

```text
geomag_1min_v2 (raw；欄位節錄)
[
  {
    time_us: 1691041800000000 (us),
    sme_nt: 1.523e+02 (nT),
    sme_valid: 1
  },
  ...
]

phase3_h_tau_minute (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691041800000000 (us),
    u_rel_rad: -1.916e+02 (rad),
    paired_sample_count: 2,
    phase_is_valid_80pct: 1
  },
  ...
]

phase3_prediction_minute (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691041800000000 (us),
    rho_l2_phase_kg_m3: 6.920e-13 (kg/m^3),
    rho_msis_quiet_phase_kg_m3: 6.530e-13 (kg/m^3)
  },
  ...
]

phase3_25storm_overview (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    r_candidate: 8.299e-01
  },
  ...
]
```

```text
trial2_split (derived；欄位節錄)
[
  {
    fold: 0,
    storm_id: S20230805T0546,
    role: train,
    algorithm_version: phase3_trial2_delay_v1
  },
  ...
]
```

`time_us=1691041800000000` 是 2023-08-03 05:50:00 UTC 的 SME 分鐘與相位錨點時刻。相位值由配對 L2 時刻在中心窗口平均；切分以 `storm_id` 分組，輸出主鍵改為 `(fold, storm_id)`。每場恰好測試 20 次。`r_candidate` 是來源欄名；本試驗沿用 Phase 3 已確定的暴前 $R_k$ 校準值，不重新估計。

#### [T2.2] 訓練選參數與留出評分 [done]

```text
prep_trial2_delay.py -> first_stage()
calc_trial2_delay.py -> response_statistics(), fit_gain(), heldout_rmse()
prep_trial2_outputs.py -> write_tables()

X=SME-65 nT；逐分鐘連續遞迴，先計算 H 再作 u±π 配對平均。
每折只用 train 事件選共用 τ、G，固定後再選 δ=0..360 min、步長 15 min。
test 事件只用其既定暴前 R_k 與事件密度作 RMSE 評分。
```

```text
trial2_split (derived；欄位節錄)
[
  {
    fold: 0,
    storm_id: S20231021T0728,
    role: test,
    algorithm_version: phase3_trial2_delay_v1
  },
  ...
]
```

```text
trial2_fold (derived；欄位節錄)
[
  {
    fold: 0,
    m1_tau_hours: 4.500e+00 (h),
    m1_gain_per_nt: 6.752e-04 (1/nT),
    delta_minutes: 0 (min),
    algorithm_version: phase3_trial2_delay_v1
  },
  ...
]

trial2_test_score (derived；欄位節錄)
[
  {
    fold: 0,
    storm_id: S20231021T0728,
    rmse_m1: 9.130e-02,
    rmse_delay: 9.130e-02,
    algorithm_version: phase3_trial2_delay_v1
  },
  ...
]
```

`trial2_fold` 以 `fold` 為鍵；`trial2_test_score` 以 `(fold, storm_id)` 為鍵。兩個 RMSE 都是對數密度誤差。等權事件留出改善為 0%，未達預先設定的 3% 門檻；`trial2_joint_grid` 因此沒有資料，逐段 $\tau_j$ 亦未重擬合。100 組切分重用同一批 25 場，不能當作 100 組獨立事件。

#### [T2.3] 固定主線參數的描述性診斷 [done]

```text
prep_trial2_delay.py -> check_mainline(), full_data_delay()
prep_trial2_outputs.py -> write_tables(), draw_figure()

固定 Phase 3 M1 的 τ=4.65 h、G=0.0007032326071208369 (1/nT)。
比較 δ=0..360 min 的全資料合併 RMSE；單場最低點只作資料內診斷。
```

```text
phase3_prediction_minute (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    time_us: 1691041800000000 (us),
    h_phase_nt: 1.297e+02 (nT),
    rho_l2_phase_kg_m3: 6.920e-13 (kg/m^3)
  },
  ...
]
```

```text
trial2_full_delta_grid (derived；欄位節錄)
[
  {
    delta_minutes: 0 (min),
    pooled_rmse_log_density: 2.065e-01,
    algorithm_version: phase3_trial2_delay_v1
  },
  ...
]

trial2_event_delta_grid (derived；欄位節錄)
[
  {
    storm_id: S20230805T0546,
    delta_minutes: 0 (min),
    rmse_log_density: 1.355e-01,
    algorithm_version: phase3_trial2_delay_v1
  },
  ...
]
```

`trial2_full_delta_grid` 以 `delta_minutes` 為鍵；`trial2_event_delta_grid` 以 `(storm_id, delta_minutes)` 為鍵。$\delta=0$ 的相位響應與主線最大差 $1.512\times10^{-11}$ nT。全資料與單場最低點均使用事件期間 L2，不能作留出預測成績；圖見[位移診斷](../../figures/delta_diagnostic.png)。
