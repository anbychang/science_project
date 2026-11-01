# Trial 索引

狀態：[done]。本頁是所有 Trial 的入口，不把不同資料、不同校準機會或資料內／held-out 分數混成同一場競賽。現行下游密度基線是 `Phase 4 D-model`；Phase 5 的採用條件與各 Trial 決定見[總入口](../phases/phase5/README.md)。

## 狀態定義

- `[historical]`：保留研究過程，不是現行下游基線。
- `[done: descriptive]`：完成資料內描述，不能視為外測或預報。
- `[done: negative]`：完成 held-out 檢查，沒有通過採用條件。
- `[working]`：有初步結果，尚未成為下游輸入或結論。
- `[not created]`：已保留位置或計畫，沒有研究輸出。

## Phase3 試驗

| 位置 | 狀態 | 問題與結果 | 報告 |
| --- | --- | --- | --- |
| `phase3-trial/` | [historical] | M2 倍率、共同／逐圈 `tau` 與交替擬合探索；資料內格點最低值不可升格為物理量 | [倍率](../phases/phase3-trial/reports/m2_r_grid_trial.md)、[共同 tau](../phases/phase3-trial/reports/m2_tau_fixed_r.md)、[交替擬合](../phases/phase3-trial/reports/m2_alternating_trial.md)、[逐圈 tau](../phases/phase3-trial/reports/m2_phase2_orbit_tau_trial.md) |
| `phase3-trial2/` | [done: negative] | 共用有效時間位移 `delta`；100 個 20/5 split 都選 `delta=0`，沒有改善 | [Trial2 報告](../phases/phase3-trial2/reports/phase3_trial2_delay_report.md) |
| `phase3-trial3/` | [historical] | 單場 SME／響應線性診斷；只提供個案圖，不構成跨 storm 模型選擇 | [SME 個案圖](../phases/phase3-trial3/figures/s20250101_sme_l2.png)、[線性診斷圖](../phases/phase3-trial3/figures/s20250101_response_linearity.png) |
| `phase3-trial5/` | [working] | Phase 4 上加入每場 recovery 起始項與共同恢復時間；目前只改善同資料貼合，未獨立驗證 | [Trial5 報告](../phases/phase3-trial5/reports/trial5_recovery_first_fit.md) |

## Phase 4

| 位置 | 狀態 | 問題與結果 | 報告 |
| --- | --- | --- | --- |
| `phase4/` | [done: descriptive] | 每場自由 $R_k,\tau_k$ 與共同正 $G$；D-model RMSE 0.109953，是現行下游基線 | [joint-fit 報告](../phases/phase4/reports/trial4_joint_fit_tau15_report.md)、[資料血緣](../phases/phase4/docs/lineage/trial4_joint_fit_tau15.md) |
| `phase4-trial1/` | [done: descriptive] | 共同 $\tau$ 粗、細格點；4.75 h 的資料內 RMSE 0.113059，仍高於 D-model | [共同 tau 報告](../phases/phase4-trial1/reports/shared_tau_grid_report.md) |

## Phase5 殘差模型試驗

共同規則：Trial2--Trial5 對固定 Trial4 D-model 做 20-train/5-test storm-group 評估，基線對數 RMSE 為 0.11005。Trial1 是同資料描述，不能與後四者並列為驗證成績。

