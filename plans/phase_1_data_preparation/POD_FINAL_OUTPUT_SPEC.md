# P1.5 POD 軌道輸出規格

## 狀態

這是 P1.5 的 10 分鐘軌道中間產物規格，不是 P1.7 的完整分析資料集。現在已完成
原始 POD、瞬時半長軸與基本品質標記；orbit-average、B-spline 平滑半長軸與衰減率尚未
發布，原因記在 `P1.5_RESAMPLE_AND_DECAY.md`。P1.6 feature join 與 P1.7 最終欄位
見 `P1.4_TO_P1.7_EXECUTION_PLAN.md`。

## 發佈時的資料說明

- Swarm-A POD 原始資料的 10 分鐘衍生結果。
- 包含 orbit-average、平滑半長軸、衰減率與 POD provenance。
- 10 分鐘資料列只能由同一個 continuous usable interval 的原始 POD 產生。

## 每一列的欄位

SQLite 內部以 `time_us` 儲存 UTC Unix microseconds；對外 CSV 或 Parquet export
另外提供 ISO 8601 的 `timestamp`。

| 欄位 | 單位 | 意義 | 目前狀態 |
| --- | --- | --- | --- |
| `time_us` | UTC Unix microseconds | 10 分鐘 bin 的 SQLite key | P1.5 待建立 |
| `timestamp` | ISO 8601 UTC | 對外 export 的時間 | P1.7 export 時建立 |
| `semi_major_axis_orbit_mean_m` | m | orbit-average 後的半長軸 | P1.5 待建立 |
| `semi_major_axis_smooth_m` | m | 移除短週期項後的半長軸 | P1.5 待建立 |
| `da_dt_smooth_m_s` | m/s | 平滑半長軸的一階導數 | P1.5 待建立 |
| `decay_rate_smooth_m_day` | m/day | `-da_dt_smooth_m_s * 86400`，正值代表下降 | P1.5 待建立 |
| `pod_count` | count | 參與輸出的 POD observation 數 | P1.5 待建立 |
| `max_pod_gap_s` | s | 該 bin/window 最大相鄰 POD 時差 | P1.5 待建立 |
| `interval_id` | integer | 所屬連續可用區間 | P1.5 待建立 |

## 不屬於這張表的欄位

原始 `x_m`、`velocity_m_s`、瞬時 `semi_major_axis_m` 與 `is_usable` 分別留在
`swarm_a_states`、`swarm_a_orbital_elements`、`swarm_a_pod_quality`。不要在 P1.5
重複複製它們。若後續研究需要高度，`semi_major_axis_smooth_m - 6,371,000 m` 只能命名為
`mean_orbit_height_m`，不能冒充瞬時或 geodetic `altitude_m`。

## 實際資料量與行數限制

目前 POD 範圍是 2021-12-31 23:59:42 UTC 至 2026-08-12 23:59:32 UTC，
有 14,558,400 筆、10 秒分辨率的原始資料。這不是原先估計的 12 年、30 秒、
約 30,000,000 筆。

P1.4 規定每個 source-file boundary 都要切開 interval。每個 interval 有 143 個完整的
10 分鐘 bin，所以目前最多只能產生：

```text
1,685 intervals * 143 complete bins = 240,955 rows
```

因此以下原始目標與目前資料範圍衝突，不能列為 release pass condition：

| 原始估計 | 為何目前不可能 |
| --- | --- |
| 10 分鐘後約 630,000 行 | 現有資料只有約 4.6 年。 |
| `valid = True` 超過 300,000 行 | 即使所有完整 bin 都可用，最多也只有 240,955 行。 |
| 品控後約 315,000 行 | 同樣超過目前的理論上限。 |

若要達到 300,000 個完整 10 分鐘 bin，且維持目前的 source boundary 規則，至少需要約
2,098 個完整 daily POD interval；也就是比目前多約 413 天資料。

## 最終檢驗條件

以下是目標檢驗條件；標示為待確認者不可在目前當成 pass/fail。

| 檢驗 | 狀態 |
| --- | --- |
| 輸出列沒有 `NaN` 或無窮大 | P1.5 實作時必須檢查 |
| 每列 `is_usable = true`，且有 `interval_id` | 已具備輸入條件 |
| 每個輸出 bin 有 60 筆 POD，最大間隔 10 秒 | 已具備輸入條件 |
| `decay_rate_smooth_m_day` 平均為 0.3 至 1.5 m/day | 待確認；先完成短週期項處理方法 |
| 高度約 400 至 415 km | 待確認欄位定義；不可直接以未平滑 `a` 檢查 |
| `valid = true` 超過 300,000 行 | 待資料範圍擴充或改成目前範圍的比例門檻 |

## 從目前資料到最終表的執行計畫

### 原則

原始資料與已完成的衍生表都不修改：

