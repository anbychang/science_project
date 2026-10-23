# Swarm-A 軌道衰減研究時間紀錄

最後更新：2026-10-22

> 2026-10-18 的 10 分鐘 Phase 1 工作稽核與後續逐 10 秒相位候選，是兩條不同資料產品。舊紀錄提到的 `data/swarm_a_analysis.sqlite` 目前不在工作區；現存三年與 2014–2026 候選工作庫位於 `data/sqlite/`，尚非已校準的正式 decay release。

Current status：三年與 2014–2026 工作庫均已完成逐 10 秒的 raw B-L／joint H2/H3 3／5 圈候選、共用 P1.6 v2 feature，以及 P1.7 v2 audit。兩份 audit 各有 6 項、violation 全為 0，metadata status 均為 `pass`。12 年 v2 兩張 rate table 各有 38,378,878 筆；十二年報告限定 2014-07-01 至 2026-06-30。舊 10 分鐘產品的歷史交付與限制見 `plans/phase_1_data_preparation/PHASE_1_FINAL_REPORT.md`。

## 2026-10-22：Phase 1 現行資料與文件核對

**證據**：12 年 checkpoint 有 4,554 `source_files`，`swarm_a_states` 與 `swarm_a_pod_quality` 各 39,346,560 rows，`swarm_a_mean_orbit_elements_v1` 有 39,346,558 rows。差額是 2013-12-31 23:59:44／23:59:54 UTC 兩個範圍外的可用 state；quality 的 38,378,880 個可用點扣除這兩筆，正好是 38,378,878 個 v2 source keys。三年 checkpoint 保留同一全期 raw states，mean-element table 有 9,469,438 rows。三年 v2 feature table 有 9,469,438 rows。兩份 working copy 的 P1.7 v2 audit 各 6 rows，violation 全 0，metadata status 均為 `pass`。

**決定**：README、lineage 與執行計畫以現存 SQLite 和 v2 writer 為準；10 分鐘和 v1 long-candidate 文件保留為歷史，不再稱為現行輸出。audit pass 不代表 maneuver、source、method anomaly 已校準。

## 2026-10-21：P1.5.6 12 年 phase-harmonic decay batch

**輸出完成**：`data/sqlite/swarm_a_analysis_2014_2026_phase_candidate_working_v2.sqlite`，31.01 GB。
`swarm_a_phase_harmonic_decay_raw_b_l_sets_v2` 與
`swarm_a_phase_harmonic_decay_joint_h2_h3_sets_v2` 各為 38,378,878 筆。

**方法**：每個 usable 10-second epoch 向前取 3 或 5 個完整 unwrapped
`u = omega + M` orbit window；phase boundary 直接插值。raw table 對 `a(t)` 作 OLS；
joint table 以同一 window 聯合擬合 linear trend 與 `H2(u) + H3(u)`。

**待辦**：完整 `time_us` key-set、rate validity parity 及 table-specific
`integrity_check` 尚待補跑；先前全表掃描超過 interactive tool 的 120-second limit，不能記為 pass。

這份檔案只記錄時間順序：某一天做了什麼、量到什麼、得到什麼結論。它不放長期規則或完整技術定義；那些放在 `plans/phase_1_data_preparation/PLAN.md` 與各階段規格。

## 日期可信度

- 研究在 2026-09-15 之前已開始。
- 2026-09-15 是目前 Git repository 的最早紀錄日，不是研究開始日。
- 9 月 15 日以前的精確操作日期沒有可靠的版本紀錄，因此不補造日期；之後若找到原始筆記，再補入正確日期。

## 2026-09-15：Git 開始記錄既有原型

**做了什麼**：將既有的 ISS/TLE 軌道原型放入 Git，建立私有 GitHub repository，並盤點原型使用的資料。

**量到或確認的事**：TLE 是為 SGP4 設計的平均軌道元素；OEM 只代表檔案格式，不能保證是精密軌道觀測。兩者都不足以當成研究微小 orbital decay 的真值。

**結論**：ISS 與 synthetic data 只能保留為程式練習歷史。正式研究必須採用 ESA Swarm-A reduced-dynamic POD。

## 2026-09-16：建立 Swarm-A POD 取得與讀取流程

**目的**：把 ESA Swarm-A precise-orbit product 轉成專案統一的 orbit state。

**做了什麼**：

1. 建立 POD downloader，加入批次下載、續傳與下載後覆蓋檢查。
2. 解析 POD ZIP 內的 SP3：epoch、`P` position 與 `V` velocity line。
3. GPS time 轉 UTC；position 從 km 轉 m；velocity 從 dm/s 轉 m/s。
4. 統一 orbit state 為 `{time, frame, position_m, velocity_m_s}`。
5. 建立 GCRF/ITRF 轉換、二體重力、J2 與 RK4。

**量到或確認的事**：

- POD 約每 10 秒一筆，直接提供位置與速度。
- SP3 header 的 frame 跨越 `IGb14`、`IGS20`、`IGb20`、`IGc20`，不能永久只稱作 `ITRF`。
- 歷史位置預報檢查：從 `2025-01-01 00:00:02 UTC` 起，以二體重力、J2、10 秒 RK4 傳播 10 分鐘，對官方 POD 的 position error 為 29.295 m。

**結論**：POD parser、時間轉換與基本 propagation 可用。但位置預報改列為後續驗證工具，不是主研究問題。

## 2026-09-19：統一 state、太空天氣、大氣密度與 SQLite

**目的**：讓資料與物理計算使用同一個 state shape，並把來源資料改成可重建的本機資料庫。

**做了什麼**：

1. 將 loader、座標轉換、force、RK4 統一為同一種 state。
2. 固定內部使用 SI units；來源單位只在 loader 轉一次。
3. 加入 CelesTrak `SW-All.csv` 下載與讀取，對 state 加入 F10.7、F10.7A、Ap 與資料類型。
4. 以 Astropy 處理 GCRF/ITRF、IERS 與地理座標。
5. 建立 NRLMSIS 2.0：ITRF position -> WGS84 longitude/latitude/altitude -> `density_kg_m3`。
6. 由月 CSV 流程改為單一 `data/old/swarm_a_data.sqlite`。

**量到或確認的事**：

- NRLMSIS 單點程式檢查：`2025-01-01`、赤道、450 km、F10.7 = 150、F10.7A = 150、Ap = 4，輸出約 `9.58e-13 kg/m^3`。這只驗證程式與單位。
- NRLMSIS 的 F10.7 使用前一天觀測；F10.7A 使用 centered 81-day average。這個差異之後成為 P1.6 防 future leakage 的關鍵。
- Swarm DNSAACC density 可讀取與匯入 SQLite，但尚未與 NRLMSIS 或 orbital decay 比較。

**結論**：density 先作獨立資料準備，不接進 drag propagator，也不建立 ML target。

