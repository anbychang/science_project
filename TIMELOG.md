# Swarm-A 軌道衰減研究實驗日誌

最後更新：2026-09-30

這份檔案記錄實際做過的研究與工程工作：為什麼做、輸入資料是什麼、實際操作、量到什麼、因此做出什麼決定，以及下一步。它不是完整技術規格；正式欄位定義與研究 gate 請看 `plans/phase_1_data_preparation/`。

## 目前位置

研究問題：地磁暴如何影響 Swarm-A 軌道衰減。

目前只進行第一階段：將 Swarm-A POD、space weather 與 geomagnetic data 整理成可重建的 10 分鐘分析資料集。XYZ 軌道預報、machine learning、將 atmospheric drag 接入 propagator 都不是目前範圍。

```text
已完成
P1.1 原始 POD 取得
P1.2 raw SQLite 建置
P1.3 瞬時半長軸計算
P1.4-A/B 基本品質檢查與連續區間
P1.6-A feature 時間對齊規則

尚未完成
P1.4-C/D frame/Q3 audit 與 maneuver 校準
P1.5 orbit-average、short-period 處理、10 分鐘衰減率
P1.6-B 最終 analysis table writer
P1.7 可重建資料集發布
```

目前資料庫：`data/swarm_a_data.sqlite`，約 1.91 GB，不提交 Git。

| Table | 已寫入列數 | 用途 |
| --- | ---: | --- |
| `swarm_a_states` | 14,558,400 | raw POD ITRF position/velocity |
| `swarm_a_orbital_elements` | 14,558,400 | P1.3 instantaneous semi-major axis |
| `swarm_a_pod_quality` | 14,558,400 | P1.4 quality 與 interval |
| `geomagnetic` | 2,952,000 | raw SYM-H / AE minute data |
| `space_weather` | 201,861 | raw F10.7 / F10.7A / Ap 3-hour rows |
| `swarm_a_density` | 436,708 | raw DNSAACC density，尚未進核心分析 |

## 實驗紀錄

### 2026-09-15：建立原型並淘汰 ISS 假資料

**目的**：先確認軌道資料處理、Git 保存與數值傳播是否能跑通。

**做了什麼**：

1. 建立本機 Git repository 與私有 GitHub repository。
2. 使用 ISS TLE、假軌道與假太空天氣資料做初期程式原型。
3. 檢視 TLE、OEM、POD 的資料意義與精度差異。
4. 決定研究改用 Swarm-A，而不是延續 ISS 原型。

**觀察結果**：TLE 是給 SGP4 使用的平均軌道元素，不是精密軌道觀測；OEM 只是格式名稱，也不保證內容是精密產品。這兩者都不適合作為「地磁暴造成的細微軌道衰減」研究真值。

**結論**：ISS 假資料只適合作為程式練習，不能進正式研究。正式輸入必須換成 ESA Swarm-A reduced-dynamic POD。

**後續動作**：封存並移除 ISS 假資料與相關流程，開始建立 Swarm-A POD 下載、讀取與驗證管線。

### 2026-09-16：取得 Swarm-A POD，建立基本軌道資料管線

**目的**：把 ESA 提供的 Swarm-A precise-orbit product 轉成專案可使用的 state。

**原始輸入**：ESA Swarm-A `SP3ACOM_2_` reduced-dynamic POD ZIP；ZIP 內為 SP3 軌道檔。

**做了什麼**：

1. 實作 Swarm POD 下載器，加入批次下載、續傳與下載後覆蓋檢查。
2. 先下載一天資料，再擴充為多個 POD ZIP 的批次處理。
3. 解析 SP3 epoch、`P` position line、`V` velocity line。
4. 將 SP3 的 GPS time 轉 UTC。
5. 將 position 從 km 轉 m，velocity 從 dm/s 轉 m/s。
6. 統一輸出 orbit state：`{time, frame, position_m, velocity_m_s}`。
7. 建立 GCRF/ITRF 座標轉換，並加入二體重力、J2 與 RK4。

