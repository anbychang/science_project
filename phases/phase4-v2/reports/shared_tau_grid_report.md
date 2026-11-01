# Phase 4 v2：共同 tau 密度基線

狀態：[done: descriptive]。固定 Phase 4 v1 的 25 場事件、對數密度目標與等事件權重損失。每個共同 $\tau$ 候選都重新擬合 25 個 $R_k$ 與一個正的 $G$；v2 以細掃最佳 4.75 h 重新建成 214,907 筆逐分鐘密度。v1 的自由 $\tau_k$ D-model 保留原檔。

| 模型 | $\tau$ 設定 | 等事件權重對數 RMSE |
| --- | --- | ---: |
| Phase 4 B | 共同 4.65 h | 0.113074 |
| v2 粗掃最佳 | 共同 4.8 h | 0.113062 |
| v2 現行值 | 共同 4.75 h | 0.113059 |
| Phase 4 D-model | 每場自由 $\tau_k$ | 0.109953 |

先在 0–15 h、每 0.1 h 的 151 個候選中選出 4.8 h；再於 4.6–4.9 h 每 0.01 h 細掃 31 個候選，選出 4.75 h。細掃最佳 $G=0.000689829\ \mathrm{nT}^{-1}$，RMSE 為 0.113058770。4.74 h 與 4.76 h 分別為 0.113058992、0.113058837，差距極小。4.7 h 與 4.8 h 的細掃結果和粗掃逐位一致。相對固定 4.65 h 的 Phase 4 B，改善約 0.000015；每場自由 $\tau_k$ 的 D-model 仍低約 0.003106。

決定：v2 是現行共同 $\tau$ 的描述性基線。它比自由 $\tau_k$ 的 v1 簡單，但資料內誤差較大；這個格點沒有顯示精確的物理記憶時間，也沒有未見事件的外測證據。Phase 5、Phase 6 舊結果仍依 v1 計算，不能直接改標為 v2。

重算入口：[粗掃](../code/prep_shared_tau_grid.py)、[細掃](../code/prep_shared_tau_fine.py)、[逐分鐘 v2](../code/prep_phase4_v2_density.py)。本機三庫依序為 `shared_tau_grid_v1.sqlite`、`shared_tau_fine_v1.sqlite`、`swarm_a_phase4_v2_shared_tau.sqlite`。粗、細格點分別 151、31 筆；v2 有 25 場、214,907 筆分鐘列，事件等權對數 RMSE 0.113058769603，與細掃逐位一致，`PRAGMA integrity_check=ok`。各衍生表有 `algorithm_version`；SQLite 依專案規則不提交 Git。