## 2026-09-21：固定第一階段研究範圍

**做了什麼**：建立 `plans/phase_1_data_preparation/PLAN.md`，將正式流程定為：

```text
raw files
-> raw SQLite
-> instantaneous semi-major axis
-> quality / interval
-> 10-minute orbit data
-> feature alignment
-> release
```

**量到或確認的事**：同時做 density comparison、drag propagator、預報與 ML，無法判斷錯誤是資料、物理還是模型造成。

**結論**：第一階段唯一交付物是可重建的 10 分鐘分析資料集。raw table 永遠保持來源紀錄；新計算一律寫獨立 derived table。

## 2026-09-27：測試直接平滑瞬時半長軸

**目的**：檢驗能否直接從每 10 秒 osculating semi-major axis 得到 orbital decay。

**做了什麼**：對第一個可用 POD interval 的 instantaneous semi-major axis 試跑 natural cubic B-spline，量測 10 秒差分與 spline derivative。

**量到或確認的事**：

| 量測 | 結果 |
| --- | ---: |
| interval 內半長軸範圍 | 6,791,545.8 至 6,811,052.0 m |
| 相鄰 10 秒半長軸差標準差 | 153.9 m |
| GCV cubic spline 的 derivative | -7.97 m/s |

`-7.97 m/s` 換算後是每天數十萬公尺下降，不可能是 Swarm-A 的大氣阻力。

**結論**：osculating semi-major axis 含強烈 short-period variation。P1.5 不可直接 spline 後發布衰減率；必須先選 orbit-average 或可驗證的 short-period treatment。

## 2026-09-28：建立 P1.4 至 P1.7 工作拆分，完成 P1.4-A/B

**做了什麼**：

1. 建立 `P1.4_TO_P1.7_EXECUTION_PLAN.md`，分開 P1.4-C/D、P1.5-A 至 D、P1.6-A/B、P1.7。
2. 從 raw POD 與 P1.3 orbital element 重建 `swarm_a_pod_quality`。
3. P1.4-A 檢查時間遞增、state finite、P1.3 result、軌道能量與半長軸合理性。
4. P1.4-B 量測 native cadence，並在 source boundary、前一列失敗或同 source time gap 時切開 `interval_id`。

**量到或確認的事**：

| 項目 | 結果 |
| --- | ---: |
| raw POD / P1.3 / P1.4-A rows | 14,558,400 |
| `is_usable = 1` | 14,558,400 |
| P1.4-A Q1/Q5 rejected rows | 0 |
| native cadence | 10 s |
| continuous intervals | 1,685 |
| 每個 interval POD rows | 8,640 |
| interval 內 time gaps | 0 |

**結論**：目前一個 interval 對應一份 POD source file。P1.4 尚未完成，因為 Q3 official quality information 與 Q4 maneuver rule 未校準。

## 2026-09-28：補齊 SYM-H / AE，修正 WDC 下載截斷

**目的**：使 geomagnetic data 覆蓋全部本機 POD 時段，並驗證下載結果真的完整。

**做了什麼**：

1. 下載並匯入 `2021-01-01` 至 `2026-08-12` 的 WDC Kyoto SYM-H 與 AE minute data。
2. 發現 2025 SYM-H 年度 request 在 `2025-10-18 10:40` 提早停止。
3. 以短日期範圍補下載並重新匯入。
4. 將 downloader 限制為每次最多 180 天，並檢查 CSV 末筆 observation 是否到達 requested end date。

**量到或確認的事**：

| 項目 | 結果 |
| --- | ---: |
| SYM-H rows | 2,952,000 |
| AE rows | 2,952,000 |
| UTC coverage | 2021-01-01 00:00 至 2026-08-12 23:59 |
| SYM-H 最大相鄰 gap | 60 s |
| 大於 2 分鐘 gap | 0 |

**結論**：geomagnetic raw source 完整覆蓋本機 POD。未來下載必須分成不超過 180 天，不能用年度 request。

## 2026-09-28：完成 P1.6-A feature 時間規則

**目的**：在寫 final join 前，先定義任何 environmental feature 是否可在某個 orbit time 合法使用。

**做了什麼**：

1. 建立純函式 `prep_feature_alignment.py`，不讀也不寫 SQLite。
2. SYM-H：exact minute 直接使用；只有左右 source total gap <= 2 分鐘時才線性內插。
3. Ap：使用 target 所屬 official 3-hour block；明確測試 `02:59:59` / `03:00:00` boundary。
4. 新增 raw `f107a_last81_sfu`，保存 `F10.7_OBS_LAST81`。
5. F10.7 與 F10.7A 都使用前一日 source time；P1.6 F10.7A 不可使用 centered `F10.7_OBS_CENTER81`。
6. 建立 exact/interpolation/gap、future-only SYM-H、Ap boundary、F10.7 source time 的 unit tests。

**量到或確認的事**：`space_weather` 有 201,861 個 3-hour rows，覆蓋本機 POD；Python test suite 共 34 個測試，全部通過。

**結論**：P1.6-A 完成。P1.6 只對 P1.5 最終的 10 分鐘 `time_us` 做 alignment，不對每 10 秒 POD 建立替代資料集。

## 2026-09-28：整理資料模組責任

**做了什麼**：

1. 移除過度泛化的 geomagnetic selector abstraction。
2. 重新命名資料準備模組：

```text
prep_raw_*       原始檔寫入 raw SQLite
prep_derived_*   raw table 產生 derived table
prep_feature_alignment.py
                 P1.6 純時間對齊規則
```

3. 同步重新命名測試與文件引用。
4. 重新檢查 import、編譯與全部 unit tests。

**量到或確認的事**：raw import、derived calculation 與 feature rule 不再混在 `prep_write_*` / `prep_sqlite_*` 名稱中；34 個測試仍全過。

**結論**：保持小型直接模組，不新增 class、config layer 或 provider interface。

## 2026-09-30：固定 P1.6 schema 與資料來源追溯

**做了什麼**：

1. 建立 `P1.6_ANALYSIS_SCHEMA.md`。
2. 定義預計 `swarm_a_analysis_10min` 的欄位型態、單位、`NULL` 規則、中文意義與 source timestamps。
3. 記錄 POD、SYM-H、AE、F10.7、F10.7A、Ap、DNSAACC density 從原始產品到 P1.6 的資料路徑。
4. 記錄 P1.6-B 禁止事項：不刪 orbit row、不改 raw table、不跨 source gap 補值、不使用 future weather value。

**量到或確認的事**：最終 `swarm_a_analysis_10min` 尚未存在；文件明確標示為 P1.6-B 的固定介面規格，不是假裝已產生的資料。

**結論**：P1.6-B 實作時必須以 schema 文件與現有 pure tests 為準。欄位或時間規則若要改，必須先更新文件與測試。

