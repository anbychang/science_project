# 第一階段計畫：Swarm-A 資料準備

NOTE: 本頁保留原先 10 分鐘分析資料集的設計與驗證紀錄，**不是現行 P1.5.6--P1.7
輸出契約**。現行逐 10 秒、3／5 個 phase orbit 的 raw B-L／joint H2/H3 局部斜率、
共用 P1.6 feature 與 P1.7 v2 audit，以
[PHASE_1_EXECUTION_PLAN.md](PHASE_1_EXECUTION_PLAN.md) 和
[orbit_analysis.md](../../data_lineage/orbit_analysis.md) 為準。本頁提到的
`data/old/`、`data/swarm_a_analysis.sqlite` 與 14,558,400 筆統計均屬舊範圍，
不得當成目前檔案路徑或資料量。

## 目標

建立一份可重建、每 10 分鐘一列的 Swarm-A 資料集，用來研究軌道衰減與地磁、太陽活動的關係。每個衍生數值都必須保留來源時間與品質判斷。

這個階段只建立資料，不訓練機器學習模型，也不把大氣阻力接進 propagator。

## 基本約定

- 軌道 `state` 形狀：`{time, frame, position_m, velocity_m_s}`。
- 專案內部使用 SI 單位：`m`, `m/s`, `m/s^2`, `s`, `kg/m^3`。
- 原始 POD 使用 SP3 header 寫明的地球固定 IGS reference frame。現有 `loader` 暫時把它泛稱為 `ITRF`；跨時段正式分析前要處理下方的 frame issue。
- 所有資料對齊都使用 UTC。
- 半長軸變化率同時保存 3、6、12 小時 window：`da_dt_Hh_backward_m_day = (a(t) - a(t - H h)) / H h * 86400`；負值代表半長軸下降。

### Chunk 規則

每個計算都在安全的 `chunk_id` 內完成。`source_id` 或每日 ZIP 改變本身不是 boundary；
只要 product stream、SP3 frame、cadence
或時間連續性有任何改變或不確定性，就結束舊 chunk、開始新 chunk。多切可以接受；少切
不可以。只保存 `chunk_id`，不保存 `chunk_reason`。

```text
chunk_id
  -> mean orbit
  -> 10-minute bin
  -> 3h, 6h, 12h backward differences
```

任何一步都不可跨 chunk。

## 資料來源與原始解析度

| 資料來源 | 原始解析度 | 原始儲存 | 目標 10 分鐘特徵 |
| --- | ---: | --- | --- |
| ESA Swarm-A POD | 由 SP3 header 驗證；目前為 10 秒 | 位置與速度 | 軌道 `state`、半長軸 |
| SYM-H | 1 分鐘 | `geomagnetic.sym_h_nt` | 線性內插 |
| Ap | 3 小時 | `space_weather.ap_*` | forward-fill |
| F10.7 / F10.7A | 每日來源，儲成 3 小時列 | `space_weather.f107_sfu`, `f107a_sfu` | forward-fill |

不要假定 POD 是固定 cadence；要從下載檔實際測量相鄰時間並記錄 gap。

## 處理流程

```text
POD ZIP + SYM-H + Ap/F10.7
            |
            v
raw SQLite: data/old/swarm_a_data.sqlite
            |
            v
UTC alignment, GCRF conversion, orbital elements
            |
            v
quality labels and continuous usable intervals
            |
            v
10-minute resampling and verified short-period treatment
            |
            v
derived 10-minute analysis dataset
```

## Raw 與衍伸資料規則

SQLite 的 raw table 是不可變的來源紀錄。`swarm_a_states`、`space_weather`、`geomagnetic` 與 `swarm_a_density` 只由 `prep_raw_database.py` 寫入；後續計算不可修改或刪除其中的 observation。

要增加新維度時，使用下面固定流程：

```text
load SQLite raw data
    -> calculate one new quantity
    -> write a separate derived table
```

每個 derived row 必須保留原始 `time_us`，並記錄演算法與必要設定。例子：P1.3 從 `swarm_a_states` 讀取 POD，計算後寫入 `swarm_a_orbital_elements`；原始 POD table 不變。

## 資料血緣文件格式

資料沿革是 repository 的獨立 target，放在 [`data_lineage/`](../../data_lineage/README.md)。它按下載資料與資料產品記錄完整 flow，不按 phase 分類。

每個處理 stage 固定使用一個 block：

```text
### [N] input -> output
資料：輸入資料或 shape
程式：module.py -> function()
動作：轉換、計算、filter、join 或停止條件
輸出：檔案、SQLite table、derived table 或 temporary state
e.g.：一個具體輸入 -> 動作 -> 具體輸出

### [N] current stored state
path、table、fields、raw / derived / temporary

### [STOP]
未建立、未 join、禁止 operation
```