**觀察結果**：

- POD 原始資料約每 10 秒一筆，且直接提供位置與速度。
- SP3 header 的 reference frame 跨越 `IGb14`、`IGS20`、`IGb20`、`IGc20`。早期程式統稱 `ITRF`，但跨時段研究前仍要做 frame inventory。
- 用官方 POD 跑過歷史位置誤差實驗：從 `2025-01-01 00:00:02 UTC` 起，以二體重力、J2、10 秒 RK4 傳播 10 分鐘，與未來官方 POD 比較的 position error 為 29.295 m。

**結論**：POD parser、GPS-to-UTC、座標轉換與基本傳播可用；但位置預報只是後續驗證工具，不是研究主問題。

**後續動作**：停止把「預報誤差」當主產物，改把 POD 當成觀測軌道，研究其半長軸的長期衰減。

### 2026-09-19：統一資料形狀、加入太空天氣與大氣密度準備

**目的**：建立一致的物理資料介面，讓 POD、座標轉換、力模型與 atmosphere 不再各自使用不同資料格式。

**做了什麼**：

1. 將整個軌道流程統一為同一種 state：`{time, frame, position_m, velocity_m_s}`。
2. 確立專案內部一律使用 SI units：m、m/s、m/s^2、kg、kg/m^3；來源單位只在 loader 轉換一次。
3. 建立 CelesTrak `SW-All.csv` downloader 與 reader。
4. 對一筆 state 加入前一日 F10.7、centered F10.7A、trailing F10.7A、7 個 Ap 值與 F10.7 data type。
5. 使用 Astropy 處理 GCRF/ITRF、IERS 資料與地理座標轉換。
6. 建立 NRLMSIS 2.0 density call：ITRF position -> WGS84 longitude/latitude/altitude -> density。
7. 將原先按月份準備的 CSV 流程改成單一 SQLite 資料庫設計。

**觀察結果**：

- NRLMSIS 單點程式檢查：`2025-01-01`、赤道、450 km、F10.7 = 150、F10.7A = 150、Ap = 4，輸出約 `9.58e-13 kg/m^3`。這只驗證程式呼叫與單位，不是研究觀測結果。
- NRLMSIS 的 F10.7 使用前一天觀測，F10.7A 使用當日 centered 81-day average；這個差異後來成為 P1.6 防止 future leakage 的重要問題。
- Swarm DNSAACC density ZIP 可讀取並寫入 SQLite，但尚未和 NRLMSIS 或軌道衰減做比較。

**結論**：資料單位與 state 介面已統一；大氣密度只能先作獨立資料準備，不能在沒有明確研究設計時直接接入 drag force 或 machine learning。

**後續動作**：以 SQLite 保存 raw source records；後續計算必須另寫 derived table，不可覆寫 raw observation。

### 2026-09-21：固定第一階段研究邊界

**目的**：避免程式功能持續擴張，先定義一個可驗證、可重建的最小研究產物。

**做了什麼**：

1. 建立第一階段正式計畫 `plans/phase_1_data_preparation/PLAN.md`。
2. 將研究流程定為：raw files -> raw SQLite -> instantaneous semi-major axis -> quality/interval -> 10-minute orbit data -> feature alignment -> release。
3. 明確排除 machine learning、atmospheric drag propagator 與 XYZ 預報主線。
4. 規定 raw SQLite table 是不可變來源紀錄；任何計算結果必須寫獨立 derived table，使用同一個 `time_us` 追溯。

**觀察結果**：若同時做 density comparison、drag model、預報、ML 與資料整理，會無法判斷任何錯誤到底來自資料品質、物理模型或統計模型。

**結論**：目前唯一可交付目標是「可重建的 10 分鐘分析資料集」，不是預報模型。

**後續動作**：將舊 CSV 產物與一次性驗證程式逐步移出主流程，集中實作 SQLite raw/derived pipeline。

