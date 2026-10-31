# Phase 5：無同場 L2 的 GPR 終版判定與實驗紀錄

狀態：[done: negative]。Phase 5 終版以「目標磁暴整場沒有可用 L2」為條件。Trial10--Trial13 的留場核對未找到可採用的 GPR 修正；**目前沒有部署用的無 L2 密度終版**。Phase 4 D-model 是已保存的描述性基線，但事件參數曾用同場 L2 擬合，不能直接移用到這個目標條件。各 Trial 的原始數據、程式與圖保留供核對。

本階段原名 Phase 4，現已整套改名為 Phase 5。既有 SQLite 表名、分析資料檔名與模型 `algorithm_version` 中的 `phase4` 保留為原實驗識別碼；它們不是另一套仍需執行的 Phase 4。搬遷不改動既有數據與模型內容。

先讀[Phase 5 最終報告](reports/phase_5_report.md)，看無同場 L2 時的證據、決定與限制。[Trial1--Trial13 整合報告](reports/phase_5_trial1_13_report.md)按實驗順序解釋每一步並附圖。Trial9 用上一圈 L2 得到的正向結果保留為**不同資料條件的歷史實驗**，不是本終版的修正入口。

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
| 10 | 只用 Phase 3 M1 的大小、前一圈變化與三圈彎曲，能否跨場修正殘差？ | 對數密度 RMSE 0.20663 升至 0.21960，2/5 折改善；不採用 | [Trial10](../phase5-trial10/reports/trial10_m1_shape_gpr_report.md) |
| 11 | 加入磁暴時間並讓 GPR 只學場內誤差升降，能否修正跨場趨勢？ | 對數密度 RMSE 0.20663 升至 0.21922，0/5 折改善；不採用 | [Trial11](../phase5-trial11/reports/trial11_temporal_shape_gpr_report.md) |
| 12 | 改用整場 M1 峰值、距峰時間與累積高密度，能否修正跨場趨勢？ | 對數密度 RMSE 0.20663 升至 0.21395，1/5 折改善；不採用 | [Trial12](../phase5-trial12/reports/trial12_peak_context_gpr_report.md) |
| 13 | 同圈、同指標比較 Trial10–Trial12，無同場 L2 的 M1-GPR 是否有可靠改善？ | 2,235 圈、25 場；三版密度 RMSE 都高於 M1；同圈 D-model 為 0.11000，但已用同場 L2 擬合 | [Trial13](../phase5-trial13/reports/trial13_m1_gpr_final_audit.md) |

Trial1 是資料內貼合；Trial2--Trial5 是固定 Phase 4 之上的跨場殘差測試；Trial6--Trial8 各有不同的同場資料條件；Trial9 留出整場磁暴，但使用測試場上一圈 L2。Trial10--Trial12 在 GPR 推論時不讀測試場 L2；Trial13 統一核對相同 2,235 圈。這些分數的基線與資料條件不同，不能直接排名。檔名中的 `trial4` 常指 **Phase 4 基線**，不一定是 Phase 5 Trial4。

## 終版使用規則

| 目標場可用資料 | Phase 5 決定 |
| --- | --- |
| 整場沒有 Swarm-A L2 | 不套用 Trial9；不採用 Trial10--Trial12 的 GPR 修正。現有 Phase 3 M1 和 Phase 4 D-model 的事件參數都曾使用同場 L2，不能直接改名為無 L2 基線。 |
| 已有上一圈 Swarm-A L2 | Trial9 曾在這個條件下得到 0.03926 的留場對數 RMSE，低於直接沿用上一圈的 0.04211；它是歷史的條件性方法，不是本終版。 |

相同 25 場、2,235 圈的**對數密度 RMSE**：Phase 4 D-model **0.11000**（同場 L2 擬合參考）、M1 **0.20663**、Trial10--Trial12 GPR 分別 **0.21960、0.21922、0.21395**。三版都沒有改善 M1，也沒有測到 D-model 殘差修正。[最終報告](reports/phase_5_report.md)列出五折的訓練與測試分數及 D-model 的同圈比較；[Trial13 技術報告](../phase5-trial13/reports/trial13_m1_gpr_final_audit.md)核對三版留場預測。D-model 同圈核對的本機 SQLite 是 `data/sqlite/swarm_a_phase5_d_model_same_orbits_v1.sqlite`，由 `python phases/phase5/code/prep_phase5_d_model_score.py` 唯讀來源後建立。

## 歷史 Trial9 輸出

本目錄 `code/prep_phase5_direct_gpr.py`、`code/prep_phase5_density_overview.py`、`data/sqlite/swarm_a_phase5_pooled_orbit_gpr_v1.sqlite`、`data/models/` 與 `figures/phase5_density_25storm_overview.png` 重現的是**有上一圈 L2**的 Trial9 延伸版。原檔保留供查核，不作無 L2 終版的推論入口。[歷史資料血緣](docs/lineage/phase5_pooled_orbit_gpr.md)記錄來源、欄位與相位錨點。早期 CSV/JSON 留在 `data/retained_csv_v1/`，只作歷史對照。

`code/` 也保留 Trial1--Trial5 的共用計算程式；[原 Trial1--Trial7 計畫](docs/plans/PLAN.md)是歷史方法紀錄。這些檔案與 Trial9 模型都不因終版判定而刪除；它們的數字不能被改稱為整場無 L2 的修正效果。