```text
swarm_a_states                 原始 POD
swarm_a_orbital_elements       瞬時半長軸
swarm_a_pod_quality            品質標記與 interval
```

P1.5 只讀取這三張表，並寫入新的 10 分鐘衍生表。任何步驟失敗都不能回頭
覆寫原始 POD。

### Step A：確認一個軌道週期的時間尺度

目的：決定要平均多長時間，才可以移除 osculating 半長軸的短週期震盪。

1. 從每個 interval 的 `semi_major_axis_m` 計算 Kepler orbit period。
2. 報告所有 interval 的 median、最小與最大 orbit period。
3. 固定使用這個 median 當作 orbit-average window，並把數值寫入 metadata。

這一步不產生最終資料，只決定後面平均視窗的實際長度。不能硬寫「90 分鐘」；
必須由現有 Swarm-A 半長軸算出來。

完成條件：orbit period 的單位是秒，方法與選出的 window 都記錄在 metadata。

### Step B：建立 orbit-averaged semi-major axis

目的：先把每個軌道一圈內的快速上下震盪平均掉。

1. 對每個 UTC 10 分鐘輸出時間點，取前後各半個 orbit period 的 centered window。
2. window 內只接受同一個 `interval_id`、`is_usable = 1` 的 POD。
3. window 必須沒有超過 10 秒的 source-time gap，且 observation 數量足夠；不完整 window
   不產生輸出列。
4. 對 window 內的 `semi_major_axis_m` 取平均，得到
   `semi_major_axis_orbit_mean_m`。
5. 保存 `pod_count`、`max_pod_gap_s`、window 起訖原始 `time_us` 與 `interval_id`。

這個值是「以一圈軌道為尺度的平均半長軸」，不是瞬時半長軸。它仍可每 10 分鐘
輸出，但相鄰輸出視窗會重疊；這是為了保留平滑時間序列，不代表多做了新的量測。

完成條件：不跨 interval、不跨 gap；一個人工 gap 的測試資料在 gap 附近沒有輸出列。

### Step C：對 orbit mean 做 B-spline

目的：從已去除主要短週期項的序列，得到連續且可微分的長期趨勢。

1. 每個 interval 獨立 fit B-spline；絕不跨 `interval_id`。
2. 輸入是 Step B 的 `semi_major_axis_orbit_mean_m`，不是原始瞬時半長軸。
3. 先在 synthetic data 測試三個情境：固定半長軸、線性下降、線性下降加一圈週期震盪。
4. 使用時間上連續的 held-out block 比較候選 smoothing strength；不可隨機抽點，避免
   洩漏相鄰時間資訊。
5. 選出參數後，記錄 spline degree、smoothing strength、選擇方法與程式版本。

完成條件：synthetic linear decay 的 slope 誤差在預先設定的容許值內；加入週期震盪後，
recover 的 slope 仍接近真值。

### Step D：計算衰減率並建立 10 分鐘表

目的：把平滑曲線轉成最後可分析的數值。

1. 在每個有效 UTC 10 分鐘點 evaluate spline，得到 `semi_major_axis_smooth_m`。
2. 取 spline 一階導數，得到 `da_dt_smooth_m_s`。
3. 計算 `decay_rate_smooth_m_day = -da_dt_smooth_m_s * 86400`；正值代表軌道下降。
4. 寫入新的 derived SQLite table，保留每列的原始 window 時間範圍與 `interval_id`。

完成條件：沒有 `NaN`、無窮大、跨 interval 的列，且每列都有 POD provenance。

### Step E：真實資料驗證與發布

目的：確認結果既平滑又沒有失去研究需要的變化。

1. 報告 raw、orbit mean、B-spline 三個階段的 row count 與值域。
2. 報告每個 rejection reason、缺少 window 的原因與 interval coverage。
3. 比較 raw 與 smooth 的 10 分鐘導數分布；確認不再出現數十萬 m/day 的假衰減率。
4. 檢查平滑高度是否落在合理的 Swarm-A 軌道範圍；此檢查使用
   `mean_orbit_height_m`，不是未平滑瞬時半長軸。
5. 通過後才建立 CSV 或 Parquet export；SQLite 仍是可重建的工作資料庫。

## 完成順序與停止點

| 關卡 | 可產生的東西 | 可以繼續的條件 |
| --- | --- | --- |
| A | orbit period 報告 | window 有明確秒數 |
| B | 10 分鐘 orbit mean | gap 與 interval 測試通過 |
| C | 已校準的 B-spline 設定 | synthetic slope 測試通過 |
| D | 最終 10 分鐘 POD SQLite table | 沒有非有限值與跨界資料 |
| E | 發布資料與完整報告 | 真實資料統計合理 |

目前停在 A 之前。下一個實作小步是只計算並記錄 Swarm-A 的 orbit period；
它不會產生衰減率，也不會更動任何既有資料。