## 2026-09-30：淘汰 direct raw Savitzky-Golay

**目的**：檢驗能否直接將 Savitzky-Golay 用在每 10 秒 osculating semi-major axis，
再把導數當作 orbital decay。

**做了什麼**：先 read-only audit 第一個真實 interval：半長軸 peak-to-peak 為
`19,506.2 m`，最強 FFT short-period component 約 46.45 分鐘、振幅 `9,535.4 m`。再建立
可重跑的 24 小時 synthetic series：已知 `1 m/day` linear decline，加上這個 representative
component 的 fundamental / harmonic variation，以及固定 seed 的 25 m Gaussian noise。以
279、559、837 samples 和 polynomial order 2、3 測試 6 個 raw-SG candidate；只量測排除
edge window 後的 interior derivative。

**量到或確認的事**：所有 candidate 都遠超過預先設定的 recovery gate。最佳 median result
仍是 `-3,845.5 m/day`，而真值是 `1 m/day`；最小的 95th-percentile absolute error 仍為
`64,417.9 m/day`。相對地，只有 linear trend 的 control input 能正確回收 `1 m/day`。

**結論**：問題不是 derivative 的 unit 或 sign，而是 direct SG 仍會追蹤 km-level
short-period variation。P1.5 不能直接 SG raw osculating series。下一步是定義並驗證
orbit-average 或理論 osculating-to-mean conversion；P1.5-B/C/D 與 P1.6-B 仍不得開始。

## 2026-09-30：驗證條件式 mean-like SG candidate 與 10 分鐘 bin

**結果**：對 mean-like 10 分鐘 synthetic series，73-sample（12 小時）order-2 centered
Savitzky-Golay 的 median decay 是 `0.9462 m/day`，95th-percentile pointwise error 是
`0.1812 m/day`；different-seed held-out error 是 `0.1527 m/day`，均通過 gate。UTC bin helper
會拒絕 cross-bin、cross-interval、non-increasing input，並保留 count、首尾 source time、max gap。

**證據**：開頭 3 個與最後 1 個真實 interval 的 read-only audit 都量到約 19.5 km
peak-to-peak 與 46.452 分鐘 dominant short-period component，支持 direct raw-SG rejection
不是單一檔案的偶然結果。

**未解決**：真實 orbit-average / mean-element conversion 能否把輸入轉成這個 SG candidate
要求的 mean-like series。這仍是 P1.5-B 前的 gate，不建立正式 table。

## 2026-09-30：淘汰 simple rectangular orbit-average

**結果**：用第一個 interval 的 5,582.02 s Kepler period，測試 1 至 12 個 orbit 的
rectangular rolling average。raw peak-to-peak 從 `19,506.2 m` 降到約 `66.6 m`，但 residual
std 仍是 `12.131` 至 `13.245 m`；1-orbit linear slope 是 `20.306 m/day`。

**決定**：simple orbit-average 不符合 SG candidate 的 mean-like input contract，淘汰。
Brouwer-Lyddane conversion 是下一個合理選項，但本機沒有 Java、Orekit 或 Python bridge；
不自行重寫理論公式。

## 2026-10-01：釐清 data module 命名與入口

**結果**：

- `prep_raw_common.py` 改為 `prep_raw_identifiers.py`：只負責 raw record 的 `time_us` 與 source signature。
- `prep_raw_sqlite.py` 改為 `prep_raw_database.py`：明確表示它建立並更新 local SQLite database。
- 純時間規則 `prep_feature_alignment.py` 改為 `calc_feature_alignment.py`。
- `prep_orbit_bins.py` 改為 `prep_orbit_bin_summary.py`。

**證據**：更新所有 current import、test、執行指令與規格引用後，Python test suite 全過。

**決定**：保留 `prep_raw_*` 與 `prep_derived_*`，因為它們確實建立 prepared data；不為了少檔案合併 download、load、raw write、derived write 四個責任層。

## 2026-10-01：移除尚未啟動階段的預先實作

**結果**：刪除 P1.5/P1.6 的 standalone bin/alignment helper、專屬測試與已淘汰 raw-SG verifier；刪除未接入現行研究流程的 atmosphere、RK4 propagation 與 position-error code。

**證據**：這些 module 沒有現行 production caller；raw SQLite -> P1.3 -> P1.4 pipeline 不引用它們。

**決定**：保留 P1.5/P1.6 文件中的規則、輸入條件與量測結果。相應 phase 開始時才寫最小 implementation 與 test。

## 2026-10-14：拆分 Phase 1 data lineage 文件

**結果**：將原本單一 data-lineage 文件拆成 POD、space weather、geomagnetic、density 四份。每份固定記錄 `資料`、`程式`、`動作`、`輸出`、`Shape`、`例`；資料 shape 用多行 `{}` 與 `[]`，不把巢狀欄位塞成長句。

**證據**：POD lineage 追到 `swarm_a_pod_quality`；space-weather lineage 追到 `space_weather`；geomagnetic lineage 追到 `geomagnetic`；density lineage 追到 `swarm_a_density`。P1.5/P1.6 都標為未建立。2026-10-18 已集中至 `data_lineage/`，作為獨立 target 與實際資料產品記錄。

**決定**：資料血緣是程式與資料表之間的追溯文件，不是研究計畫替代品。新增來源或改變 writer 時，必須同步更新對應 lineage 文件與本格式規則。

## 2026-10-14：raw data integrity 與 POD 時間邊界 code review

**結果**：以三輪 review / red-green 修正檢查資料準備主線。space-weather CSV 若在完整日期之間缺少 `AP1`，或 `AP1..AP8` 任一欄缺失或非數字，現在會在寫入前失敗；不留下不完整 raw rows 或 provenance。最後完整日期之後的空白列仍可略過。weather preparation version 升為 `3`，舊 SQLite database 必須重建。

**結果**：POD SP3 epoch 的秒數若四捨五入進位，例如 `59.9999996`，現在會正規化到下一秒，而不是建立無效的 `microsecond=1000000`。

**證據**：新增 weather malformed/interior-gap/trailing-gap regression tests，以及 SP3 fractional-second carry test。完整 `python -m unittest discover -s tests -v`：34 tests passed；`git diff --check` 無 whitespace error。

**決定**：raw source 的 complete coverage 必須先驗證，才允許寫入 metadata。只在確定的資料完整性與時間解析邊界補最小修正，不重構尚未進入主線的 module。

## 2026-10-17：P1.5-A 選定並驗證 Brouwer-Lyddane mean orbit

**目的**：將 POD 的 osculating state 轉成可分析長期變化的 mean orbit；不把 raw
`semi_major_axis_m` 的短週期項誤當 orbital decay。

**做了什麼**：

1. 建立 `calc_mean_orbit.py`：GCRF `{UTC, position_m, velocity_m_s}` 經 Orekit
   `CartesianOrbit` 與 `BrouwerLyddanePropagator.computeMeanOrbit()` 產生 mean semi-major axis。
