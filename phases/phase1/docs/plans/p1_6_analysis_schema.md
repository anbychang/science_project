# P1.6 分析資料欄位與來源追溯

NOTE: 本頁是 `swarm_a_analysis_10min` 舊分支的 schema，所列 224,280 筆、
3／6／12 小時 backward rate 和 `data/swarm_a_analysis.sqlite` 不是現行
P1.6 v2 的資料或路徑。現行 v2 feature 的 Input／Output 見
[orbit_analysis.md](../lineage/orbit_analysis.md) 的 P1.6 節。

## 文件地位

這份文件保留舊 `swarm_a_analysis_10min` 的欄位定義與追溯，不作現行 target。

P1.6-A/B 已完成：P1.5 先產生並驗證 10 分鐘軌道列，P1.6 再建立 224,280 列 final table；沒有以每 10 秒 POD 建立替代品。

## SQLite 型態約定

- `INTEGER`：64-bit 整數。用於 UTC Unix microseconds、數量與 ID。
- `REAL`：64-bit 浮點數。用於物理量與 index。
- `TEXT`：文字。用於受控的資料來源狀態與品質旗標。
- `NULL`：資料缺失或依規則不可使用；不等於零。

所有 `*_time_us` 都是 UTC Unix microseconds。它們不是顯示給人的日期格式，而是 SQLite join 與來源追溯使用的整數 key。

## 最終 table 的欄位定義

### P1.5 軌道結果

這組欄位由 P1.5 產生。P1.6 只複製到最後分析列，不重新計算。

| 欄位 | SQLite 型態 | Python 型態 | 單位 | 可否 `NULL` | 定義 |
| --- | --- | --- | --- | --- | --- |
| `time_us` | `INTEGER PRIMARY KEY` | `int` | UTC Unix microseconds | 不可 | 這筆 10 分鐘分析列代表的時間，也是所有 feature 對齊的 target key。P1.5 必須先固定其 bin timestamp 規則。 |
| `semi_major_axis_orbit_mean_m` | `REAL` | `float` | m | 不可 | `time_us` 對應的 10 分鐘 Brouwer-Lyddane mean semi-major axis。 |
| `da_dt_3h_backward_m_s` | `REAL` | `float` | m/s | 不可 | `(a(t) - a(t - 3 h)) / 3 h`。負值表示這 3 小時內半長軸下降。 |
| `da_dt_3h_backward_m_day` | `REAL` | `float` | m/day | 不可 | `da_dt_3h_backward_m_s * 86400`；負值表示下降。 |
| `da_dt_6h_backward_m_s` | `REAL` | `float` | m/s | 不可 | `(a(t) - a(t - 6 h)) / 6 h`。負值表示這 6 小時內半長軸下降。 |
| `da_dt_6h_backward_m_day` | `REAL` | `float` | m/day | 不可 | `da_dt_6h_backward_m_s * 86400`；負值表示下降。 |
| `da_dt_12h_backward_m_s` | `REAL` | `float` | m/s | 不可 | `(a(t) - a(t - 12 h)) / 12 h`。負值表示這 12 小時內半長軸下降。 |
| `da_dt_12h_backward_m_day` | `REAL` | `float` | m/day | 不可 | `da_dt_12h_backward_m_s * 86400`；負值表示下降。 |
| `pod_count` | `INTEGER` | `int` | count | 不可 | 建立這筆 10 分鐘列時實際使用的 POD observation 數量。完整 10 分鐘 bin 預期為 60 筆。 |
| `max_pod_gap_s` | `REAL` | `float` | s | 原則上不可 | 該 10 分鐘 bin 或所屬處理 window 中，相鄰 POD observation 的最大時間差。數值偏大代表缺資料風險。 |
| `chunk_id` | `INTEGER` | `int` | 無 | 不可 | P1.4 產生的 final continuous chunk。P1.5 bin 與所有 backward difference 都不可跨越它。 |

三個軌道欄位描述同一條軌道變化，但意義不同：

```text
semi_major_axis_orbit_mean_m  = 10 分鐘 mean semi-major axis
da_dt_3h_backward_m_s         = 過去 3 小時的每秒變化量
da_dt_3h_backward_m_day       = 過去 3 小時的每天半長軸變化量；負值代表下降
da_dt_6h_backward_m_s         = 過去 6 小時的每秒變化量
da_dt_6h_backward_m_day       = 過去 6 小時的每天半長軸變化量；負值代表下降
da_dt_12h_backward_m_s        = 過去 12 小時的每秒變化量
da_dt_12h_backward_m_day      = 過去 12 小時的每天半長軸變化量；負值代表下降
```

