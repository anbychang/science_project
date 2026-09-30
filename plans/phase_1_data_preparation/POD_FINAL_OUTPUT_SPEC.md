# P1.5 POD 軌道輸出規格

## 狀態

這是 P1.5 的 10 分鐘軌道中間產物規格，不是 P1.7 的完整分析資料集。現在已完成
原始 POD、瞬時半長軸與基本品質標記；orbit-average、short-period treatment、平滑半長軸與衰減率尚未
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

## 執行位置

這份文件只定義 P1.5 的表格介面與 release checks。P1.5-A 至 P1.5-D 的執行順序、
synthetic tests、method decision 與停止條件只維護在
`P1.4_TO_P1.7_EXECUTION_PLAN.md`，避免兩份文件日後分歧。
