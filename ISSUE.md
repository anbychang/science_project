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
| [open] | Phase 1 的 SYM-H short-gap interpolation 使用晚於 target 的 right endpoint；Phase 2 P2.1–P2.6 不內插地磁指數。 | 離線分析可接受；嚴格 forecast-safe feature 不可接受。 | 未來預報工作前，拆成 analysis-time 與 forecast-time rule。 |
| [open] | P2.3 的當前完整圈平均半長軸、圈尾與 `orbit_id` 晚於分鐘標籤才形成。 | 目前不是即時預報，先保留事後欄位；可接受約 1–2 h 資料延遲。v2 全圈結束最晚是分鐘標籤後 1.572 h，沒有超過 2 h 或隔天的完整圈。這是資料可用時間約定，不是嚴格因果推論。`storm_id`／`t_rel_h` 只作事後事件分組，不作預報輸入。 | 建模前明定發報時刻 `issue_time` 與預測目標時刻；只使用在 `issue_time` 前已形成的欄位，不使用隔天才形成的觀測。若稱「預測未來一天」，一天須從 `issue_time` 起算，不能從較早的分鐘標籤起算。 |
| [open] | P2.6 嚴格峰值順序只有 5/21 場符合，不能宣稱 SME 峰普遍先於密度差峰、SYM-H 最低點最後。 | 20/21 場為複合事件；每圈平均與 t0 前後 24 h 最大值可能挑到不同能量脈衝。這是已觀測的不一致，不應調整時間戳或刪事件來硬湊預期。 | 步驟三建立延遲核前，按單一脈衝與緯度／地方時分層重新檢查；若仍不符，修改驅動與延遲假設。 |
| [hold] | P2.4 有 4 場因 81 日 F10.7 歷史含 CelesTrak `INT` 日而無 MSIS 配對。 | 既定資料契約只接受完整 `OBS` 歷史；L2 覆蓋率本身約 99–100%。 | 取得可追溯的正式觀測版本，或先訂明替代來源與敏感度測試；不得把 `INT` 默認為 `OBS`。 |
| [open] | P2.4 原生圈計數比分鐘表多 18 筆 L2、16 筆配對樣本。 | 圈邊界樣本的四捨五入分鐘鍵落在 P2.3 選取分鐘外；現行覆蓋率與峰值稽核使用不同母體，不能改寫已封存 SQLite。 | 訂明邊界樣本歸屬後建立版本化 P2.4/P2.6，重新比較覆蓋率與峰值。 |
| [later] | F10.7、Ap、SYM-H 只記 source time，未記實際發布時間。 | 現在是離線分析，不是即時預報。 | 開始 forecast / hindcast 時建立 availability policy。 |

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
