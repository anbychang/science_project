# ISSUE

只記錄已確認、暫不處理的問題。

不重複 `PLAN.md` 的正式工作包；完成後刪除該項，必要結論寫回規格或 `TIMELOG.md`。

```text
[open]  有明確問題，尚未排程
[hold]  缺資料、方法或前置條件
[later] 現階段不需要，需求出現才處理
```

## 研究與資料

| 狀態 | 問題 | 暫緩原因 | 解除條件 |
| --- | --- | --- | --- |
| [hold] | ESA POD 沒有可用的 Q3 per-epoch quality/accuracy field。 | P1.4-C 已完成 header 與文件 audit；本機 SP3xCOM ZIP 沒有可用欄位，不可杜撰 quality filter。 | 取得 `SP3xVAL_2_` 或其他可追溯的官方逐筆品質來源。 |
| [hold] | Q4 maneuver 沒有可辯護的 rejection threshold。 | P1.4-D residual audit 已完成，但任意 `delta_v` threshold 可能刪除真實 storm-time response。 | 取得 external maneuver labels，或留存足以校準的人工審查與分布證據。 |
| [open] | SYM-H short-gap interpolation 使用晚於 target 的 right endpoint。 | 離線分析可接受；嚴格 forecast-safe feature 不可接受。 | 未來預報工作前，拆成 analysis-time 與 forecast-time rule。 |
| [later] | F10.7、Ap、SYM-H 只記 source time，未記實際發布時間。 | 現在是離線分析，不是即時預報。 | 開始 forecast / hindcast 時建立 availability policy。 |
| [later] | `swarm_a_density` 以單一 `time_us` 為 key，且用檔名判斷是否匯入。 | density 不是目前 P1.6 core feature；現在 migration 只會擴大工作。 | density 進入研究主線前，設計 source signature 與 key migration。 |

## 工程與維護

| 狀態 | 問題 | 暫緩原因 | 解除條件 |
| --- | --- | --- | --- |
| [later] | 本機沒有 `ruff` executable。 | unittest 與 `compileall` 可驗證目前行為；不為 lint 新增臨時依賴。 | 開發環境明確安裝並固定 Ruff 版本。 |
| [later] | `quality_flags` 目前只適合 P1.6 feature-missing token。 | 若 Q3/Q4 要同時保存多個 POD flag，逗號字串不是資料模型。 | 出現多重 POD flag 需求時，新建 keyed-by-`time_us` flag table。 |

## 結構與文件

| 狀態 | 問題 | 暫緩原因 | 解除條件 |
| --- | --- | --- | --- |

## 結構原則

```text
不要為減少檔案數硬合併：
download  = network side effect
load      = local parsing
prepare   = SQLite / derived write

可以合併的前提：
同一 input -> 同一 output -> 同一 side effect -> 一起改動
```

## 處理規則

```text
issue resolved
  -> 修正程式 / 資料 / 規格
  -> 加最小驗證
  -> 更新 TIMELOG.md
  -> 從本檔刪除
```
