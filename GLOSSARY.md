# 研究術語

本頁區分各 Phase 的資料產品。Phase 1 的逐 10 秒候選與舊 10 分鐘分支不是同一種衰減率；Phase 2／2R／3 的結案結果也不是已校準的軌道衰減率。

## 原始資料與 Phase 1

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

## Phase 2／2R 磁暴資料

**t0**：每場事件選定的 SYM-H 最低點時間；不是磁暴開始時刻。

**Peak QC**：在指定事件窗口內，比較平滑後的 SME 與密度殘差峰值時間。它是描述性檢查；兩個峰可能來自不同 pulse，不等於因果延遲。

## Phase 3 密度響應

**$R_k$**：第 $k$ 場事件依低活動段規則算出的 L2／平靜 MSIS 密度倍率。這是 Phase 3 已定稿的操作倍率，不等於事件真正的物理平靜倍率。

**$H_\tau$**：以 `SME - 65 nT` 為輸入的一階記憶濾波；單位為 nT，不是實測熱通量。

**M0／M1**：M0 是使用實際 `ap` 歷史的完整 MSIS；M1 是以平靜 MSIS、$R_k$ 與 $H_\tau$ 建立的離線響應曲線。兩者校準機會不同，現有誤差不能作公平勝負判定。

## Phase 4 計畫

**GPR 殘差修正**：計畫在 M1 物理基線上學習對數密度殘差；尚無 Phase 4 模型結果。
