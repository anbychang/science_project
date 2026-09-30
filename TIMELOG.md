# Swarm-A 軌道衰減研究時間紀錄

最後更新：2026-09-30

這份檔案只記錄時間順序：某一天做了什麼、量到什麼、得到什麼結論。它不放長期規則或完整技術定義；那些放在 `PROJECT_MEMO.md`。

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

## 下一個時間紀錄應記錄的實驗

下一個工作只能從以下可驗證項目選擇：

1. P1.4-C：盤點 SP3 source 的真實 frame label 與 official quality information。
2. P1.4-D：從正常 interval 的 position/velocity residual 校準 maneuver candidate，並以 synthetic jump 驗證。
3. P1.5-A：建立並驗證 orbit-average synthetic input，檢驗候選方法能否回收已知 slope。

每次新增紀錄都要寫：原始輸入、實際操作、量測結果、結論、下一步；不可只寫「完成某功能」。
