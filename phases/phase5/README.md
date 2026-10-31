# Phase 5：採用版與實驗紀錄

狀態：[done: method selected]。Phase 5 採用固定 Phase 4 D-model 加跨場逐圈 GPR 的殘差修正流程；這是有上一圈 L2 時的描述性回溯修正，尚非端到端預報。Phase 5 採用與其他 Phase 相同的六個資料夾：`code/`、`data/`、`docs/`、`figures/`、`reports/`、`tests/`。共用計算程式也在本目錄的 `code/`；各 Trial 的詳細紀錄留在原 Trial 目錄。

本階段原名 Phase 4，現已整套改名為 Phase 5。既有 SQLite 表名、分析資料檔名與模型 `algorithm_version` 中的 `phase4` 保留為原實驗識別碼；它們不是另一套仍需執行的 Phase 4。搬遷不改動既有數據與模型內容。

先讀[Phase 5 採用版報告](reports/phase_5_report.md)，看最後選用的輸入、公式、結果與限制。[Trial1--Trial9 實驗報告](reports/phase_5_trial1_9_report.md)保留研究過程、負結果與各圖。後續從 Phase 4 直接重算跨場 GPR，使用本目錄的單一入口，不必按順序重跑九個 Trial。

## Trial 計畫與目前進度

| Trial | 要回答的問題 | 已完成的檢查 | 結果入口 |
| --- | --- | --- | --- |
| 1 | GPR 能否描述已見的 Trial4 密度殘差？ | 25 場 2,295 一圈錨點同資料擬合與評分 | [Trial1](../phase5-trial1/reports/phase_5_trial4_altitude_gpr_report.md) |
| 2 | 同一組 GPR 特徵能否轉移到別場磁暴？ | 五折 20 場訓練／5 場完整磁暴留出 | [Trial2](../phase5-trial2/reports/phase_5_trial4_groupcv20_5_report.md) |
| 3 | 移除高度後能否避免局部化而改善跨場結果？ | 四特徵 nested 20/5 留出 | [Trial3](../phase5-trial3/reports/phase_5_trial4_nested_groupcv_report.md) |
| 4 | 時間、已擬合 tau 與季節是否提供額外殘差訊號？ | nested 20/5 留出 | [Trial4](../phase5-trial4/reports/phase_5_time_tau_season_report.md) |
| 5 | `dSYM-H/dt`、`ap_step`、`F10.7` 能否修正剩餘殘差？ | 新 driver nested 20/5 留出 | [Trial5](../phase5-trial5/reports/phase_5_trial5_driver_report.md) |
| 6 | 有前後 L2 時能否修同場六小時缺口？ | 275 個定期缺口、$t_0$ 與 SYM-H 壓力區、兩條事前規則 | [Trial6](../phase5-trial6/reports/trial6_within_storm_ridge_report.md) |
| 7 | 有持續觀測時能否只用過去 L2 逐分鐘更新？ | 25 場逐分鐘修正；一圈平均密度與逐分鐘密度分開評分 | [Trial7](../phase5-trial7/reports/trial7_25storm_past_mean_report.md) |
| 8 | 用這一圈誤差推下一圈時，GPR 能否勝過直接沿用？ | 25 場 2,115 個可評分圈；單輸入與四輸入 GPR 整體都輸給上一圈誤差 | [Trial8](../phase5-trial8/reports/trial8_next_orbit_gpr_report.md) |
| 9 | 其他 20 場磁暴能否教 GPR 修正留下的 5 場下一圈？ | 沿用五折 20/5；整場 17/25 場勝過直接沿用，磁暴中心附近 13/25 場 | [Trial9](../phase5-trial9/reports/trial9_pooled_orbit_gpr_report.md) |

Trial1 是資料內貼合；Trial2--Trial5 是固定 Trial4 之上的跨場殘差測試；Trial6--Trial8 各有不同的同場資料條件；Trial9 留出整場磁暴，但使用測試場上一圈已知的 L2。總報告分開評分，沒有把它們當成同一種預測競賽。檔名中的 `trial4` 常指 **Phase 4 基線**，不一定是 Phase 5 Trial4。

## 現行重算入口

Phase 5 只有一條現行流程：讀取 Phase 4 已保存的相位與密度，取 25 場的 2,295 個逐圈點，組成 2,265 組相鄰圈，做五折 20 場訓練／5 場整場測試，最後存下五個測試模型與一個 25 場共同模型。Trial1--Trial9 是找到這個方法的研究紀錄，不是重算時的九道工序。