2. 使用 repository 內 `.orekitvenv` 的 `orekit-jpype 13.1.8.0`、內建 `jdk4py` Java runtime
   與 `orekit-data`；不需要系統 Java。
3. 建立 `prep_derived_mean_orbit.py`，輸出獨立
   `swarm_a_mean_orbital_elements {time_us, mean_semi_major_axis_m, rejection_reason}`；不修改 raw
   POD、P1.3 或 P1.4 table。
4. 新增 fixed synthetic regression、ITRF frame guard、SQLite two-row integration test。
5. read-only 驗證 interval `1`、`843`、`1,685`，每段都是 `8,640` 個 usable 10-second POD rows。

**量到或確認的事**：

| interval | raw 46.452-minute amplitude m | mean amplitude m | reduction |
| ---: | ---: | ---: | ---: |
| 1 | 9,535.35 | 52.65 | 99.45% |
| 843 | 7,395.07 | 48.89 | 99.34% |
| 1,685 | 9,675.05 | 64.54 | 99.33% |

完整 test suite：`37 tests passed`。Brouwer-Lyddane 只用 J2--J5 gravity terms，`M2 = 0.0`；
它不是 drag model，也沒有產生 `decay_rate`。

**結論**：P1.5-A 的 short-period method gate 通過。P1.4-C frame audit 與 P1.4-D maneuver
calibration 尚未完成，因此不重建全庫、不建立 10-minute table、不進入 smoothing、derivative 或
P1.6 final join。

## 2026-10-17：P1.4-C SP3 provenance 與 Q3 policy

**原始輸入**：1,685 個 `data/swarm_a_pod/*.ZIP`、`source_files`、
`swarm_a_orbital_elements`、`swarm_a_pod_quality`。

**實際操作**：逐 ZIP 讀取 SP3 header，將固定 metadata 寫入每個 source 的
`source_files {sp3_frame_label, coverage_start_time_us, coverage_end_time_us,
epoch_count, cadence_s, time_system}`。新增 transition report，對每個 frame boundary
前後各三個 source 的 usable semi-major axis 做 read-only median 比較。

**量測結果**：四個 frame group 是 `IGb14: 331`、`IGS20: 798`、`IGb20: 343`、
`IGc20: 213`；所有 source 都是 `{epoch_count: 8640, cadence_s: 10.0, time_system: GPS}`。
transition median difference 分別是 `-72.242 m`、`-164.760 m`、`-196.648 m`。這些值混有
真實軌道演化，不是 frame offset，沒有修正。

**Q3 結論**：ESA `SP3xCOM_2_` 的 quality indicator 是獨立 `SP3xVAL_2_`。目前本機
SP3xCOM ZIP 沒有已驗證可用的 official per-epoch quality；policy 是
`quality_source: unavailable`，只能使用 finite / bound / cadence / gap。證據在
`plans/phase_1_data_preparation/RESEARCH_P1.4_C_SP3_QUALITY.md`。

**下一步**：P1.4-D 以 position/velocity residual 建立 maneuver candidate 分布與
synthetic jump test；不得因本次 median comparison 直接套用 frame offset。

## 2026-10-17：P1.4-D maneuver residual audit

**原始輸入**：固定十個 source 的 usable POD state；每個 residual 使用同 source、同 frame、
連續 10 秒的三點 window。

**實際操作**：新增 pure `centered_residuals()` 與 read-only audit command。synthetic
position jump、velocity jump、source/frame/gap boundary 都有測試。

**量測結果**：86,380 個 valid window；curvature median/MAD 是
`427.103403 / 2.588821 m`，velocity residual median/MAD 是
`0.160260 / 0.001692 m/s`。sample 沒有異常 tail。

**結論**：計算工具已驗證，但尚無可辯護的 Q4 rejection threshold。維持現有 quality table，
不把 `median + 10 * MAD` 誤寫成正式 maneuver rule。

## 2026-10-17：Phase 1 chunk 與 10-minute bin contract

**決定**：final analysis 不再把每日 ZIP / `source_id` 當作自動 boundary。同一 product
stream 可跨 ZIP；只要 product stream、SP3 frame、cadence、時間連續性有改變或不確定，
就關閉舊 chunk、建立新 `chunk_id`。多切可以接受；少切不可以。不保存 `chunk_reason`。

**決定**：10-minute bin 的完整預期是 60 筆 POD；`pod_count >= 56` 可以輸出，
`pod_count <= 55` 排除。gap 兩側屬於不同 chunk，不能湊成同一 bin；56--59 筆只可能
出現在 chunk 邊緣。

**影響**：mean orbit、bin、smoothing、derivative 都不可跨 `chunk_id`。原本以每日
source boundary 推導的 240,955 row 上限作廢，待 final chunk rebuild 後重新量測。

## 2026-10-17：P1.4 final chunk rebuild

**結果**：`swarm_a_pod_quality` 已由 provisional `interval_id` 重建為 final `chunk_id`。
14,558,400 raw POD 都有 quality row，全部 usable，final chunk count 是 4。

```text
chunk 1: 2,859,840 rows
chunk 2: 6,894,720 rows
chunk 3: 2,963,520 rows
chunk 4: 1,840,320 rows
```

**決定落實**：同 stream 跨日 ZIP 不再切開；frame/product-stream/cadence/gap 改變或
metadata 不明才切新 chunk。raw table 未改動。

## 2026-10-17：P1.5 full mean-orbit batch resumed

**實際操作**：從既有 2,021,760 row checkpoint 繼續計算 `swarm_a_mean_orbital_elements`。
這一次性的 full-batch runner 使用 3 個 Orekit calculator process 與 1 個 SQLite writer；
worker 不寫 SQLite。完成後刪除平行 runner code，恢復單線 source-by-source writer。

**下一步**：完整 mean table 的 count、UTC coverage、missing 與 rejection 驗證通過後，才建立
不跨 `chunk_id` 的 `swarm_a_orbit_10min`。之後才可做 P1.6 join 與 P1.7 release。

## 2026-10-17：Phase 1 release

**輸出**：`swarm_a_mean_orbital_elements` 14,558,400 rows；
`swarm_a_orbit_10min` 242,640 rows；`swarm_a_orbit_decay_10min` 與
`swarm_a_analysis_10min` 各 242,352 rows。

**規則**：4 個 `chunk_id`；10-minute `pod_count` 58--60、最大 gap 10 s；每個 chunk
以 73-sample Savitzky-Golay 產生中心 decay rows，前後各排除 36 rows。P1.6 僅使用
causal weather / geomagnetic source time；density 不進 core analysis table。