每個 window 的 m/s 與 m/day 欄位是同一個半長軸變化率的不同單位；例如 `da_dt_12h_backward_m_s = -0.00001` 時，`da_dt_12h_backward_m_day = -0.864`。

### SYM-H 地磁特徵

| 欄位 | SQLite 型態 | Python 型態 | 單位 | 可否 `NULL` | 定義 |
| --- | --- | --- | --- | --- | --- |
| `sym_h_nt` | `REAL` | `float` | nT | 可以 | 對齊到 target `time_us` 的 SYM-H。用來描述全球尺度地磁擾動。 |
| `sym_h_left_time_us` | `INTEGER` | `int` | UTC Unix microseconds | 隨 `sym_h_nt` 可為 `NULL` | 用於這個 SYM-H 值的左側原始觀測時間。exact match 時等於 target。 |
| `sym_h_right_time_us` | `INTEGER` | `int` | UTC Unix microseconds | 隨 `sym_h_nt` 可為 `NULL` | 用於這個 SYM-H 值的右側原始觀測時間。exact match 時等於 target；內插時可能晚於 target。 |

對齊規則：

```text
target 剛好有 minute observation
-> 直接使用，left = right = target

target 位於兩筆 observation 之間，且左右總 gap <= 2 分鐘
-> 線性內插，保留左右兩個 source time

缺任一側，或左右總 gap > 2 分鐘
-> 三個 SYM-H 欄位都為 NULL
```

右端點可晚於 target 是唯一允許的 future-time 例外，僅限兩分鐘內插，且左右 source time 必須完整留下。不可只有未來 observation 就直接使用。

### Ap 太空天氣特徵

| 欄位 | SQLite 型態 | Python 型態 | 單位 | 可否 `NULL` | 定義 |
| --- | --- | --- | --- | --- | --- |
| `ap_now` | `REAL` | `float` | Ap index | 可以 | target 所屬官方 3 小時 block 的 Ap 值。 |
| `ap_source_time_us` | `INTEGER` | `int` | UTC Unix microseconds | 隨 `ap_now` 可為 `NULL` | 此 Ap block 的 UTC 開始時間。 |

Ap 不做內插，也不自行改變 block：

```text
02:59:59 UTC -> 使用 00:00 block
03:00:00 UTC -> 使用 03:00 block
```

因此 `ap_source_time_us` 只能是 `00:00`、`03:00`、`06:00`、`09:00`、`12:00`、`15:00`、`18:00` 或 `21:00` UTC。

### F10.7 與 F10.7A 太陽活動特徵

| 欄位 | SQLite 型態 | Python 型態 | 單位 | 可否 `NULL` | 定義 |
| --- | --- | --- | --- | --- | --- |
| `f107_sfu` | `REAL` | `float` | sfu | 可以 | 因果安全的 F10.7 solar flux。 |
| `f107_source_time_us` | `INTEGER` | `int` | UTC Unix microseconds | 隨 `f107_sfu` 可為 `NULL` | F10.7 真正的原始日值所屬 UTC 00:00。 |
| `f107a_sfu` | `REAL` | `float` | sfu | 可以 | 因果安全的 trailing 81-day F10.7A average。 |
| `f107a_source_time_us` | `INTEGER` | `int` | UTC Unix microseconds | 隨 `f107a_sfu` 可為 `NULL` | trailing average 所屬來源日 UTC 00:00。 |
| `f107_data_type` | `TEXT` | `str` | 無 | 隨 weather feature 可為 `NULL` | F10.7 資料來源類型，例如 `OBSERVED` 或 `PREDICTED`。 |

例如 target 是 `2024-05-10 14:20 UTC`，兩個 source time 都是 `2024-05-09 00:00 UTC`。這確保分析不會使用目標時刻之後才知道的日值。

`f107a_sfu` 必須取自 raw table 的 `f107a_last81_sfu`，不可取 centered `f107a_sfu`。centered 81-day average 會使用未來日資料，只可保留給既有 NRLMSIS state，不能當 P1.6 因果分析 feature。

### 品質旗標

