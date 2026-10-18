# Swarm-A 軌道衰減研究時間紀錄

最後更新：2026-10-18

Current status：`data/swarm_a_phase1_rebuild_v4.sqlite` 是現行 Phase 1 working output，已通過 audit；它是由 v3 從 signed-rate stage 往下重建，並非 full fresh rebuild。詳細交付與限制見 `plans/phase_1_data_preparation/PHASE_1_FINAL_REPORT.md`。

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
6. 由月 CSV 流程改為單一 `swarm_a_data.sqlite`。

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

**限制**：這是 current-database audit。weather preparation v2/v3 修正後，尚未從 raw files fresh rebuild 並重跑完整 audit；不可將本次結果稱為 frozen release。

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
做 P1.4--P1.7 partial rebuild，因此狀態為 `working_audit_pass`，不是 `frozen`；它沒有偽稱
為完整 fresh rebuild。

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