**驗證**：`integrity_check = ok`；foreign-key violations 0；analysis/decay key 與 chunk
完全一致；feature flags 全為 `ok`；future source reference 0。P1.7 manifest、raw signature
aggregate、coverage、Git revision、row counts、missingness 與 rebuild commands 已寫入
SQLite `metadata`。

**限制**：這是 current-database audit。weather preparation v2/v3 修正後，尚未從 raw files fresh rebuild 並重跑完整 audit；不可將本次結果宣稱為 full fresh rebuild。

## 2026-10-18：補齊 Swarm-A 官方 orbit event 排除

**發現**：原本三段 orbit-raise campaign 不足以涵蓋所有有官方證據、會污染 Swarm-A
12-hour semi-major-axis difference 的操作日。官方文件確認兩個漏項：

| event | UTC exclusion | 證據 | 對舊輸出的影響 |
| --- | --- | --- | --- |
| `SWA_ORBIT_CONTROL_2022-01-13` | `[2022-01-13, 2022-01-14)` | ESA-prepared CGMS report | 舊版 campaign 外最大上升：`2022-01-14T00:00:00Z` 的 12-hour `delta_a = +273.788 m`，輸出為 `-547.576 m/day`。 |
| `SWA_CAM_2023-01-06` | `[2023-01-06, 2023-01-07)` | ESA-prepared CGMS report | 沒有同級數值上升，但屬已確認 Swarm-A maneuver，不能留在自然衰減樣本。 |

**做了什麼**：

1. 對既有 2022、2023、2026 campaign 加上上述兩個單日 event，建立
   `OFFICIAL_SWARM_A_ORBIT_EVENTS {id, kind, start, stop}`。
2. P1.4 依 event kind 標記 `planned_orbit_raise_campaign`、
   `official_orbit_control_manoeuvre` 或 `official_collision_avoidance_manoeuvre`，並切開
   chunk。
3. 完成官方 catalog 稽核；沒有找到 2024--2025 或 `2026-08-13` 前另一段可精確指向
   Swarm-A 的公開 raise/CAM 日期。
4. 將所有官方 event 與已檢查觀測時段記入
   `plans/phase_1_data_preparation/ORBIT_RAISE_CAMPAIGN_MEMORY.md`；詳細證據在
   `plans/phase_1_data_preparation/RESEARCH_SWARM_A_ORBIT_RAISE_CATALOG_AUDIT.md`。

**流程決定**：Brouwer-Lyddane mean orbit 僅依 P1.3 valid state 計算，執行順序改為
`P1.3 -> P1.5 mean orbit -> P1.4 quality -> 10-minute -> backward 12h`。P1.4 只決定哪些
既有 mean row 可進下游。新增官方 event 時，從 P1.4 往下重建即可，不再重算 Orekit
mean orbit。

**結果**：現行 `data/swarm_a_phase1_rebuild_v3.sqlite` 從 P1.4 往下重建完成。P1.4 有
`13,495,680` usable rows、`1,045,440` campaign rows、兩種單日 maneuver 各 `8,640` rows，
final chunk count 為 `9`。P1.5/P1.6 各輸出 `224,280` decay / analysis rows；所有 official
event 的 final analysis row count 為 `0`。先前 `>700 m/day` 的 campaign uplift 已不在 final
output；最大剩餘正半長軸變化是 `2022-10-10T14:20:00Z` 的 `522.574 m/day`，沒有對應的
官方 Swarm-A event 證據，維持 audit-only。

**驗證**：P1.7 audit pass，SQLite integrity 與 foreign key 均為 0 failure；analysis/decay
key、chunk、time continuity、feature source time 與 missingness 全部通過。

**狀態**：舊 `data/swarm_a_phase1_rebuild.sqlite` 已被 supersede，不可作正式交付。先前
v2 與全量 v3 均在發現流程可縮短後停止並移除。現行 v3 是從既有 raw/P1.3/mean 資料複製後
做 P1.4--P1.7 partial rebuild，因此狀態為 `working_audit_pass`；它沒有偽稱為完整
fresh rebuild。

## 2026-10-18：自然符號 rate 與編號 pipeline

**決定**：不再輸出反號的 `decay_rate_12h_backward_m_day`。正式欄位改為
`da_dt_12h_backward_m_day = da_dt_12h_backward_m_s * 86400`；負值代表半長軸下降，與
`da_dt_12h_backward_m_s` 及外部文獻的自然符號一致。

**做了什麼**：

1. 更新 signed-rate table、analysis table、release audit、schema 文件與測試；舊欄位不再存在。
2. POD processing module 改為 `prep_01` 至 `prep_07`，analysis 與 release audit 為
   `prep_08`、`prep_09`；順序寫入 `plans/phase_1_data_preparation/POD_PIPELINE.md`。
3. 從 v3 複製建立 `data/swarm_a_phase1_rebuild_v4.sqlite`，只重建 rate、analysis、audit；
   mean orbit 沒有重算，v3 保留。

**結果**：v4 有 `224,280` analysis rows。首列舊 `+146.856 m/day` 改為
`-146.856 m/day`；末列舊 `-225.052 m/day` 改為 `+225.052 m/day`。所有數值絕對值、時間、
chunk 與 feature 都保持不變。

**驗證**：完整 test suite `95` tests 通過；新的 synthetic decline test 確認
`-1.2 m/day` 下降輸出 `-1.2 m/day`；v4 schema 沒有舊欄位，且 status 是
`working_audit_pass`。

## 2026-10-18：P1.7 manifest 最終 refresh

**結果**：對當時的 `data/swarm_a_analysis.sqlite` 重跑 P1.7 audit metadata。沒有重算
10-minute orbit、3/6/12h rate 或 analysis。

**驗證**：`audit_outcome = pass`、`release_status = working_audit_pass`、
SQLite integrity 為 `ok`、foreign-key violation 為 `0`。manifest 的
`code_content.digest` 已與目前 Phase 1 implementation files 一致。

## 2026-10-20：建立三年軌道分析報告與圖表

**結果**：建立 `output/report/orbit_analysis_report.md` 與資料來源圖。工作期間為
`2023-07-01` 至 `2026-07-01` UTC；主文以 ITRF/GCRF、平均元素、品質與 `chunk`、H2/H3、
3/5 圈 OLS、特徵對齊及稽核為順序。2023 年軌道抬升事件圖標示排除區間與兩側切段。

**限制**：當時圖 5、圖 6 仍取自舊版「每圈右端點」候選，不代表後來的逐 10 秒 v2 輸出。

## 2026-10-21：核對逐 10 秒 3/5 圈候選

**結果**：每個可用的 10 秒時間點，在原始模型與 H2/H3 聯合模型各有 3 圈、5 圈兩個結果位置。視窗歷史不足時仍保留 `time_us`，斜率為 `NULL` 並記錄拒絕原因；不能再用舊版每圈端點的 `16,836`／`16,828` 筆描述現行輸出。