| 欄位 | SQLite 型態 | Python 型態 | 單位 | 可否 `NULL` | 定義 |
| --- | --- | --- | --- | --- | --- |
| `quality_flags` | `TEXT NOT NULL` | `str` | 無 | 不可 | 此列 feature 是否缺失的受控機器可讀標記；不是物理數值。 |

P1.6-B 固定使用下列最小 vocabulary：

```text
ok
missing_sym_h
missing_space_weather
missing_sym_h|missing_space_weather
```

它使用 `|` 串接多個受控 token，不使用自由文字、JSON、額外 flags table 或通用 rule engine。feature 缺失時保留整筆 orbit row，對應 feature 寫成 `NULL`，再以 `quality_flags` 標明原因。

## 每個資料來源做了什麼

### A. Swarm-A POD：從 SP3 到 P1.5 軌道欄位

**原始來源**：ESA Swarm-A precise-orbit POD ZIP；ZIP 內含 SP3 檔。

```text
ESA POD ZIP
-> SP3 epoch、P position line、V velocity line
-> GPS time 轉 UTC
-> position: km 轉 m
-> velocity: dm/s 轉 m/s
-> ITRF state
-> raw SQLite swarm_a_states
-> P1.3 instantaneous semi-major axis
-> P1.4 usability + chunk_id
-> P1.5 orbit mean / 3h, 6h, 12h backward differences
-> P1.6 複製為最終分析列的軌道欄位
```

各步驟的實際責任：

1. `load_swarm_pod.py` 從 ZIP 找出 `.sp3`，讀取 epoch、位置與速度。時間原本是 GPS time，會轉成 UTC；位置與速度進入專案後都是 SI units。
2. `prep_01_raw_pod.py` 將 state 寫入 `swarm_a_states`：`time_us`、ITRF `x_m` 至 `vz_m_s`、`weather_time_us`、`source_id`。只有能對應到已存在 3 小時 weather block 的 POD 才會存入。
3. `prep_03_orbital_elements.py` 讀 raw ITRF state，轉 GCRF，以 two-body specific energy 算每 10 秒一筆 `semi_major_axis_m`，寫入 `swarm_a_orbital_elements`。non-finite 或 non-bound state 不假造數值，而是留下 `rejection_reason`。
4. `prep_05_pod_quality.py` 讀 raw state 加上 P1.3 結果，產生 `is_usable`、`rejection_reason` 與 `chunk_id`。product stream、frame、cadence 或 time gap 有變化或不確定就切 chunk；Q3 為 `quality_source: unavailable`，Q4 為 audit-only。
5. P1.5 已用 Brouwer-Lyddane mean orbit 建立 10 分鐘列，再在每個 contiguous chunk/run 以 `a(t)` 與 `a(t - H h)` 算 `H = 3, 6, 12` 的自然符號 backward difference；沒有直接對 osculating semi-major axis 發布衰減率。

因此 P1.6 不碰原始 position/velocity，也不從每 10 秒 POD 自己做 10 分鐘 bin；它只接受 P1.5 已驗證的結果。

### B. SYM-H：從 WDC Kyoto minute data 到 `sym_h_nt`

**原始來源**：WDC Kyoto HAPI `min_asysym` dataset，欄位為 `symHValue` 與 `versionCode`。

```text
WDC Kyoto HAPI CSV
-> 跳過 header 與 99999 缺失碼
-> ISO UTC time + integer nT + version
-> raw SQLite geomagnetic.sym_h_nt / sym_h_version
-> P1.6 exact match 或 <= 2 分鐘線性內插
-> sym_h_nt + left/right source time
```

下載器每次最多下載 180 天，並檢查下載檔最後 observation 是否真的到達 requested end date。這是因為 WDC 曾回傳看似成功、實際提早中斷的年度資料。

目前 raw SYM-H 覆蓋 `2021-01-01 00:00:00` 至 `2026-08-12 23:59:00` UTC；相鄰最大 gap 為 60 秒，覆蓋本機 POD 時段。

### C. AE：保存來源，但目前不放進 P1.6 最終 schema

**原始來源**：WDC Kyoto HAPI `min_ae` dataset，欄位為 `aeValue` 與 `versionCode`。

它經過與 SYM-H 相同的 CSV 清理與時間轉換，寫入同一張 `geomagnetic` table 的 `ae_nt` 與 `ae_version`。