### 2026-09-27：清理資料流程，驗證 P1.5 不能直接平滑

**目的**：減少重複程式與過期流程，並測試能否直接從每 10 秒半長軸得到衰減率。

**做了什麼**：

1. 簡化資料準備程式，移除舊的月 CSV 產物與不再使用的 API。
2. 保留 raw SQLite、P1.3 orbital-element table 與後續 derived table 的分層。
3. 對第一個可用 POD interval 的 instantaneous semi-major axis 試跑自然 cubic B-spline。
4. 量測相鄰 10 秒半長軸差、spline derivative 與合理物理尺度。

**觀察結果**：

| 量測 | 結果 |
| --- | ---: |
| interval 內半長軸範圍 | 6,791,545.8 至 6,811,052.0 m |
| 相鄰 10 秒半長軸差標準差 | 153.9 m |
| GCV cubic spline 在第一個 10 分鐘點的 derivative | -7.97 m/s |

`-7.97 m/s` 等於每天數十萬公尺下降，物理上不可能是 Swarm-A 的 atmospheric drag。

**結論**：瞬時 osculating semi-major axis 含有強烈 short-period variation。不可直接做 spline 後把 derivative 稱為 orbital decay。P1.5 必須先選擇 orbit-average 或明確、經 synthetic validation 的短週期處理方法。

**後續動作**：暫停 P1.5 正式資料表；先完成可獨立驗證的 P1.4 品質控制、P1.6 時間規則與資料來源盤點。

### 2026-09-28：建立 P1.4 至 P1.7 執行計畫與 P1.4-A/B

**目的**：把後續工作拆成不互相覆寫資料、可平行準備且有明確停止條件的工作包。

**做了什麼**：

1. 建立 `P1.4_TO_P1.7_EXECUTION_PLAN.md`，區分 P1.4-C/D、P1.5-A 至 D、P1.6-A/B、P1.7。
2. 由 raw `swarm_a_states` 與 P1.3 `swarm_a_orbital_elements` 重建 `swarm_a_pod_quality`。
3. P1.4-A 實作不需猜測門檻的檢查：時間遞增、position/velocity finite、P1.3 result 存在、軌道能量與半長軸合理。
4. P1.4-B 量測 native cadence，遇到 source-file boundary、前一列不可用或同 source 的 time gap 時切開 `interval_id`。
5. 將 P1.3、P1.4 與 raw table 的資料責任分開，quality rebuild 不修改 raw POD。

**觀察結果**：

| 項目 | 結果 |
| --- | ---: |
| raw POD / P1.3 / P1.4-A rows | 14,558,400 |
| `is_usable = 1` | 14,558,400 |
| P1.4-A Q1/Q5 rejected rows | 0 |
| native cadence | 10 s |
| continuous intervals | 1,685 |
| 每個 interval POD rows | 8,640 |
| interval 內 time gaps | 0 |

**結論**：目前每個 interval 剛好對應一份 POD source file。這只代表 Q1/Q5 與 gap 已通過；P1.4 尚未完成，因為 Q3 ESA quality flag 與 Q4 maneuver candidate 還沒有可辯護的校準。

**後續動作**：P1.4-C 要盤點真實 SP3 frame label 與逐筆官方 quality information；P1.4-D 要用正常 interval 的 position/velocity residual 校準 maneuver threshold，不能拿衰減率大小當判定規則。

### 2026-09-28：下載完整 SYM-H / AE，並修正資料完整性檢查

**目的**：讓地磁資料完整覆蓋本機 POD 時段，且避免下載器把被來源截斷的檔案當成完整資料。

**原始輸入**：WDC Kyoto HAPI `min_asysym` 的 SYM-H 與 `min_ae` 的 AE minute data。

**做了什麼**：