| 工作庫 | 每張 v2 表的時間列 | 每種模型有效 3 圈斜率 | 每種模型有效 5 圈斜率 |
| --- | ---: | ---: | ---: |
| 2023–2026 三年 | 9,469,438 | 9,464,376 | 9,461,003 |
| 2014–2026，實際約十二年半 | 38,378,878 | 38,356,927 | 38,342,299 |

**證據**：兩個 SQLite 工作庫的 `p1_5_6_v2_*` metadata、原始與 H2/H3 表的 `COUNT(*)` 及非空斜率計數。十二年庫候選時間為 `2014-01-01 00:00:04` 至 `2026-06-30 23:59:32` UTC。

**未解決**：尚未逐鍵稽核兩張 v2 表、精確 3/5 圈相位覆蓋，也未建立新版地磁特徵對齊表。列數核對不等於 release 通過。

## 2026-10-21：拆分圖 6，建立十二年工作版報告

**結果**：三年版圖 6 拆為無 H2/H3 與含 H2/H3 兩張；兩圖均以藍色表示 3 圈、橘色表示 5 圈，並共用縱軸範圍。舊的四線圖與四張單線圖移至 `output/image/test/`，未刪除。三年版報告及圖片已推至 GitHub `master`（`e8c3e47`）。

**結果**：新增 `output/report/orbit_analysis_report_2014_2026.md`，使用十二年庫實際筆數，不由三年結果外推。另產生平均半長軸每日總覽，以及 `2024-05-03` 無／含 H2/H3 的兩張逐 10 秒候選圖；候選圖各有 8,640 個時間點，使用相同縱軸。平均半長軸總覽保留 P1.4 官方事件排除前的變化，候選圖則使用 v2 結果。

**決定**：十二年報告排除 2014 年上半年，分析期間改為 `[2014-07-01, 2026-07-01)` UTC。圖 1 已重產；每張 v2 表在此期間有 36,815,038 個右端點，3／5 圈每種模型分別採用 36,794,802／36,781,317 個斜率，且視窗起點不能早於 2014-07-01。原始 POD 與既有工作庫未刪改。

**未解決**：既有 v2 工作庫仍含被報告排除的 2014 年上半年；正式版須依新期間重建或產出可稽核的篩選結果。十二年版的單圈 H2/H3 診斷、全年資料涵蓋圖、地磁對齊與完整稽核仍待產出；目前是工作報告，不是評審版 release。十二年版檔案仍在本機，尚未提交 GitHub。

## 2026-10-23：完成 Phase 2 P2.3 與 P2.4 三年 pilot 檢查點

**決定**：SME 是地面磁力站的地磁活動指數，DNSAPOD 是 Swarm-A POD 反演的衛星位置密度；兩者不互換。P2.4 使用 `SW_OPER_DNSAPOD_2_` 的原生 `density`，不使用 DNSAACC，也不從 Phase 1 的 10-second 軌道列內插密度。每一步複製前一 SQLite，原始檔和舊檢查點不覆寫。

**來源**：現行 P2.2 的 25 場候選窗口需要 217 個 UTC DNSAPOD 日檔。舊窗口已有 181 個；從 ESA 補 36 個，另存 `data/swarm_density_pod/manifest_p2_4_v2.json`。217 檔均為產品版本 `0301`，HDR `Quality_Indicator = 000`，manifest 逐檔記錄 SHA-256 並綁定 P2.3 SQLite SHA-256。舊 manifest 保留供稽核。

**結果**：P2.3 `storm_orbit_1min_v2` 有 280,055 個事件窗口分鐘格，均為 `complete`。P2.4 在原生 L2 時間與 geodetic 位置呼叫 `pymsis` 的 NRLMSIS 2.0，將相同有效樣本上的 L2／MSIS 密度各自平均。624,960 筆 DNSAPOD 原生列中，`validity_flag = 0` 有 624,230 筆、`1` 有 730 筆；559,440 筆落在事件窗口並成功配對。`storm_density_1min_v2` 有 279,720 個配對分鐘格，另有 335 格保留 `NULL`。輸出為 `data/sqlite/2023/swarm_a_phase2_sme_p2_4_v2.sqlite`，SHA-256 `f3ac15792c4c5bdd7af68f56d0a538e0134c9e854f49e3bd0f622a3a1827d8dc`。

**方法界線**：F10.7 用前一日 `OBS`，F10.7A 用截至前一日的 81 日內至少 77 個觀測日平均；ap 用前一完整 UTC 日平均與樣本前已結束的三小時區間歷史。這是本專案的保守替代輸入，不等於 `pymsis` 的 centered 81-day／當日 ap 慣例，也不代表 definitive ap 當時即時發布。DNSAPOD 與 Phase 1 POD 軌道量同源，不能聲稱獨立驗證；尚未產生衰減標籤。

**驗證**：P2.4 的 sample/minute 計數相符，25 場都有配對樣本；SQLite `integrity_check = ok`、foreign key violation = 0。來源 ZIP、manifest、P2.3、GFZ 與 CelesTrak 的 SHA-256 已核對。P2.4 相關 15 個測試通過，涵蓋 UTC 日界、只用已結束 ap、前一日 F10.7、模型單樣本輸出、分鐘平均與缺值。

**未解決**：P2.5 地磁特徵與 P2.6 逐場資格判定未做；25 場仍是候選，不能稱作可用訓練事件。P2.4 的密度比較尚未處理 POD 共同來源的系統誤差，也未做產品高度基準的外部校準。

## 2026-10-22：補齊三年 DNSAPOD 原始檔

**結果**：先核對 P2.3 的 25 場事件窗口：280,055 個分鐘格均有有效 SME，所需 217 個 DNSAPOD 日檔已在本機。再從 ESA 補下載三年 pilot 缺少的 879 個 DNSAPOD 日檔；連同沿用的 217 檔，`2023-07-01` 至 `2026-06-30` UTC 共 1,096 檔、152,923,221 bytes，檔名版本均為 `0301`。原始 ZIP 與 P2.0–P2.4 SQLite 都沒有覆寫。

**證據**：每檔通過 ESA byte count、ZIP 完整性及 SHA-256 核對；日期無缺漏。`data/swarm_density_pod/manifest_dnsapod_20230701_20260630.json` SHA-256 為 `47c55aaf2f25b7adb373148786e7b36b00c54b1b655250cc36810bbdfd159152`；舊事件 manifest SHA-256 維持 `d1eb2a15f862eaedf6841d8399bf8fa63aa5cabe31a71671133b9ae5b2251c07`。下載選日測試及既有 POD 下載測試共 6 項通過。

**未解決**：SME 三年 1,096 個日檔已存在，但 `2026-05-07T02:35:00Z` 起的 79,045 分鐘仍是來源填充值。環境未設定 `SUPERMAG_USER_ID`；無法重新查詢並判定來源是否已補值。三年 DNSAPOD 目前只有原始檔，尚未建立三年密度衍生表。

