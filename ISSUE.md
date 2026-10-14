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
| [hold] | `source_files` 未保存 SP3 frame label、coverage、epoch metadata。 | 跨 `IGb14`、`IGS20` 等 frame transition 的長期比較不安全。 | 完成 P1.4-C inventory 與 frame audit。 |
| [hold] | ESA POD 的 Q3 per-epoch quality/accuracy field 尚未確認。 | 沒有原始欄位或文件，不可杜撰 quality filter。 | 完成 ESA SP3/POD 文件與 sample audit。 |
| [hold] | Q4 maneuver candidate 沒有 calibration。 | 任意 `delta_v` threshold 可能刪除真實 storm-time response。 | 留存 residual 分布、人工檢查高值樣本、固定 robust threshold。 |
| [hold] | P1.5 尚無 orbit-average 或 mean-element 定義。 | raw osculating 半長軸的 spline / SG 導數已證明會產生假 decay。 | synthetic 與真實 clean interval 都能驗證方法。 |
| [open] | SYM-H short-gap interpolation 使用晚於 target 的 right endpoint。 | 離線分析可接受；嚴格 forecast-safe feature 不可接受。 | 未來預報工作前，拆成 analysis-time 與 forecast-time rule。 |
| [later] | F10.7、Ap、SYM-H 只記 source time，未記實際發布時間。 | 現在是離線分析，不是即時預報。 | 開始 forecast / hindcast 時建立 availability policy。 |
| [later] | `swarm_a_density` 以單一 `time_us` 為 key，且用檔名判斷是否匯入。 | density 不是目前 P1.6 core feature；現在 migration 只會擴大工作。 | density 進入研究主線前，設計 source signature 與 key migration。 |

## 工程與維護

| 狀態 | 問題 | 暫緩原因 | 解除條件 |
| --- | --- | --- | --- |
| [later] | 本機沒有 `ruff` executable。 | unittest 與 `compileall` 可驗證目前行為；不為 lint 新增臨時依賴。 | 開發環境明確安裝並固定 Ruff 版本。 |
| [later] | `quality_flags` 目前只適合 P1.6 feature-missing token。 | 若 Q3/Q4 要同時保存多個 POD flag，逗號字串不是資料模型。 | 出現多重 POD flag 需求時，新建 keyed-by-`time_us` flag table。 |
| [open] | P1.5 synthetic test 新增 mean-like SG pass case。 | 它只驗證理想慢變輸入，不驗證真實 orbit-average。 | 文件與測試名稱持續明確區分「候選條件」和「正式方法」。 |

## 結構與文件

| 狀態 | 問題 | 暫緩原因 | 解除條件 |
| --- | --- | --- | --- |
| [open] | `satellite_orbit/data/` 檔案過多，責任邊界難以掃讀。 | 先改檔名或硬併檔，容易破壞資料邊界與測試。 | 做 module audit：列出每檔 input、output、side effect、呼叫者；刪除無用 wrapper，合併真正同責任的小檔。 |
| [open] | 部分 data module 太長或同時 parse、SQLite write、batch orchestration。 | 50 行是閱讀目標，不是機械限制；為湊行數而拆檔會更難讀。 | 每個 module 只留一個可一句話說明的責任；複雜流程拆成短 pure helper 與一個 entry point。 |
| [later] | `calculation/` 不是目前資料準備主線。 | 現在搬移或重構不會解除 P1.4/P1.5 blocker。 | 要接 drag、做 propagation validation，或確認模組無人使用時再處理。 |
| [open] | `plans/` 有多份現行規格、執行計畫、報告與 archive，入口不明。 | 直接移檔會弄斷文件連結，也可能混淆歷史證據。 | 固定一份 canonical `PLAN.md`；其餘分為 `plans/active/`、`plans/decisions/`、`plans/archive/`，再更新連結。 |

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