1. 下載並匯入 `2021-01-01` 至 `2026-08-12` 的 SYM-H / AE。
2. 發現 WDC 的 2025 SYM-H 年度 request 在 `2025-10-18 10:40` 提早停止，雖然下載表面成功。
3. 補下載 `2025-10-18` 至 `2025-12-31` 的較短範圍，重新匯入 raw SQLite。
4. 修改 `down_geomagnetic.py`：單次 request 最多 180 天，並讀取 CSV 最後一筆 observation 檢查是否到達 requested end date。
5. 將 SYM-H 與 AE 寫入同一張 `geomagnetic` table：同一 `time_us` 共享一列，但保留各自 value 與 version。

**觀察結果**：

| 項目 | 結果 |
| --- | ---: |
| SYM-H rows | 2,952,000 |
| AE rows | 2,952,000 |
| UTC coverage | 2021-01-01 00:00 至 2026-08-12 23:59 |
| SYM-H 最大相鄰 gap | 60 s |
| 大於 2 分鐘 gap | 0 |

**結論**：raw geomagnetic data 已完整覆蓋目前 POD。未來不得再使用年度 WDC request；需要分成不超過 180 天的區段，並由程式驗證末筆資料。

**後續動作**：用這份 raw coverage 寫 P1.6-A 的 source-time 對齊規則；AE 保留但不自行加入正式 feature。

### 2026-09-28：完成 P1.6-A，定義 feature 時間規則

**目的**：在寫任何 final SQLite join 前，先確定每個 environmental feature 在某個 orbit time 是否能合法使用，避免 future leakage。

**做了什麼**：

1. 建立 `prep_feature_alignment.py`，只放 pure alignment functions，不讀 SQLite、不寫 SQLite。
2. 定義 SYM-H 規則：exact minute 直接使用；僅在左右 source total gap <= 2 分鐘時線性內插；否則缺失。
3. 定義 Ap 規則：使用 target 所屬官方 3-hour block；`02:59:59` 不可提早使用 `03:00` block。
4. 檢查 CelesTrak F10.7A 欄位：既有 centered `F10.7_OBS_CENTER81` 會包含未來日資料。
5. 在 raw `space_weather` 新增並重建 `f107a_last81_sfu`，保存 `F10.7_OBS_LAST81`。
6. 定義 P1.6 使用前一日 F10.7 與前一日 trailing F10.7A，並保存各自 source time。
7. 為 exact/interpolation/gap、future-only SYM-H、Ap boundary、F10.7 source date、trailing F10.7A 建立 unit tests。

**觀察結果**：

- `space_weather` 有 201,861 筆 3-hour rows，範圍覆蓋目前 POD。
- centered F10.7A 適合保留給既有 NRLMSIS state，但不適合 P1.6 的因果分析。
- `F10.7_OBS_LAST81` 是只看當日與過去 80 日的 trailing average，可避免 future leakage。
- 目前 Python test suite 共 34 個測試，全部通過。

**結論**：P1.6-A 已完成。P1.6 不是把所有資料粗暴對到每 10 秒 POD；它只會對 P1.5 最終的 10 分鐘 `time_us` 做 feature alignment，並保留每個 feature 的 source timestamp。

**後續動作**：P1.6-B 等 P1.5 固定 `swarm_a_orbit_10min` 的 `time_us`、半長軸、衰減率與 `interval_id` schema 後才可開始。

### 2026-09-28：依 clean-code 與 KISS 原則整理資料模組

**目的**：讓資料管線可以從檔名看出責任，移除不必要 abstraction，避免後續 P1.5/P1.6 在不清楚的模組中堆疊邏輯。

**做了什麼**：

1. 刪除過度泛化的 geomagnetic selector abstraction，保留明確的 `write_sym_h` 與 `write_ae`。
2. 將資料準備檔名分成三種角色：

```text
prep_raw_*       原始檔寫入 raw SQLite
prep_derived_*   raw table 產生 derived table
prep_feature_alignment.py
                 P1.6 的純時間對齊規則
```