## 2026-10-23：重新查詢 SME 尾段缺口

**結果**：用 Anby 提供的 SuperMAG 識別名稱，逐日查詢 `2026-05-07` 至 `2026-06-30` UTC，共 55 日。`2026-05-07` 有 155 個有效分鐘，最後一筆是 02:34 UTC，之後 54 日的有效分鐘數均為 0。官方來源沒有新增可用 SME 觀測，因此沒有重複下載填充值日檔，也沒有改動原始 CSV、manifest 或 SQLite。

**未解決**：79,045 分鐘的 SME 長缺口仍在。P2.3 的 25 場事件窗口早於此缺口，現有事件分析不受影響；三年全期 SME 不能宣稱觀測完整。

## 2026-10-23：P2.3 改為逐圈 SME 特徵

**決定**：P2.0–P2.2 沿用；舊一分鐘 P2.3–P2.4 留作 pilot。新版 P2.3 從 P2.2 複製獨立 SQLite，使用 Phase 1 完整相位圈的加權平均半長軸，並在 `u = 0` 的前後 10 秒資料間內插圈界。沒有覆寫原始資料或舊檢查點。

**結果**：`data/sqlite/2023/swarm_a_phase2_sme_p2_3_orbit_v1.sqlite` 新增 `storm_orbit_feature_v1`。25 場候選共有 2,990 圈，2,990 圈的 SME／SYM-H 覆蓋率均達 80%；8 圈因前圈不連續而無 `dsymh_dt_nt_h`。SHA-256 為 `236fa5c7c7ac468b5c2ea91a112b35eba085aa3acbdb7475b8e0ec34930bc8dd`；SQLite integrity 與 foreign key 檢查通過。

**未解決**：新版 P2.4 的 L2 每圈密度與逐場 70% 覆蓋篩選尚未建立。整圈特徵在圈尾後才可取得；`t_mid_time_us` 只是對齊標籤，不是即時發布時間。

## 2026-10-23：移除舊版 Phase 2 SQLite

**結果**：將 `data/sqlite/2023/` 內舊一分鐘 P2.3／P2.4 兩檔，以及 `data/sqlite/phase2_retired_2026-10-22/` 內四檔舊 SQLite 送入 Windows 資源回收筒；退役資料夾的過時說明與空目錄已移除。

**證據**：`data/sqlite/2023/` 現只保留 P2.0、P2.1、P2.2、逐圈 P2.3 四個 SQLite；原始 CSV／ZIP、Phase 1 資料與現行檢查點未刪改。舊 SQLite 被 Git 忽略，須從資源回收筒而非 Git 復原。

**未解決**：舊一分鐘產生程式仍在 repository；若執行，可能重新建立舊檔。本次只移除 SQLite，不改程式。

## 2026-10-23：P2.3 改回事件窗口每分鐘一列

**決定**：P2.2 仍是上游檢查點；P2.3 不先把 SME／SYM-H 壓成逐圈平均。每分鐘接 Phase 1 的 `u`、局部 mean semi-major axis、完整圈歸屬，以及 raw B-L／joint H2/H3 各 3 圈、5 圈的回溯 decay rate。整圈 phase-weighted mean 只作事後摘要，另列來源圈尾時間。

**結果**：`data/sqlite/2023/swarm_a_phase2_sme_p2_3_minute_v1.sqlite` 新增 `storm_minute_feature_v1`，25 場共 280,055 列；所有列均有相位、完整圈連結及四種 rate。`u` 和局部 mean axis 由同 chunk、相距不超過 20 秒的 Phase 1 mean elements 內插到分鐘中點。四種 rate 均取中點以前的 10 秒列，未改正負號。SHA-256 為 `c9c0a45c7e595f85c7d7b44b392d17434d9b74ce924c04b8e8f73444d59d127c`。

**證據**：`integrity_check = ok`，foreign key violation = 0。rate 來源晚於分鐘中點、ap 來源晚於分鐘標籤、相位右端晚於分鐘結束的列數均為 0；整圈 mean 來源晚於分鐘中點的列數為 279,960，因此不可當即時 predictor。舊 `swarm_a_phase2_sme_p2_3_orbit_v1.sqlite` 已送入 Windows 資源回收筒；Git 忽略 SQLite，須從回收筒復原。

**未解決**：L2 密度、逐場覆蓋篩選、延遲核與最終 decay 標籤尚未建立。舊 P2.3/P2.4 pilot 程式仍在 repository，但不屬現行檢查點。

## 2026-10-23：P2.3 分鐘時間戳改為中心對齊

**決定**：京都 SYM-H 的 UTC 整分戳按官方中心標記；SME `tval` 暫按相同中心語意處理，但來源未確認。`05:38:00` 對齊該時刻的 Phase 1 軌道量，名義支持區間為 `05:37:30–05:38:30`。P2.0–P2.2 不改動；由 P2.2 另建 P2.3 v2，不覆寫舊檢查點。

**結果**：`data/sqlite/2023/swarm_a_phase2_sme_p2_3_minute_v2.sqlite` 新增 `storm_minute_feature_v2`，25 場、280,055 列；相位、完整圈連結及四種 rate 均有值。例：`2023-08-03T05:38:00Z` 取 Phase 1 的 `05:37:52` 與 `05:38:02` 內插，rate 只取前者。P2.1 原有 SME 標籤 +60 s 可用界線維持保守，不把名義支持區間終點當實際發布時間。舊 `swarm_a_phase2_sme_p2_3_minute_v1.sqlite` 已送入 Windows 資源回收筒；Git 忽略 SQLite，須從回收筒復原。

**證據**：7 項 P2.3 測試通過；SQLite `integrity_check = ok`、foreign key violation = 0。rate 來源晚於 target、ap 來源晚於來源標籤、相位右端晚於名義支持區間終點皆為 0。整圈 mean 來源晚於 target 的列數為 279,924，僅供事後描述。SQLite SHA-256 為 `0aa7021f92a6b7d89272a11980f60df309a72a765f04c9db60d301f2f0b170a3`。

**未解決**：SuperMAG 尚未確認 `tval` 的區間位置與實際發布時間；L2 密度、逐場覆蓋篩選、延遲核及最終衰減標籤未建立。

## 2026-10-23：合併完整圈事件並完成 P2.4 v3 密度檢查點

**決定**：以含 `t0` 的第 0 圈、前 31 圈、後 61 圈建立 93 圈窗口；相鄰窗口若共享完整圈，按聯集合併並以較深 SYM-H 最低點為代表。P2.3 v2 鐘錶窗口保留作歷史資料，不作 P2.4 輸入。P2.4 的 DNSAPOD 原生 `density` 與 `density_orbitmean` 分開保留；逐圈 L2、L2／MSIS 配對及逐場合格圈比例均需至少 80%。MSIS 的 81 日 F10.7 歷史只接受完整 `OBS` 日，不用 `INT` 填補。