固定輸入只來自 Phase 4，程式以唯讀方式開啟：

| Phase 4 檔案 | 使用的資料 |
| --- | --- |
| `../phase4/data/sqlite/swarm_a_phase3_h_tau_phase_v1.sqlite` | `phase3_h_tau_minute` 的時間、相位與有效標記，決定每圈取哪一點 |
| `../phase4/data/sqlite/swarm_a_trial4_joint_fit_tau15.sqlite` | `trial4_joint_fit_minute` 的 D-model、L2 與殘差；`trial4_25storm_overview` 的事件時間 |

資料從 Phase 4 進入 Phase 5 後，Phase 4 的 $R_k$、$\tau_k$ 與 $G$ 都不重估。Phase 5 只學下一圈的殘差變化；正式資料寫入 `data/sqlite/swarm_a_phase5_pooled_orbit_gpr_v1.sqlite`，模型檔留在 `data/models/`。

在專案根目錄執行：

```powershell
python phases/phase5/code/prep_phase5_direct_gpr.py
```

SQLite 內有 `phase5_orbit_anchor`（2,295 點）、`phase5_orbit_prediction`（2,265 筆留場預測）、`phase5_event_metric`（25 場分數）、`phase5_fold` 與 `phase5_fold_storm`（五折分組）、`phase5_summary_metric`（合計分數）及 `phase5_metadata`。這些表可以用 SQL 依 `storm_id,time_us` 查詢，不必讀 CSV。`code/prep_phase5_direct_gpr.py` 也提供 `load_final_model()` 與 `predict_next_orbit()`，可直接使用 `data/models/all_25.joblib`，不必重訓。程式拒絕覆寫既有結果。原本的 CSV 與 JSON 已移到 `data/retained_csv_v1/`，只作舊結果核對，不再是現行資料來源。

例如要看某一場磁暴的逐圈 L2、Phase 4 基線與 GPR 修正值，輸入是 `phase5_orbit_prediction`，查詢結果依分鐘鍵排序：

```sql
SELECT time_us, rho_l2_phase_kg_m3, rho_trial4_phase_kg_m3,
       rho_pooled_gpr_kg_m3
FROM phase5_orbit_prediction
WHERE storm_id = 'S20230805T0546'
ORDER BY time_us;
```

資料欄位、來源 key 與版本見[現行 GPR 資料血緣](docs/lineage/phase5_pooled_orbit_gpr.md)。

要重畫 25 場的 **5×5 三線總覽圖**，輸入是 Phase 4 的事件時刻和 Phase 5 已保存的逐圈留場預測，輸出是一張 PNG；這一步不重訓模型：

```powershell
python phases/phase5/code/prep_phase5_density_overview.py
```

[25 場總覽圖](figures/phase5_density_25storm_overview.png)與[圖的讀法](reports/phase_5_report.md#25-場密度折線總覽)都在 Phase 5。

## GPR 真正輸入什麼

設 $D_n$ 是 Phase 4 算出的這一圈密度，$L_{n-1}$ 是上一圈已收到的 L2 密度。GPR 接收四個數字：

| 輸入 | 意思 | 取得方式 |
| --- | --- | --- |
| $\ln D_n$ | 這一圈的 Phase 4 密度 | 固定的 Phase 4 輸出 |
| $\ln D_{n-1}$ | 上一圈的 Phase 4 密度 | 固定的 Phase 4 輸出 |
| $\ln L_{n-1}$ | 上一圈的實際 L2 密度 | 已完成的觀測 |
| $e_{n-1}=\ln(L_{n-1}/D_{n-1})$ | 上一圈相對 Phase 4 的誤差 | 由前兩個上一圈密度算出 |

第四個數字由第二、三個算出，不是額外的獨立觀測。時間與相位只用來確認兩個點是同場磁暴的相鄰圈，不直接送入 GPR。訓練時，用歷史資料的這一圈 L2 算出目標 $e_n-e_{n-1}$；真正修這一圈時，**不輸入這一圈的 L2**。GPR 估出誤差變化後，將修正值乘回 $D_n$。它沒有新增物理公式；整體方法仍以 Phase 4 D-model 為基線。Phase 4 的事件參數曾用完整 L2 擬合，因此本結果不是端到端獨立預報。

[共用計算程式](code/)與[歷史完整計畫](docs/plans/PLAN.md)已放進 Phase 5；它們支持 Trial1--Trial5 重算。Trial10 尚無實驗結果。
