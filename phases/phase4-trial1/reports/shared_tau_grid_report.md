# Phase 4 Trial1：共同 tau 格點比較

狀態：[done: descriptive]。固定 Phase 4 的 25 場事件、對數密度目標與等事件權重損失。每個共同 $\tau$ 候選都重新擬合 25 個 $R_k$ 與一個正的 $G$；不沿用 D-model 的已擬合參數。

| 模型 | $\tau$ 設定 | 等事件權重對數 RMSE |
| --- | --- | ---: |
| Phase 4 B | 共同 4.65 h | 0.113074 |
| 本 Trial 粗掃最佳 | 共同 4.8 h | 0.113062 |
| 本 Trial 細掃最佳 | 共同 4.75 h | 0.113059 |
| Phase 4 D-model | 每場自由 $\tau_k$ | 0.109953 |

先在 0–15 h、每 0.1 h 的 151 個候選中選出 4.8 h；再於 4.6–4.9 h 每 0.01 h 細掃 31 個候選，選出 4.75 h。細掃最佳 $G=0.000689829\ \mathrm{nT}^{-1}$，RMSE 為 0.113058770。4.74 h 與 4.76 h 分別為 0.113058992、0.113058837，差距極小。4.7 h 與 4.8 h 的細掃結果和粗掃逐位一致。相對固定 4.65 h 的 Phase 4 B，改善約 0.000015；每場自由 $\tau_k$ 的 D-model 仍低約 0.003106。

決定：共同 $\tau$ 可作較簡單的描述性對照；這個格點沒有顯示精確的物理記憶時間，也沒有未見事件的外測證據。Phase 4 D-model 的保存輸出不因本試驗改寫。

重算入口：[粗掃](../code/prep_shared_tau_grid.py)、[細掃](../code/prep_shared_tau_fine.py)。結果保存在本機 `data/sqlite/shared_tau_grid_v1.sqlite` 的 `shared_tau_grid` 表與 `data/sqlite/shared_tau_fine_v1.sqlite` 的 `shared_tau_fine` 表；分別為 151、31 筆，兩庫 `PRAGMA integrity_check=ok`，各筆均有 `algorithm_version`。來源為 Phase 4 的唯讀 Phase 2/3 快照；SQLite 依專案規則不提交 Git。
