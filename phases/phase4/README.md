# Phase 4：Trial1--Trial7 計畫與總報告

狀態：[done: descriptive]。本目錄只放 Phase 4 的閱讀入口與整合報告；實驗程式、資料、測試和逐場圖留在各 Trial 目錄。Phase 3 Trial4 D-model 是固定密度基線。Phase4 Final 為 `[not created]`：七個 Trial 都不能被改稱為已驗證的通用密度修正。

先讀[Phase 4 實驗總報告](reports/phase_4_report.md)。報告依 Trial1--Trial7 的研究順序，說明問題、方法、結果、負結果的價值和可主張的界線；圖各自說明一件事。較細的逐場數值、舊圖與重算入口在各 Trial 目錄。

## Trial 計畫與目前進度

| Trial | 要回答的問題 | 已完成的檢查 | 結果入口 |
| --- | --- | --- | --- |
| 1 | GPR 能否描述已見的 Trial4 密度殘差？ | 25 場 2,295 一圈錨點同資料擬合與評分 | [Trial1](../phase4-trial1/reports/phase_4_trial4_altitude_gpr_report.md) |
| 2 | 同一組 GPR 特徵能否轉移到別場磁暴？ | 五折 20 場訓練／5 場完整磁暴留出 | [Trial2](../phase4-trial2/reports/phase_4_trial4_groupcv20_5_report.md) |
| 3 | 移除高度後能否避免局部化而改善跨場結果？ | 四特徵 nested 20/5 留出 | [Trial3](../phase4-trial3/reports/phase_4_trial4_nested_groupcv_report.md) |
| 4 | 時間、已擬合 tau 與季節是否提供額外殘差訊號？ | nested 20/5 留出 | [Trial4](../phase4-trial4/reports/phase_4_time_tau_season_report.md) |
| 5 | `dSYM-H/dt`、`ap_step`、`F10.7` 能否修正剩餘殘差？ | 新 driver nested 20/5 留出 | [Trial5](../phase4-trial5/reports/phase_4_trial5_driver_report.md) |
| 6 | 有前後 L2 時能否修同場六小時缺口？ | 275 個定期缺口、$t_0$ 與 SYM-H 壓力區、兩條事前規則 | [Trial6](../phase4-trial6/reports/trial6_within_storm_ridge_report.md) |
| 7 | 有持續觀測時能否只用過去 L2 逐分鐘更新？ | 25 場一分鐘、前 60 分鐘移動平均與失敗場分析 | [Trial7](../phase4-trial7/reports/trial7_25storm_past_mean_report.md) |

Trial1 是資料內貼合；Trial2--Trial5 是固定 Trial4 之上的跨場殘差測試；Trial6 和 Trial7 各有不同的同場資料條件。總報告分開評分，沒有把它們當成同一種預測競賽。檔名中的 `trial4` 常指 **Phase 3 Trial4 基線**，不一定是 Phase 4 Trial4。

既有的[共用計算程式](../phase4_shared/code/)與[歷史完整計畫](../phase4_shared/docs/plans/PLAN.md)保留在本目錄之外；它們支持 Trial1--Trial5 重算，不是 Phase 4 總報告的實驗輸出。Trial8--Trial10 沒有既有研究檔案或定義，本次不建立空 Trial 或虛構結果。