**結果**：P2.3 v3 由 P2.2 複製建立 `storm_event_full_orbit_v3`、`storm_event_orbit_v3`、`storm_minute_feature_v3`，有 25 場、2,325 圈、217,912 分鐘；三年候選沒有新增重疊合併。P2.4 v3 再複製 P2.3 v3，建立 `storm_density_1min_v3`、`storm_orbit_coverage_v3`、`storm_catalog_v3`。當時曾另匯出 catalog CSV，後續已刪除，正式紀錄仍在 SQLite。25 場中 21 場 `used`，4 場 `excluded_coverage`。

**證據**：P2.3 v3 SQLite SHA-256 為 `acda2fac9710dc076b0128c491b7f78a0c3d5fb4966e4860153e8b5c33a43599`；P2.4 v3 為 `4fc0085035f268fc8fd3ec6798856018760ee5eb2cc43a50873f13e20118e214`。P2.4 核對 175 個 DNSAPOD 日檔與 504,000 筆來源樣本；逐圈預期 435,830 個 30 秒位置，主 L2 有效 435,220，L2／MSIS 成功配對 365,664。兩個 SQLite 的 integrity 與 foreign key 檢查通過；P2.0–P2.4 相關測試共 27 項通過。

**未解決**：4 場缺配對不是 L2 缺失，而是其 81 日歷史窗包含 CelesTrak `INT` 日；目前不放寬來源契約。密度與 POD 軌道量同源，尚無獨立衰減驗證；延遲核、機動排除、峰值時序圖與最終衰減標籤未完成。

## 2026-10-23：完成三年 Phase 2 每圈地磁摘要與峰值自我檢查

**決定**：P2.5 建立精簡的獨立 SQLite，只存每圈 SME、SYM-H、測站數、有效性及前一圈變化率；metadata 鎖定 P2.4 SHA-256，不再整庫複製。P2.6 以 `t0` 前後 24 h 的每圈 SME 與同圈配對密度比自然對數最大值檢查峰值順序；這是描述性診斷，不用來排除事件。

**結果**：`storm_geomag_orbit_v1` 共 2,325 圈，SME 與 SYM-H 分鐘覆蓋率均為 100%，全部達到 80% 門檻；SMEnum 範圍 71–133。21 場 P2.4 密度合格事件中，5 場符合 SME 峰 < 密度差峰 < SYM-H `t0`，20 場為複合事件。2024-05-11 案例的三個時刻依序是 SYM-H `t0` 0 h、密度差峰 +1.2 h、每圈 SME 峰 +12.2 h；已產生 F2-3 案例圖與 21 場散點圖。

**證據**：P2.5 SQLite SHA-256 `c0221fe1f7c368aa1f25b753d2105bcc6d0956e12f7b7964c278e7cc8a41a005`；P2.4 SQLite SHA-256 維持 `4fc0085035f268fc8fd3ec6798856018760ee5eb2cc43a50873f13e20118e214`。當時的 P2.6 CSV SHA-256 為 `9e75f60dafcd31598d2d5363fc889fa1961af113ca3efb032d717368b68ebb43`；後續改以 SQLite 重算、逐欄核對一致，並刪除 CSV。當時 P2.0–P2.6 相關測試 38 項通過。輸出樣本、時間語意與來源鍵見 `data_lineage/phase_2_storm_dataset.md`。

**未解決**：原報告的峰值順序不能當作本資料的普遍事實；複合事件、峰值選法與軌道採樣位置需在延遲模型前分層檢驗。4 場 MSIS 配對缺口仍受 `INT` 日限制。機動排除、獨立軌道衰減標籤與延遲核不屬本次已完成的 SME 資料產物。

## 2026-10-23：匯出 21 場 Phase 2.6 峰值比較圖

**決定**：沿用 P2.6 的 `t0` 前後 24 h 峰值定義，不改動事件篩選或來源 SQLite。「密度峰」指每圈配對密度比 `ln(L2/MSIS)` 最大值，不是原始 L2 密度最大值。圖檔以 SYM-H `t0` 的 UTC 日期與時間命名，集中於 `output/image/Phase2/P2.6/`。

**結果**：產生 21 張逐場 PNG、當時的 21 列 `peak_times.csv` 與資料夾內的說明檔。每張圖標出每圈 SME 峰、配對密度比峰及 1 分鐘 SYM-H 最低點；CSV 後續已刪除，峰值時間以 P2.6 SQLite 為準。未修改 P2.4、P2.5 或原有圖檔。

**證據**：21 個不同 `storm_id` 對應 21 張 PNG；`expected_order = 1` 仍為 5 場。抽查 2023-08-05、2024-05-11、2026-04-18 圖的峰值標記與時間；當時的 `peak_times.csv` SHA-256 為 `47c2d99472ecade93e3bf315c59cd4f19bc917cdc1aa1f8830f7fb266c468ac7`，僅留作歷史追溯。

**未解決**：複合事件的全窗口最大值可能來自不同脈衝；這組圖只供描述性比較，不能單獨證明能量輸入到密度反應的因果延遲。

## 2026-10-23：統一 Phase 2 衍生資料為 SQLite

**決定**：P2.4 的 catalog 以 `storm_catalog_v3` 為唯一正式紀錄；P2.6 峰值稽核改存獨立 SQLite 的 `storm_peak_order_v1`。圖目錄只留 21 張 PNG 與說明，不再複製數值索引 CSV。原始來源 CSV 不受影響。

**結果**：建立 `data/sqlite/2023/swarm_a_phase2_sme_p2_6_peak_order_v1.sqlite`，記錄 21 場與兩個上游 SQLite 的 SHA-256。刪除 P2.4 catalog、P2.6 峰值及圖目錄索引共三個衍生 CSV；P2.4 writer、P2.6 writer 與圖表 reader 均改成 SQLite 契約。同步修正方法報告中的 SME 實際路徑、缺值政策及分鐘／圈相對時間定義。

**證據**：新 P2.6 表 21 列，與刪除前峰值 CSV 的欄名和所有值逐欄一致；`expected_order = 1` 為 5 場。SQLite `integrity_check = ok`，SHA-256 為 `3172340c4a38a98aca462afead59c3eb9f055d422fc8f760029c421244045465`。P2.4、P2.5 SHA-256 未變；Phase 2 相關測試 54 項通過。

**未解決**：P2.6 是描述性峰值稽核，不是延遲核或衰減標籤；4 場 MSIS 配對缺口與複合事件峰值解讀仍待後續研究。另發現 P2.4 圈內原生計數比分鐘表多 18 筆 L2、16 筆配對邊界樣本；已在 lineage 與 ISSUE 記錄兩種計數母體，未改寫封存檢查點。
