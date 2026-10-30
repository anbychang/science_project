# Phase4 Trial6：複合磁暴的日夜與緯度 Ridge 殘差

狀態：[not created]。工作空間與[執行計畫](docs/plans/PLAN.md)已建立；尚未準備特徵、擬合 Ridge 或產生研究結果。Phase 3 Trial4 D-model 保持固定，Phase4 Final 仍是 `[not created]`。

```text
docs/plans/  -> 方法、輸入、檢查點與執行順序
code/        -> 待建立的準備與計算程式
data/sqlite/ -> 待建立的衍生資料庫
data/analysis/、figures/、reports/、docs/lineage/、tests/
             -> 待建立的檢查、圖、報告、血緣與必要測試
```

這個 Trial 只處理磁暴結束後的回溯殘差：保留複合事件、檢查主要再增強時段，測試當地太陽時、日夜與磁緯度是否有額外訊號。不把 `compound`、`n_minima`、SME 或 ap 當成 Ridge 輸入。
