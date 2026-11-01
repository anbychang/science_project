# Phase 6：density-to-decay closure

狀態：[done]。Phase 6 正式範圍只有 P6.1 與 P6.2：

```text
P6.1
三年 L2 density + POD semi-major axis
  -> B_eff = 0.0092292068 m²/kg

P6.2
25 場 Phase 4 D-model density + fixed B_eff
  -> 每場磁暴的 predicted semi-major-axis change
```

正式結論、公式、25 場逐場結果與限制見 [Phase 6 最終報告](reports/phase_6_final_report.md)。

## 正式結果

- P6.1 只擬合一個全域 `B_eff`，不按年份、磁暴或 block 重調。
- P6.2 只處理 Phase 4 的 25 場磁暴 `t0-2 days` 至 `t0+4 days` 窗口。
- 每場磁暴各自歸零，25 場不接成連續軌道。
- Phase 4 少估 15 場、多估 10 場；逐場 endpoint MAE 為 `29.03 m`。

## 正式資料

- `data/sqlite/swarm_a_phase6_1_l2_minute_pairs_v1.sqlite`
- `data/sqlite/swarm_a_phase6_1_beff_v1.sqlite`
- `data/sqlite/swarm_a_phase6_2_phase4_decay_v1.sqlite`

資料契約：

- [P6.1 lineage](docs/lineage/phase6_1_beff.md)
- [P6.2 lineage](docs/lineage/phase6_2_phase4_decay.md)

## 目錄

```text
code/     P6.1、P6.2 計算入口
data/     P6.1、P6.2 SQLite 衍生輸出
docs/     plan、lineage 與 retained research
figures/  retained figures
reports/  Phase 6 最終報告與 retained reports
tests/    P6.1、P6.2 可重跑檢查
```

舊的 quiet-window、paper baseline、NRLMSIS scale 與逐圈 sensitivity 文件保留作研究歷史，不是 Phase 6 的正式輸入或結論。