`資料`、`輸出`、`e.g.` 的 `{}` 與 `[]` 使用多行；不以長句重述欄位。每類 raw data 各有一份文件，不在 README 或 memo 複製完整流程。

未實作 stage 的 `程式` 必須寫「未建立」，不能用規格文件偽裝成現行程式。

## 工作項目

### P1.1 下載與盤點 POD

1. 下載所選期間的 Swarm-A precise-orbit products。
2. 記錄來源 URL、產品版本、下載日期、ZIP 檔名、UTC 覆蓋範圍、epoch 數與量測到的 sampling interval。
3. 原始 ZIP 保留在 `data/swarm_a_pod/`，不可修改內容。
4. 在算任何趨勢前，找出缺日與時間 gap。

完成條件：每份原始檔可追溯，且 UTC 覆蓋範圍已知。

### P1.2 建立原始資料庫

使用 `python -m satellite_orbit.data.database.prep_raw_database`。它把原始觀測寫到分開的 SQLite tables；POD row 只連到可用的 3 小時 weather block。

完成條件：已報告 row count、首尾 UTC、重複時間與 source provenance。原始觀測不可在原 table 中 resample。

狀態：`[done]`

- SQLite：`data/old/swarm_a_data.sqlite`，目前約 1.8 GiB；可由 raw source 重建。
- POD：14,558,400 筆，2021-12-31 23:59:42 UTC 至 2026-08-12 23:59:32 UTC。
- 每筆 POD 都有完整的位置與速度；沒有重複 `time_us`。
- 1,685 個 `source_files` 與 1,685 個原始 POD ZIP 一一對應。
- SQLite 中保留 10 秒原始 POD，不含半長軸、平滑值或衰減率。

### P1.3 計算瞬時半長軸

每個通過品質條件的 POD epoch，都要先把完整 `state` 從 earth-fixed frame 轉成 GCRF，才能計算：

```text
r = norm(position_m)
v = norm(velocity_m_s)
specific_energy_m2_s2 = v^2 / 2 - earth_mu_m3_s2 / r
semi_major_axis_m = -earth_mu_m3_s2 / (2 * specific_energy_m2_s2)
```

這是 osculating two-body element。J2、殘餘 POD noise 與 frame conversion 會造成短週期波動，所以它不是直接量到的 drag。

完成條件：拒絕 non-finite value 與 non-bound state，保留 `rejection_reason`；用獨立 orbital-element tool 或手算驗證小樣本。

狀態：`[done]`

- `swarm_a_orbital_elements` 有 14,558,400 筆，與 raw POD 筆數完全一致。
- 所有半長軸都是有效值；`rejection_reason` 為 0 筆。
- 每個 derived row 以相同 `time_us` 對應一筆 raw POD；沒有缺少的半長軸列。
- circular-orbit 手算測試、GCRF frame 檢查與真實 POD 單日 rollback 檢查都已通過。

### P1.4 品質控制與連續區間

在平滑前套用品質規則。保留 `is_usable` 與機器可讀的 `rejection_reason`，不刪除被拒絕的原始列。遇到 product stream、provenance frame、cadence、time gap 或 quality failure 時切開 chunk。未標記的 Q4 maneuver candidate 只做 audit，不切 chunk；有官方證據的 Swarm-A orbit event 採 UTC date-level exclusion，必須切開 chunk。

完成條件：每個保留的 10 分鐘 row 都來自一個連續 usable chunk，並報告每種 `rejection_reason` 的數量。

完成：P1.4-A/B 產生 14,558,400 quality rows；P1.4-C 將 SP3 provenance 寫入
`swarm_a_pod_source_provenance`，Q3 是 `quality_source: unavailable`；P1.4-D 完成 residual
audit。未標記 Q4 保留 rows、不設未校準 rejection threshold；已確認的官方 event 依 canonical
date interval 排除。細節見
`P1.4_QUALITY_CONTROL.md`；完成證據見 `PHASE_1_EXECUTION_PLAN.md`。

### P1.5 Resample 並推導衰減率

1. 定義 UTC 10 分鐘 bin boundary。
2. 只使用同一個連續 chunk 內、有至少 56 筆有效 POD observation 的 bin；記錄 `pod_count` 與最大 source-time gap。
3. 先做已驗證的 short-period treatment；不得直接對 osculating 半長軸做 Savitzky-Golay
   或 B-spline 再把導數當 decay。
