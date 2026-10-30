# Trial 索引

狀態：[done]。本頁是所有 Trial 的入口，不把不同資料、不同校準機會或資料內／held-out 分數混成同一場競賽。現行下游密度基線只有 `Phase 3 Trial4 D-model`；Phase4 Trial1--Trial5 都未進入 Final。

## 狀態定義

- `[historical]`：保留研究過程，不是現行下游基線。
- `[done: descriptive]`：完成資料內描述，不能視為外測或預報。
- `[done: negative]`：完成 held-out 檢查，沒有通過採用條件。
- `[working]`：有初步結果，尚未成為下游輸入或結論。

## Phase3 試驗

| 位置 | 狀態 | 問題與結果 | 報告 |
| --- | --- | --- | --- |
| `phase3-trial/` | [historical] | M2 倍率、共同／逐圈 `tau` 與交替擬合探索；資料內格點最低值不可升格為物理量 | [倍率](../phases/phase3-trial/reports/m2_r_grid_trial.md)、[共同 tau](../phases/phase3-trial/reports/m2_tau_fixed_r.md)、[交替擬合](../phases/phase3-trial/reports/m2_alternating_trial.md)、[逐圈 tau](../phases/phase3-trial/reports/m2_phase2_orbit_tau_trial.md) |
| `phase3-trial2/` | [done: negative] | 共用有效時間位移 `delta`；100 個 20/5 split 都選 `delta=0`，沒有改善 | [Trial2 報告](../phases/phase3-trial2/reports/phase3_trial2_delay_report.md) |
| `phase3-trial3/` | [historical] | 單場 SME／響應線性診斷；只提供個案圖，不構成跨 storm 模型選擇 | [SME 個案圖](../phases/phase3-trial3/figures/s20250101_sme_l2.png)、[線性診斷圖](../phases/phase3-trial3/figures/s20250101_response_linearity.png) |
| `phase3-trial4/` | [done: descriptive] | 每場自由 $R_k,\tau_k$ 與共同正 $G$；D-model RMSE 0.109953，是現行下游基線 | [joint-fit 報告](../phases/phase3-trial4/reports/trial4_joint_fit_tau15_report.md)、[資料血緣](../phases/phase3-trial4/docs/lineage/trial4_joint_fit_tau15.md) |
| `phase3-trial5/` | [working] | Trial4 上加入每場 recovery 起始項與共同恢復時間；目前只改善同資料貼合，未獨立驗證 | [Trial5 報告](../phases/phase3-trial5/reports/trial5_recovery_first_fit.md) |

## Phase4 殘差 GPR 試驗

共同規則：Trial2--Trial5 對固定 Trial4 D-model 做 20-train/5-test storm-group 評估，基線對數 RMSE 為 0.11005。Trial1 是同資料描述，不能與後四者並列為驗證成績。

| Trial | 狀態 | 特徵／方法 | 結果 | 報告 |
| --- | --- | --- | --- | --- |
| 1 | [historical] | `H_tau_k, H_24h, SME, SYM-H, altitude` 的資料內 GPR | RMSE 0.02029；只代表貼合能力 | [Trial1](../phases/phase4/reports/phase_4_trial4_altitude_gpr_report.md) |
| 2 | [done: negative] | 同五特徵固定 20/5 GPR | RMSE 0.11028，較基線 +0.00023 | [Trial2](../phases/phase4/reports/phase_4_trial4_groupcv20_5_report.md) |
| 3 | [done: negative] | 移除高度的四 geomagnetic 特徵 nested GPR | RMSE 0.12014，較基線 +0.01009 | [Trial3](../phases/phase4/reports/phase_4_trial4_nested_groupcv_report.md) |
| 4 | [done: negative] | `relative_time, tau, season_sin, season_cos` nested GPR | RMSE 0.11323，較基線 +0.00318；`tau` 只可回溯使用 | [Trial4](../phases/phase4/reports/phase_4_time_tau_season_report.md) |
| 5 | [done: negative] | `dSYM-H/dt, ap_step, F10.7` nested GPR | RMSE 0.13203，較基線 +0.02198 | [Trial5](../phases/phase4/reports/phase_4_trial5_driver_report.md) |

Phase4 Final：[not created]。特徵組合比較、各欄位現有證據與不可主張的範圍，見 [Phase4 特徵貢獻整理](../phases/phase4/reports/phase_4_feature_contribution_summary.md)。

## 採用界線

```text
Phase3 historical trials ──> retained only
Phase3 Trial4 D-model ────> current descriptive density baseline
Phase3 Trial5 ────────────> working; not downstream
Phase4 Trial1--Trial5 ────> rejected as Final candidates
Phase4 Final ─────────────> not created
```

Trial4 D-model 是資料內回溯擬合，不是 forecast；所以即使 Phase4 的 held-out 殘差 GPR 通過，也不會自動變成端到端未見 storm 的密度預報。
