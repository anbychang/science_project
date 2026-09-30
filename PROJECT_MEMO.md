# Swarm-A 軌道衰減研究備忘錄

最後更新：2026-09-30

這份文件是不帶日期的「目前有效定義」。時間順序與實驗結果看 `TIMELOG.md`。

## 研究問題與第一階段目標

研究問題：地磁暴如何影響 Swarm-A 軌道衰減。

第一階段只交付可重建的 10 分鐘分析資料集。它必須能追溯每個 orbital result 與 environmental feature 的原始來源時間。

不在目前範圍：

- XYZ 軌道預報主線。
- machine learning。
- 將 atmospheric drag 接入 propagator。
- 未定義研究意義就把 density 或 AE 強行加入 analysis table。

## 目前資料流程

```text
ESA Swarm-A POD ZIP
-> raw swarm_a_states
-> P1.3 swarm_a_orbital_elements
-> P1.4 swarm_a_pod_quality
-> P1.5 swarm_a_orbit_10min
-> P1.6 swarm_a_analysis_10min
-> P1.7 export / metadata / rebuild check

CelesTrak SW-All.csv
-> raw space_weather
-> P1.6 Ap / F10.7 / F10.7A

WDC Kyoto SYM-H / AE
-> raw geomagnetic
-> P1.6 SYM-H
```

`swarm_a_orbit_10min` 與 `swarm_a_analysis_10min` 尚未建立；它們是 P1.5 與 P1.6-B 的預定 derived tables。

## 資料責任規則

- raw SQLite tables 是來源紀錄；後續計算不可 update 或 delete raw observation。
- calculation 一律寫新的 derived table，並以同一 `time_us` 可追溯到來源。
- 專案通用 state：`{time, frame, position_m, velocity_m_s}`。
- 一個 orbit series：`[state, ...]`。
- 內部使用 SI units；只在 loader 或外部 library call 做單位轉換。
- 每個 Python function 要用短 docstring 寫明 Input 與 Output。

## 模組責任

```text
prep_raw_*       原始檔寫入 raw SQLite
prep_derived_*   raw table 產生 derived table
prep_feature_alignment.py
                 P1.6 pure feature timing rules
load_*           讀取本機原始檔或 SQLite
down_*           下載原始資料
calc_*           物理與數值計算
```

通常更新資料庫只執行：

```powershell
python -m satellite_orbit.data.prep_raw_sqlite
```

## 已確認的資料狀態

| 資料 | 狀態 |
| --- | --- |
| POD | 14,558,400 rows；2021-12-31 23:59:42 至 2026-08-12 23:59:32 UTC；native cadence 10 s |
| P1.3 | 每筆 POD 都有 instantaneous semi-major axis；non-bound result 會保留 rejection reason |
| P1.4-A/B | 14,558,400 usable rows；1,685 intervals；每個 interval 8,640 rows；Q3/Q4 尚未完成 |
| SYM-H / AE | 各 2,952,000 minute rows；2021-01-01 至 2026-08-12；SYM-H 最大 gap 60 s |
| space weather | 201,861 個 3-hour rows；足以覆蓋 POD |
| DNSAACC density | 436,708 raw rows；已保存，不是 P1.6 core feature |

## P1.5 硬性停止條件

不可直接對每 10 秒 osculating `semi_major_axis_m` 做 B-spline 或 Savitzky-Golay，然後把 derivative 當 atmospheric decay。

原因：試跑的 GCV cubic spline 得到 `-7.97 m/s`，相當於每天數十萬公尺下降，顯然在追蹤 J2 等 short-period variation，不是真實 drag。

P1.5-A 的 direct raw Savitzky-Golay synthetic test 也已淘汰 1、2、3 個 representative
short-period window。已知 `1 m/day` trend 加入 km-level periodic variation 後，6 個 candidate
全都無法通過 slope recovery gate。完整定義與結果看 `P1.5_RESAMPLE_AND_DECAY.md`。

P1.5-A 仍要完成 orbit-average 或理論 mean-element conversion 的定義與驗證。P1.5 的輸出只可在同一 `interval_id` 內計算。

已驗證的 numerical candidate 只適用於 mean-like 10-minute series：73-sample（12 小時）
centered Savitzky-Golay、order 2，兩端各排除 6 小時。真實資料尚未證明符合它的 input contract，
所以這不是 P1.5 release。

simple rectangular orbit-average 已實測淘汰：1 至 12 Kepler orbits 的 residual std 都約 12 至
13 m，不能交給 SG candidate。下一個合理選項是 Brouwer-Lyddane conversion；本機尚無其
Orekit / Java dependency，不能自行重寫公式冒充等價方法。

## P1.6 硬性規則

詳細欄位、型態與完整 lineage 看 `plans/phase_1_data_preparation/P1.6_ANALYSIS_SCHEMA.md`。

- SYM-H：exact minute，或左右 source total gap <= 2 分鐘時的線性內插；否則 `NULL`。
- Ap：使用 target 所屬 official 3-hour block；不內插。
- F10.7：使用前一日已知值，保存 `f107_source_time_us`。
- F10.7A：使用前一日 `F10.7_OBS_LAST81`，絕不可使用 centered `F10.7_OBS_CENTER81` 做 P1.6 analysis。
- feature 缺失時保留 orbit row，feature 欄位為 `NULL`，用受控 `quality_flags` 標示原因。
- 除 SYM-H 已記錄左右端點的短 gap 內插外，任何 feature source time 都必須 `<= target time_us`。

P1.6-A 已完成。P1.6-B 等 P1.5 固定 final 10-minute orbit schema 後才可開始。

## 目前待做

1. P1.4-C：SP3 frame / Q3 official quality audit。
2. P1.4-D：Q4 maneuver candidate calibration。
3. P1.5-A：orbit-average synthetic validation 與 short-period method selection。
4. P1.5-B/C/D：只在 P1.5-A 決定方法後開始。
5. P1.6-B：只在 P1.5 final schema 存在後開始。
6. P1.7：乾淨資料夾重建、metadata、export 與 release report。

## 文件入口

- `plans/phase_1_data_preparation/PLAN.md`：第一階段唯一正式規格。
- `plans/phase_1_data_preparation/P1.4_TO_P1.7_EXECUTION_PLAN.md`：依賴、可平行工作、停止條件。
- `plans/phase_1_data_preparation/P1.4_QUALITY_CONTROL.md`：P1.4 實作與結果。
- `plans/phase_1_data_preparation/P1.5_RESAMPLE_AND_DECAY.md`：P1.5 的失敗試跑與方法限制。
- `plans/phase_1_data_preparation/P1.6_ANALYSIS_SCHEMA.md`：P1.6 schema 與所有 feature 來源追溯。
- `TIMELOG.md`：日期順序的實驗紀錄。

## Git

- Remote：`https://github.com/anbychang/science_project.git`。
- Branch：`master`。
- 每完成一個可驗證工作包：更新受影響規格、更新 `TIMELOG.md` 的日期紀錄、commit；只有使用者要求時才 push。