4. 每個 valid chunk 分開處理，不可跨 gap；分別比較同一 chunk 的 `a(t)` 與 `a(t - 3 h)`、`a(t - 6 h)`、`a(t - 12 h)`。
5. 儲存 `semi_major_axis_orbit_mean_m`，以及每個 window 的 `da_dt_Hh_backward_m_s` 與同符號的
   `da_dt_Hh_backward_m_day`。

完成：direct raw Savitzky-Golay 已淘汰；Brouwer-Lyddane mean-orbit method 通過 synthetic
與 real-POD gate，並建立 14,558,400 legacy mean rows。fresh rebuild 僅為 13,608,000 usable
POD 建立 mean rows。`swarm_a_orbit_10min` 有 226,800 列，
每個連續 run 同時產生 3、6、12 小時 backward difference；為保留完整三組 rate，各 run 的前 72 列排除。

完成條件：乾淨的 synthetic linear-decay input 可恢復正確 slope；輸出不可跨 source gap。

### P1.6 對齊 space-weather 與 geomagnetic 特徵

對每個保留的 10 分鐘 UTC timestamp：

- SYM-H：只在兩個有效的 1-minute observation 之間 linear interpolate；不可跨已定義的 gap，否則 feature 缺失。
- Ap：在 official 3-hour block 中 forward-fill。
- F10.7/F10.7A：forward-fill daily value，並保留 `f107_data_type` 分辨 observed、estimated 與 predicted；
  分析用的 `f107_sfu` 與 `f107a_sfu` 都使用前一日來源，並各自保留 source timestamp。
  `f107a_sfu` 使用 causal `F10.7_OBS_LAST81`；既有 NRLMSIS 用的 centered 81-day value
  不能用於禁止 future leakage 的分析資料。
- 每個 feature 都保存原始 source timestamp。

完成：join 不使用 future value；00:00 UTC、3-hour Ap transition、SYM-H interpolation/gap
與前一日 F10.7/F10.7A source time 均有 contract tests；P1.7 audit 也確認 final rows 無
不合規 future reference。

### P1.7 發布衍生資料集

建議的衍生 row shape：

```text
{
  time,
  semi_major_axis_orbit_mean_m,
  da_dt_3h_backward_m_s, da_dt_3h_backward_m_day,
  da_dt_6h_backward_m_s, da_dt_6h_backward_m_day,
  da_dt_12h_backward_m_s, da_dt_12h_backward_m_day,
  pod_count,
  max_pod_gap_s,
  chunk_id,
  sym_h_nt,
  sym_h_left_time,
  sym_h_right_time,
  ap_now,
  ap_source_time,
  f107_sfu,
  f107_source_time,
  f107a_sfu,
  f107a_source_time,
  f107_data_type,
  quality_flags
}
```

資料旁要保存 source signature、code revision、frame、Earth gravitational parameter、short-period treatment、3/6/12 小時 interval contract、日期範圍與 row count。P1.7 必須逐列驗證每個 `H` 的 `da_dt_Hh_backward_m_s = (a(t) - a(t - Hh)) / Hh`，並驗證 m/day 欄位的單位換算。CSV 或 Parquet 是可選 export；SQLite 是工作資料庫。

POD 最終輸出欄位、行數限制與檢驗條件見 `POD_FINAL_OUTPUT_SPEC.md`。

完成條件：產物可從 raw input fresh rebuild，metadata 足以重現結果。

## 完成檢查

- [x] POD coverage 與 native sampling interval 已 audit。
- [x] Raw SQLite database 已成功 rebuilt。
- [x] GCRF orbital-element calculation 已驗證。
- [x] Quality rules 已完成；未標記 Q4 維持 audit-only；已確認官方 orbit event 採 date-level exclusion。
- [x] Direct raw Savitzky-Golay candidate 已用 synthetic data 淘汰。
- [x] Mean-element method 已用 synthetic 與 real-POD data 驗證；全庫 14,558,400 列完成。
- [x] 10-minute feature join 已在 boundary 與 gap 驗證。
- [x] 現有 SQLite 的 derived dataset 與 metadata 已建立；P1.7 integrity / foreign-key / causality audit 通過。
- [x] 舊 10 分鐘分支的 `data/swarm_a_analysis.sqlite` 當時通過 P1.7 audit；該檔目前不在工作區，不能用來代表現行 v2 audit。

## 暫緩決定

- 精確 date range 與目標 geomagnetic storm 數量。
- Orbit-average definition 與最小 usable bin count。
- 哪個 `da_dt_Hh_backward_m_day` 是後續分析 target，或三者都作為分析輸出。
- 是否加入 AE 或其他 geomagnetic index。

這些要根據真實 POD cadence 與初步 QC report 決定；現在硬選只是在猜。

## 品質規則

