# P1.5 POD 軌道輸出規格

NOTE: 本頁只保留舊版 10 分鐘 P1.5／P1.7 產物的欄位規格，不是現行
P1.5.6 v2 的輸出。現行 10 秒局部斜率見
[orbit_analysis.md](../lineage/orbit_analysis.md)。

## 狀態

這是當時完成的 P1.5 10 分鐘軌道產物規格；舊 P1.7 table 另外是
`swarm_a_analysis_10min`。每個 row 同時保存 3、6、12 小時 backward difference；
為使三組 rate 同時存在，每個連續 run 的前 72 列排除。

## 發佈時的資料說明

- Swarm-A POD 原始資料的 10 分鐘衍生結果。
- 包含 orbit-average、3/6/12 小時 backward decay rates 與 POD provenance。
- 10 分鐘資料列只能由同一個 continuous usable chunk 的原始 POD 產生。

## 每一列的欄位

SQLite 內部以 `time_us` 儲存 UTC Unix microseconds；對外 CSV 或 Parquet export
另外提供 ISO 8601 的 `timestamp`。

| 欄位 | 單位 | 意義 | 目前狀態 |
| --- | --- | --- | --- |
| `time_us` | UTC Unix microseconds | 10 分鐘 bin 的 SQLite key | 已建立 |
| `timestamp` | ISO 8601 UTC | optional CSV / Parquet export 的時間 | SQLite working database 不儲存 |
| `semi_major_axis_orbit_mean_m` | m | orbit-average 後的半長軸 | `swarm_a_orbit_10min` 已建立 |
| `semi_major_axis_orbit_mean_m` | m | `time_us` 的 10 分鐘 mean semi-major axis | `swarm_a_analysis_10min` 已建立 |
| `da_dt_3h_backward_m_s` | m/s | `(a(t) - a(t - 3 h)) / 3 h` | 新 release |
| `da_dt_3h_backward_m_day` | m/day | `da_dt_3h_backward_m_s * 86400` | 新 release |
| `da_dt_6h_backward_m_s` | m/s | `(a(t) - a(t - 6 h)) / 6 h` | 新 release |
| `da_dt_6h_backward_m_day` | m/day | `da_dt_6h_backward_m_s * 86400` | 新 release |
| `da_dt_12h_backward_m_s` | m/s | `(a(t) - a(t - 12 h)) / 12 h` | 新 release |
| `da_dt_12h_backward_m_day` | m/day | `da_dt_12h_backward_m_s * 86400`，負值代表下降 | 新 release |
| `pod_count` | count | 參與輸出的 POD observation 數；至少 56 | 已建立 |
| `max_pod_gap_s` | s | 該 bin/window 最大相鄰 POD 時差 | 已建立 |
| `chunk_id` | integer | 所屬安全計算 chunk | 已建立 |

## 不屬於這張表的欄位

原始 `x_m`、`velocity_m_s`、瞬時 `semi_major_axis_m` 與 `is_usable` 分別留在
`swarm_a_states`、`swarm_a_orbital_elements`、`swarm_a_pod_quality`。不要在 P1.5
重複複製它們。若後續研究需要高度，`semi_major_axis_orbit_mean_m - 6,371,000 m` 只能命名為
`mean_orbit_height_m`，不能冒充瞬時或 geodetic `altitude_m`。

## 實際資料量與行數限制

目前 POD 範圍是 2021-12-31 23:59:42 UTC 至 2026-08-12 23:59:32 UTC，
有 14,558,400 筆、10 秒分辨率的原始資料。這不是原先估計的 12 年、30 秒、
約 30,000,000 筆。

`swarm_a_orbit_10min` 為 226,800 列，6 個 `chunk_id`。每日 ZIP 不會自動切 chunk。
演算法為 `utc_10min_mean_brouwer_lyddane_v1`，bin contract 為 `[end - 600 s, end)`。

## 最終檢驗條件

以下是目標檢驗條件；標示為待確認者不可在目前當成 pass/fail。

| 檢驗 | 狀態 |
| --- | --- |
| 輸出列沒有 `NaN` 或無窮大 | [done] P1.7 audit 通過 |
| 每列源自 usable POD，且有 `chunk_id` | [done] P1.7 audit 通過 |
| 每個輸出 bin 有 56 至 60 筆 POD，最大間隔 10 秒，且不跨 chunk | [done] 實際 `pod_count = 58..60` |
| 各 window 的 `da_dt_Hh_backward_m_day` 量級合理且負值代表下降 | 待依 daily fit 比對；不可當作 acceptance threshold |
| 高度約 400 至 415 km | 待確認欄位定義；不可直接以未平滑 `a` 檢查 |
| `valid = true` 超過 300,000 行 | 待資料範圍擴充或改成目前範圍的比例門檻 |

## 執行位置

這份文件只定義 P1.5 的表格介面與 release checks。P1.5-A 至 P1.5-D 的執行順序、
synthetic tests、method decision 與停止條件只維護在
`p1_4_to_p1_7_execution_plan.md`，避免兩份文件日後分歧。
