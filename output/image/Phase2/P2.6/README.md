# Phase 2.6 磁暴峰值比較

此資料夾有 21 張磁暴比較圖，每張以該場 SYM-H 最低點 `t0` 的 UTC 日期與時間命名。三個峰值時刻、相對 `t0` 的時間與順序結果以 `data/sqlite/2023/swarm_a_phase2_sme_p2_6_peak_order_v1.sqlite` 的 `storm_peak_order_v1` 為準；不另存圖表索引 CSV。

- 上圖：每個固定相位圈的 SME 平均；藍點是 `t0` 前後 24 小時內的最大值。
- 中圖：同圈配對密度比 `ln(L2/MSIS)`；綠點是同一時間範圍內的最大值，**不是原始 L2 密度的最大值**。
- 下圖：1 分鐘 SYM-H；紅點是該場事件的最低點 `t0`。

橫軸為相對 `t0` 的小時數，虛線 `0 h` 是 SYM-H 最低點。這是 P2.6 的描述性時序檢查，不是物理延遲的測量值。來源為 P2.4 密度 SQLite、P2.5 地磁摘要 SQLite 與 P2.6 峰值 SQLite；產生程式是 `output/report/prep_phase2_peak_figures.py`。