品質控制要分開處理已知壞資料、資料不連續與真實的 storm-time drag。不能因為衰減很大就把正常物理現象刪掉。

每條規則都要記錄 input、threshold/version 與 `rejection_reason`。Raw database 保留列，即使它不能進 analysis。

| ID | 規則 | 初步動作 | 狀態 |
| --- | --- | --- | --- |
| Q1 | 缺失、non-finite 或時間不遞增的 POD `state` | reject row | fixed |
| Q2 | provenance/frame/cadence change，或相鄰 POD 時間 gap | close chunk；不可跨它內插 | fixed |
| Q3 | ESA POD 有官方 quality/accuracy flag 且不符合最高可用品質 | `quality_source: unavailable`；不杜撰 filter | 已確認本機 SP3xCOM 無可用欄位 |
| Q4 | 未標記 `state` jump 與相鄰 observation 不一致 | audit-only；記錄 residual，不拒絕 row、不切 chunk | fixed audit-only |
| Q4-E | 有官方證據的 Swarm-A orbit event | UTC date-level exclusion；reject row 並切開 chunk | fixed |
| Q5 | energy 無效：non-finite、`specific_energy_m2_s2 >= 0` 或 radius 無效 | reject row | fixed |
| Q6 | `pod_count <= 55` 或跨 chunk boundary | exclude derived bin | fixed |
| Q7 | feature 缺失或需要 future value | 保留 orbit row；標記 feature missing | fixed |

### 門檻決定

不要把任一 `da_dt_Hh_backward_m_day < -0.3` 當 raw-data acceptance rule。它會刪掉弱但有效的衰減，也會偏向只留下 active period。若研究後來只看 strong-decay window，應在完成 QC 後當成 analysis selection。

不要把 `delta_v < 10 m/s` 當未標記 maneuver 的 rejection rule。現階段只量測 clean interval 的 epoch-to-epoch residual、position 與 velocity；沒有可查核 external label 前不設定 threshold，也不改變 chunk。

### 官方 orbit event exclusion

canonical event ID、kind 與 UTC half-open interval 只在
`ORBIT_RAISE_CAMPAIGN_MEMORY.md` 維護；`OFFICIAL_SWARM_A_ORBIT_EVENTS` 必須完全相同。
每次改動都要重建新的 SQLite target，並將 policy version 與 event list 寫入 P1.7 metadata。

SP3 可能沒有逐 epoch 的單一 `good` flag。實作 Q3 前先確認 ESA product field 與 quality document；若沒有可用 flag，要明確記錄並改用可重現的一致性檢查。

### 必要報告

每一版產物都要報告 raw/usable POD row count、每種 `rejection_reason`、continuous chunk coverage、POD cadence/gap、maneuver residual 與 derived-feature missingness。

### 最小驗證案例

| 案例 | 預期結果 |
| --- | --- |
| Constant two-body state sequence | stable semi-major axis；3/6/12 小時 rates 接近零 |
| Synthetic linear semi-major-axis decrease | derivative 大小正確，且 decay-rate sign convention 正確 |
| One missing POD block | 形成兩個 chunk；derived row 與任一 backward interval 不可跨 block |
| One injected state jump | 成為 maneuver candidate；記錄 residual，不切 chunk |
| SYM-H source gap | 不可跨 gap interpolation |
| Ap boundary at 03:00 UTC | value 只在 official block boundary 改變 |

## 暫緩議題：POD reference-frame transition

下載的 Swarm-A SP3 檔跨越 `IGb14`、`IGS20`、`IGb20` 與 `IGc20`。
`swarm_a_pod_source_provenance` 已保存 SP3 frame label、coverage、epoch count、cadence 與
time system；loader 仍把 state 泛稱為
`ITRF`。

現在 POD inventory 不處理它。正式做跨時段 semi-major-axis、decay-rate 或比較前，要：

1. [done] 讀取並依 source ZIP 儲存 SP3 frame label。
2. 決定並記錄是否需要 realization-specific transformation。
3. [done] 報告每個 transition 前後的 semi-major-axis median；不套用人為 offset。

## 暫緩議題：IERS 時間與地球方向資料

現有 ITRF-to-GCRF round-trip test 已在最新本機 POD 日期通過，且現有程式禁止自動下載
IERS；正式批次仍必須固定並記錄 local leap-second 與 Earth-orientation data 版本，不能
依賴日後自動更新。

一般執行不可使用未追蹤的 automatic update。正式批次 coordinate conversion 或 semi-major-axis analysis 前，要：

1. 選擇並記錄適用期間的 IERS/leap-second data version。
2. 讓資料透過 local file 或一次明確、可記錄的 update step 提供。
3. 在最早與最新 POD 日期驗證 GCRF conversion。
