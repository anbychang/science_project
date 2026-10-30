# Phase4 Trial1：Trial4 殘差高度 GPR 資料血緣

## 狀態與邊界

狀態：[done]。Phase4 Trial1 讀 Trial4 的固定 D-model minute baseline、Phase 2 P2.6 事件／SME 與 DNSAPOD 原生高度，寫自己的衍生 SQLite。Phase 2、Phase 3、Trial4 都是唯讀來源。

```text
Trial4 residual + P2.6 paired DNSAPOD altitude
  -> P4.1 one-cycle altitude anchors
  -> P4.2 in-sample Trial4 residual GPR
  -> P4.3 SQLite, CSV, figure, report
```

#### [P4.1] Trial4 minute baseline + paired DNSAPOD -> 高度錨點 [done]

```text
prep_phase4_trial4_gpr.py -> collect_native_altitudes(), attach_altitude()

每個 DNSAPOD altitude_m 只在其 native L2 density 與 P2.6 pair count 相同、
MSIS weather driver 可用時納入。每分鐘先按 paired samples 平均，再以同一
u +/- pi centered window 和 pair count 作加權平均。每 2pi 選最近有效中心，
距格點不超過 0.01 圈。
```

```text
phase4_altitude_anchor (derived)
[
  {
    storm_id: S20240511T0214,
    time_us: 1715224320000000 (us),
    altitude_phase_m: 4.828e+5 (m),
    phase_paired_coverage: 1.000e+0,
    algorithm_version: phase4_trial4_altitude_gpr_v1,
  },
  ...
]
```

`phase4_altitude_anchor` 有 2,295 列、25 場，`altitude_phase_m` 範圍是 $4.297\times10^5$ 至 $4.957\times10^5$ m。`time_us` 是相位窗口中心，不是高度瞬時值。

#### [P4.2] Trial4 殘差 + 五個特徵 -> GPR 預測 [done]

```text
prep_phase4_trial4_gpr.py -> fit_anchor_model()

讀 Trial4 residual_log_density 和 h_phase_nt；加入 H_24h、SME、SYM-H、高度。
StandardScaler 在全部 2,295 個描述性錨點 fit。零均值 GPR 使用
ConstantKernel * RBF(ARD) + WhiteKernel、5 次 optimizer restart。
```

```text
phase4_trial4_gpr_prediction (derived)
[
  {
    storm_id: S20240511T0214,
    time_us: 1715224320000000 (us),
    rho_trial4_phase_kg_m3: 1.085e-12 (kg/m^3),
    residual_log_density: -9.280e-3,
    altitude_phase_m: 4.828e+5 (m),
    rho_gpr_median_kg_m3: 1.077e-12 (kg/m^3),
    algorithm_version: phase4_trial4_altitude_gpr_v1,
  },
  ...
]
```

`rho_gpr_median_kg_m3=rho_trial4_phase_kg_m3*exp(gp_log_residual_mean)`。95% 區間以已擬合的 Trial4 與 GPR 參數為條件，並含 WhiteKernel observation noise；不含 Trial4 參數估計不確定性。

#### [P4.3] Phase 4 SQLite -> 可讀輸出 [done]

```text
prep_phase4_trial4_gpr.py -> write_sqlite(), write_csv()
prep_phase4_trial4_figures.py -> main()
```

輸出 SQLite 為 `phases/phase4/data/sqlite/swarm_a_phase4_trial4_altitude_gpr_v1.sqlite`。它有 2,295 個 prediction rows、25 場與 `PRAGMA integrity_check=ok`。CSV 保存逐場及全部錨點的資料內指標；圖保存 25 場 L2、Trial4、Trial4+GPR、條件式區間與高度。

這些輸出只描述同一批資料內曲線。Trial4 和 GPR 都已見過事件期間 L2；不可轉述為獨立預測或高度的因果效果。