AE 現在是已保存、可追溯的 raw source，但尚未被定義為 P1.6 正式 feature。不要因為資料已在 SQLite 就自行加入最終分析表；是否使用 AE 應先有研究問題與時間規則。

### D. F10.7、F10.7A、Ap：從 CelesTrak 到 P1.6 weather 欄位

**原始來源**：[CelesTrak `SW-All.csv`](https://celestrak.org/SpaceData/SW-All.csv)。每個日列提供 daily F10.7、81-day averages、daily Ap 與 8 個官方 3 小時 Ap 值。

```text
SW-All.csv 的 daily row
-> 每日 8 個 Ap slot 展開成 3 小時 UTC block
-> 前一日 F10.7_OBS 與 F10.7_DATA_TYPE
-> 當日 centered F10.7_OBS_CENTER81
-> 當日 trailing F10.7_OBS_LAST81
-> raw SQLite space_weather
-> P1.6 依 target time 選 Ap block、前一日 F10.7、前一日 trailing F10.7A
```

`prep_raw_weather.py` 的實際結果是每 3 小時一列 `space_weather`：

- `ap_now`：該 3 小時 block 的官方 Ap。
- `ap_daily`、`ap_3h`、`ap_6h`、`ap_9h`、`ap_12_to_33h_avg`、`ap_36_to_57h_avg`：保留給 NRLMSIS 或後續明確需求；目前不會自動進 P1.6 final schema。
- `f107_sfu`：已經是前一日 `F10.7_OBS`，所以 P1.6 取 target 當下 block 的此欄位，但 provenance 標成前一日 UTC 00:00。
- `f107a_sfu`：當日 centered `F10.7_OBS_CENTER81`，保留給 NRLMSIS，禁止作為 P1.6 feature。
- `f107a_last81_sfu`：當日 trailing `F10.7_OBS_LAST81`；P1.6 取前一日這個欄位，寫入最終的 `f107a_sfu`。
- `f107_data_type`：與前一日 F10.7 原始值一起保存，例如 `OBSERVED` 或 `PREDICTED`。

P1.6 使用 space weather 時，不得內插 Ap，不得以未來日 F10.7/F10.7A 補值。缺 target 3 小時 block 或前一日來源 row 時，weather feature 全部為 `NULL`。

### E. Swarm DNSAACC density：保留但不強行 join

**原始來源**：Swarm DNSAACC density product。

```text
原始 density product
-> UTC time、density、altitude、latitude、longitude、local solar time
-> raw SQLite swarm_a_density
-> 目前停止
```

它不是 P1.6 核心 feature，也不會被自動塞進 `swarm_a_analysis_10min`。原因不是資料沒用，而是其時間對齊、物理角色與研究問題都還沒有定義；現在 join 只會增加看似完整但無法解釋的欄位。

## P1.6-B 寫入規則

輸入只能是：

```text
P1.5 swarm_a_orbit_10min
raw geomagnetic
raw space_weather
```

每一筆 P1.5 orbit row 依 `time_us` 套用本文件定義的 alignment rules。寫入時必須遵守：

1. 不刪除 orbit row。
2. 缺 feature 時寫 `NULL` 和受控 `quality_flags`。
3. 不修改 raw table、P1.3 table 或 P1.4 table。
4. 每個 source time 必須 `<= time_us`，唯一例外是已記錄左右端點的 SYM-H 短 gap 內插。
5. 輸出 row count、UTC 範圍、各 `quality_flags` 數量與 source-time audit。

## 已有驗證

- exact SYM-H minute。
- 一分鐘內的 SYM-H 合法內插。
- 三分鐘 gap 時拒絕 SYM-H 內插。
- 只有未來 SYM-H observation 時拒絕使用。
- Ap `02:59:59` 與 `03:00:00` boundary。
- F10.7 與 F10.7A 的前一日 source time。
- F10.7A 使用 trailing 而非 centered average。
- target weather source 缺失時回傳缺失 feature。

## 已發布結果

- `swarm_a_orbit_10min`：224,928 列，`utc_10min_mean_brouwer_lyddane_v1`。
- 新 release 將使用 `causal_space_weather_geomagnetic_backward_3h_6h_12h_v3`；row count 以 P1.7 manifest 為準。
- 每個 final feature 都有 source time；P1.7 audit 確認沒有不合規 future reference。
- DNSAACC density 不在 final schema；它只保留於 raw `swarm_a_density`。