3. 將測試檔改成相同責任名稱，例如 `test_prep_raw_geomagnetic.py` 與 `test_prep_derived_pod_quality.py`。
4. 保留單一 `prep_raw_sqlite.py` 作為 raw data 更新入口；沒有新增 class、config layer 或新資料夾。
5. 重新檢查所有 Python module import、編譯與 unit test。

**觀察結果**：檔案命名不再讓 raw import、derived calculation 與 feature rule 混在 `prep_write_*` / `prep_sqlite_*` 名稱中；34 個測試仍全部通過。

**結論**：目前資料層責任清楚，適合從 P1.4 繼續往 P1.5/P1.6 走。這次只做命名與必要 correctness 修正，不做 class 或通用 framework。

**後續動作**：新程式依既有命名規則加入；不要為可能的未來資料來源先建立 provider interface。

### 2026-09-30：固定 P1.6 final schema 與資料 lineage

**目的**：將 P1.6 的重要定義從聊天整理成可長期參照的文件，避免之後只記得欄位名稱卻不知道每個值從哪裡來。

**做了什麼**：

1. 建立 `P1.6_ANALYSIS_SCHEMA.md`。
2. 定義預計的 `swarm_a_analysis_10min` 欄位：SQLite/Python 型態、單位、`NULL` 規則、中文意義與 source timestamp。
3. 逐一記錄 POD、SYM-H、AE、F10.7、F10.7A、Ap、DNSAACC density 從原始產品到 P1.6 的資料路徑。
4. 記錄 P1.6-B 明確禁止事項：不刪 orbit row、不改 raw table、不跨 source gap 補值、不使用 future F10.7/F10.7A。
5. 在 `P1.6_FEATURE_ALIGNMENT.md` 加上連結，讓時間規則與完整 schema 可互相追溯。

**觀察結果**：P1.6 的欄位與來源資料不再散落於 plan、code 與聊天。最終 table 尚未存在，文件清楚標記為 P1.6-B 的固定介面規格，而非已寫入資料。

**結論**：之後實作 P1.6-B 時，應直接以這份 schema 寫 table 與 tests；若要改欄位、source time 或缺失規則，必須先更新文件與測試，不能在 writer 中默默改意義。

**後續動作**：回到 P1.4-C/D 與 P1.5-A。P1.6-B 仍等待 P1.5 的最終 10 分鐘 orbit output。

## 下一個實驗應做什麼

不要直接開始 P1.5-B/C/D。先從下列可驗證工作選一項：

1. **P1.4-C**：inventory 所有 SP3 source 的真實 frame label，確認是否能安全跨 frame transition。
2. **P1.4-D**：從正常 interval 的 position/velocity residual 校準 maneuver candidate 規則，先以 synthetic jump 驗證。
3. **P1.5-A**：建立 synthetic linear-decay input，測試候選 orbit-average / short-period 方法能否回收已知 slope。

P1.4-C、P1.4-D、P1.5-A 可分開準備；但 P1.5 正式資料表與 P1.6-B 都必須等方法與 schema 決定。

## 必讀文件

- `plans/phase_1_data_preparation/PLAN.md`：第一階段唯一正式規格。
- `plans/phase_1_data_preparation/P1.4_TO_P1.7_EXECUTION_PLAN.md`：依賴、可平行工作與 release gate。
- `plans/phase_1_data_preparation/P1.4_QUALITY_CONTROL.md`：P1.4 實作與結果。
- `plans/phase_1_data_preparation/P1.5_RESAMPLE_AND_DECAY.md`：P1.5 試跑失敗的原因與停止條件。
- `plans/phase_1_data_preparation/P1.6_ANALYSIS_SCHEMA.md`：P1.6 final schema 與資料來源追溯。
- `plans/phase_1_data_preparation/archive/RESEARCH_PLAN.md`：外部提案快照，不是現行規格。

## Git 狀態

- Git repository 建於 2026-09-15。
- 遠端：`https://github.com/anbychang/science_project.git`。
- `master` 是目前工作分支。
- 每完成一個可驗證工作包，先更新本日誌與相關規格，再建立一筆清楚的 commit。
