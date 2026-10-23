# Phase 1 術語

本表區分現行逐 10 秒相位估計與保留的 10 分鐘舊分支；兩者的衰減率不可當成同一種資料產品。

## 現行資料

**Raw record**：從來源檔寫入的原始觀測；後續計算不得修改。

**State**：一個時刻的軌道狀態，形狀為 `{time, frame, position_m, velocity_m_s}`。

**Chunk**：同一產品流、SP3 frame 與 cadence 下，時間連續的可用 state 序列。`chunk_id` 不是 maneuver 分類。

**Mean element**：從慣性座標的 osculating state 轉換所得的 Brouwer-Lyddane 平均軌道根數；不代表所有週期擾動都已消除。

**Phase orbit**：以連續展開的 `u = omega + M` 每增加 `2*pi` 定義的一個完整軌道，不是固定分鐘數。

**Local decay candidate**：在每個可用 10 秒時刻，回看完整 3 或 5 個 phase orbit，對 mean semi-major axis 求得的局部斜率。它是描述性估計，尚未校準成磁暴造成的阻力衰減。

**Causal feature**：對同一 `time_us` 對齊的 SYM-H、Ap、F10.7 與 F10.7A；來源時間須遵守各自的因果邊界。

**Working audit**：檢查兩張局部斜率表與一張 feature 表的 key、有效性、來源時間及 SQLite 完整性。`pass` 不代表物理結果已校準或資料庫已成正式 release。

## 保留的舊分支

**10-minute orbit bin**：舊流程中，同一 chunk 內的 UTC `[end - 600 s, end)` 平均列；不是現行局部斜率的輸入。

**Backward rate**：舊流程在 10 分鐘列上計算的 3、6、12 小時差分率；不等同於現行 3／5 圈 OLS slope。
