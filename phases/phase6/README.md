# Phase 6：density-to-decay prediction

共用符號與單位：[VARIABLES.md](../../VARIABLES.md)。

狀態：[done: descriptive]。P6.1 至 P6.4 已完成：

```text
P6.1
三年 L2 density + POD semi-major axis
  -> B_eff = 0.0092292068 m²/kg

P6.2
25 場 Phase 3 M0 + fixed B_eff
  -> 每場磁暴的 predicted semi-major-axis change
  -> error against POD observed change

P6.3
25 場 Phase 5 V2 Ridge density + fixed B_eff
  -> 每場磁暴的 predicted semi-major-axis change
  -> error against POD observed change

P6.4
P6.2 M0 + P6.3 Ridge
  -> 2,262 圈局部下降作底層誤差
  -> 25 場磁暴用 orbit MAE 等權決勝
  -> POD 總量、時間曲線、density 與 endpoint 輔助比較
```

完整方法、25 場逐場結果、每場誤差圖與限制全部收錄於[Phase 6 最終報告](reports/phase_6_final_report.md)。

## 正式結果

- P6.1 只擬合一個全域 `B_eff`，不按年份、磁暴或 block 重調。
- P6.2 只處理 Phase 3 M0 的 25 場磁暴 `t0-2 days` 至 `t0+4 days` 窗口。M0 是 NRLMSIS 2.0 full density。
- P6.2 直接讀 Phase 3 `phase3_prediction_minute.rho_msis_full_phase_kg_m3`，不讀 Phase 4 D-model。
- P6.3 直接讀 Phase 5 V2 `density_comparison.rho_ridge_phase_kg_m3`。
- 每場磁暴各自歸零，25 場不接成連續軌道。
- 正式磁暴分數為 Ridge 15 勝、M0 10 勝、0 平手；每場磁暴等權。
- 25 場等權平均 orbit MAE：M0 `5.460 m/orbit`，Ridge `5.425 m/orbit`。
- 底層共有 2,262 個有效圈間區間；誤差分析使用各場逐圈 MAE。
- 磁暴強度比較使用每場最低 SYM-H，以及該場逐圈誤差的 MAE。
- 所有結果都是探索性描述，不是獨立 forecast skill。

## 正式資料

- `data/sqlite/swarm_a_phase6_1_l2_minute_pairs_v1.sqlite`
- `data/sqlite/swarm_a_phase6_1_beff_v1.sqlite`
- `data/sqlite/swarm_a_phase6_2_m0_error_v1.sqlite`
- `data/sqlite/swarm_a_phase6_3_ridge_decay_v1.sqlite`
- `data/sqlite/swarm_a_phase6_4_decay_comparison_v1.sqlite`
- `data/sqlite/swarm_a_phase6_4_orbit_scores_v1.sqlite`

資料契約：

- [P6.1 lineage](docs/lineage/phase6_1_beff.md)
- [P6.2 lineage](docs/lineage/phase6_2_m0_error.md)
- [P6.3 lineage](docs/lineage/phase6_3_ridge_decay.md)
- [P6.4 lineage](docs/lineage/phase6_4_decay_comparison.md)

## 目錄

```text
code/     P6.1 至 P6.4 計算入口
data/     P6.1 至 P6.4 SQLite 衍生輸出
docs/     plan、lineage 與 retained research
figures/  P6.4 時間曲線與 retained figures
reports/  Phase 6 單一最終報告
tests/    P6.1 至 P6.4 可重跑檢查
```

Phase 4 D-model 的舊 P6.2 結果已被 Phase 3 M0 誤差分析取代，不是 Phase 6 正式輸入或結論。
