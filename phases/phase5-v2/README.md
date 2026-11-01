# Phase 5 V2：估計 Phase 4 V2 事件 R

狀態：[done: exploratory]。主線是**交叉驗證引導的演化式包裝法特徵選擇 + Ridge 迴歸**，以 A* 風格優先擴展較佳因素組合，估計 Phase 4 V2 `phase4_v2_events.r_fit`。固定因素為 `{r_phase3, prequiet_sme_mean_nt, quiet_f107a_last81_sfu}`；五次 20 場訓練／5 場算分的 $R_k$ RMSE 平均為 0.100904／0.115458。25 場密度圖只畫 L2、Ridge、同場擬合 $\tau_k$ 與 $R_k$ 三條線；Ridge 密度的等事件權重 log RMSE 為 0.179233。算分事件參與挑因素，尚無新事件的獨立外測，模型不作正式下游 $R_k$。

## 現行資料路徑

```text
Phase 4 V2 phase4_v2_events.r_fit -> 25 個 R 目標快照
Phase 3 原本 R + Phase 2／1 天氣 -> 25 場 × 23 因素
  -> 五次 20/5 分數引導搜尋 -> 一組固定因素
  -> Ridge 逐場修正量 + 全 25 場研究模型
```

| 項目 | 路徑 |
| --- | --- |
| Phase 4 V2 目標快照入口 | `code/prep_phase4_v2_r_targets.py` |
| 目標快照 SQLite | `data/sqlite/phase4_v2_r_targets_v2.sqlite` |
| Ridge 主線入口 | `code/prep_storm_r_ridge.py` |
| 主結果 SQLite | `data/sqlite/storm_r_ridge_v21.sqlite` |
| 密度比較 SQLite | `data/sqlite/storm_r_ridge_density_v1.sqlite` |
| 25 場 5×5 三線密度圖 | [查看圖](figures/ridge_density_25_storms_5x5_v3.png) |
| 完整結果與限制 | [Ridge 報告](reports/storm_r_ridge_report.md) |
| 來源、key 與表結構 | [Ridge 資料血緣](docs/lineage/storm_r_ridge.md) |

在乾淨工作目錄依序執行 `python phases/phase5-v2/code/prep_phase4_v2_r_targets.py`、`python phases/phase5-v2/code/prep_storm_r_ridge.py`、`python phases/phase5-v2/code/prep_storm_r_ridge_density.py`、`python phases/phase5-v2/code/prep_storm_r_ridge_density_figure.py`。既有輸出拒絕覆寫；來源庫唯讀。

## 歷史探索

先前的 GPR、單因素線性、分組驗證與第十四至十九輪特徵搜尋都保留為[歷史試驗紀錄](reports/storm_r_gpr_report.md)。它們的程式和 SQLite 不作現行 Ridge 主線輸入。