| Trial | 狀態 | 特徵／方法 | 結果 | 報告 |
| --- | --- | --- | --- | --- |
| 1 | [historical] | `H_tau_k, H_24h, SME, SYM-H, altitude` 的資料內 GPR | RMSE 0.02029；只代表貼合能力 | [Trial1](../phases/phase5-trial1/reports/phase_5_trial4_altitude_gpr_report.md) |
| 2 | [done: negative] | 同五特徵固定 20/5 GPR | RMSE 0.11028，較基線 +0.00023 | [Trial2](../phases/phase5-trial2/reports/phase_5_trial4_groupcv20_5_report.md) |
| 3 | [done: negative] | 移除高度的四 geomagnetic 特徵 nested GPR | RMSE 0.12014，較基線 +0.01009 | [Trial3](../phases/phase5-trial3/reports/phase_5_trial4_nested_groupcv_report.md) |
| 4 | [done: negative] | `relative_time, tau, season_sin, season_cos` nested GPR | RMSE 0.11323，較基線 +0.00318；`tau` 只可回溯使用 | [Trial4](../phases/phase5-trial4/reports/phase_5_time_tau_season_report.md) |
| 5 | [done: negative] | `dSYM-H/dt, ap_step, F10.7` nested GPR | RMSE 0.13203，較基線 +0.02198 | [Trial5](../phases/phase5-trial5/reports/phase_5_trial5_driver_report.md) |
| 6 | [done: descriptive] | 同場短缺口內插；$t_0$、強變化區及事前選擇規則 | 定期選段全補 RMSE 0.04737；部分缺口補壞，尚無已驗證選擇器 | [Trial6 報告](../phases/phase5-trial6/reports/trial6_within_storm_ridge_report.md) |
| 7 | [done: descriptive] | 原生一分鐘 L2 與 Trial4 公式的點尺度延伸；只用前 60 分鐘殘差移動平均 | 20/25 場改善；合併 RMSE 0.18056 → 0.15374，仍非獨立預測 | [25 場 Trial7 報告](../phases/phase5-trial7/reports/trial7_25storm_past_mean_report.md) |
| 8 | [done: descriptive] | 同場逐圈 GPR，只用過去 L2 估計下一圈 | 在相同 2,115 圈上，四輸入 GPR 0.04581，直接沿用上一圈 0.04211 | [Trial8 報告](../phases/phase5-trial8/reports/trial8_next_orbit_gpr_report.md) |
| 9 | [historical] | 20 場訓練／5 場整場留出的共用逐圈 GPR；需上一圈 L2 | 在相同 2,115 圈上，GPR 0.03926；逐場 17/25 場勝過直接沿用；不作無 L2 終版 | [Trial9 報告](../phases/phase5-trial9/reports/trial9_pooled_orbit_gpr_report.md) |
| 10 | [done: negative] | M1 大小、前一圈變化與三圈彎曲的 GPR | 2,235 圈對數密度 RMSE 0.20663 → 0.21960；不採用 | [Trial10 報告](../phases/phase5-trial10/reports/trial10_m1_shape_gpr_report.md) |
| 11 | [done: negative] | M1、事件時間與局部斜率的 GPR | 2,235 圈對數密度 RMSE 0.20663 → 0.21922；不採用 | [Trial11 報告](../phases/phase5-trial11/reports/trial11_temporal_shape_gpr_report.md) |
| 12 | [done: negative] | M1 峰值與累積高密度的 GPR | 2,235 圈對數密度 RMSE 0.20663 → 0.21395；不採用 | [Trial12 報告](../phases/phase5-trial12/reports/trial12_peak_context_gpr_report.md) |
| 13 | [done: negative] | 相同 25 場與 2,235 圈統一核對 Trial10--Trial12，無新 GPR 訓練 | 三版對數密度 RMSE 均高於 M1；沒有可採用的無同場 L2 修正 | [Trial13 報告](../phases/phase5-trial13/reports/trial13_m1_gpr_final_audit.md) |

十三個 Trial 的共同解讀見[Phase 5 整合報告](../phases/phase5/reports/phase_5_trial1_13_report.md)。[最終報告](../phases/phase5/reports/phase_5_report.md)記錄整場沒有目標 L2 時不採用已測 GPR 的決定；重算與歷史入口見[Phase 5 README](../phases/phase5/README.md)。這批測試沒有完成端到端無 L2 密度預報驗證。Trial1--Trial5 的特徵與消融見[特徵貢獻整理](../phases/phase5-trial2/reports/phase_5_feature_contribution_summary.md)及[單一特徵 GPR 消融](../phases/phase5-trial2/reports/phase_5_feature_ablation_report.md)。

## 採用界線

```text
Phase3 historical trials ──> retained only
Phase4 D-model ───────────> current descriptive density baseline
Phase3 Trial5 ────────────> working; not downstream
Phase5 Trial1--Trial13 ───> research evidence
Phase5 historical Trial9 -> Phase4 + previous-orbit L2 to pooled GPR
Phase5 final ─────────────> no GPR correction selected without target L2
```

Phase 4 D-model 是資料內回溯擬合，不是 forecast。Phase 5 的無同場 L2 留場測試只檢查 GPR 殘差層；Phase 3 歷史 M1 的每場倍率也曾使用 L2，因此沒有端到端無 L2 密度預報成績。
