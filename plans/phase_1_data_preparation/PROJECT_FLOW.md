# 專案現行全流程圖

## 結論

目前可執行主線止於 P1.4：原始來源 -> raw SQLite -> GCRF 瞬時半長軸 -> POD 品質與連續區間。

`swarm_a_orbit_10min`、`swarm_a_analysis_10min`、P1.6 feature join、CSV/Parquet export 都還不存在。圖中的虛線是已寫成規格、尚未實作的工作；不是目前的產物。

此圖以目前工作樹的程式為準，不把歷史文件中的 J2、RK4、NRLMSIS 或 position-error 畫成現行流程。

## 端到端資料流

```mermaid
flowchart TD
    classDef source fill:#e7f3ff,stroke:#4c78a8,color:#111
    classDef raw fill:#fff4d6,stroke:#b07d15,color:#111
    classDef derived fill:#e5f5e8,stroke:#39814a,color:#111
    classDef planned fill:#f3f3f3,stroke:#777,color:#333,stroke-dasharray: 5 5
    classDef stop fill:#fde8e8,stroke:#b44,color:#111

    subgraph inputs[原始來源與本機檔案]
        ESA[ESA Swarm-A POD ZIP<br/>內含 SP3]:::source
        CEL[CelesTrak SW-All.csv<br/>F10.7 / F10.7A / Ap]:::source
        WDC[WDC Kyoto HAPI CSV<br/>SYM-H / AE]:::source
        DNS[Swarm DNSAACC density ZIP<br/>內含 CDF]:::source

        PODZIP[data/swarm_a_pod/*.ZIP]:::source
        SWCSV[data/space_weather/SW-All.csv]:::source
        GEOCSV[data/geomagnetic/{sym_h,ae}_*.csv]:::source
        DENSZIP[data/swarm_density_acc/*.ZIP]:::source

        ESA -->|down_swarm_pod.py<br/>每日期取最高版本| PODZIP
        CEL -->|down_space_weather.py<br/>函式入口，無 CLI| SWCSV
        WDC -->|down_geomagnetic.py<br/>CLI；每次最多 180 天| GEOCSV
        DNS -.->|沒有下載器；檔案由外部放入| DENSZIP
    end

    subgraph rawbuild[Raw SQLite 重建：python -m satellite_orbit.data.prep_raw_database]
        SCHEMA[prep_raw_schema.create_tables<br/>建立 raw tables]:::raw
        WEATHER[prep_raw_weather.write_space_weather<br/>每天展開 8 個 3-hour block]:::raw
        GEOMAG[prep_raw_geomagnetic.write_sym_h / write_ae<br/>跳過 99999 缺失碼]:::raw
        POD[prep_raw_pod.write_pod_folder<br/>SP3 GPS -> UTC；km -> m；dm/s -> m/s]:::raw
        DENSITY[prep_raw_density.write_density_folder<br/>CDF；濾除 <= 0 與 fill value]:::raw
        DB[(data/swarm_a_data.sqlite)]:::raw

        SCHEMA --> WEATHER
        WEATHER -->|已知 3-hour weather time_us| POD
        SCHEMA --> GEOMAG
        SCHEMA --> DENSITY
        SWCSV --> WEATHER
        GEOCSV --> GEOMAG
        PODZIP --> POD
        DENSZIP --> DENSITY
        WEATHER --> DB
        GEOMAG --> DB
        POD --> DB
        DENSITY --> DB
    end

    subgraph rawtables[不可變 raw tables]
        SW[(space_weather<br/>time_us；F10.7；F10.7A；Ap history；type)]:::raw
        GM[(geomagnetic<br/>time_us；sym_h_nt；ae_nt；versions)]:::raw
        STATE[(swarm_a_states<br/>time_us；ITRF x/y/z m；vx/vy/vz m/s；weather_time_us；source_id)]:::raw
        DENST[(swarm_a_density<br/>time_us；density kg/m^3；altitude；lat/lon；LST)]:::raw
        FILES[(source_files<br/>source_id；file_name；size:mtime signature)]:::raw
        META[(metadata<br/>weather signature / procedure version)]:::raw
        DB --> SW
        DB --> GM
        DB --> STATE
        DB --> DENST
        DB --> FILES
        DB --> META
    end

    subgraph p13[P1.3：已實作的瞬時軌道元素]
        READSTATE[依 source_id 讀取 raw state<br/>{time, ITRF, position_m, velocity_m_s}]:::derived
        GCRF[calc_coordinates.itrf_states_to_gcrf<br/>Astropy ITRS -> GCRS]:::derived
        ENERGY[calc_orbital_response.calculate_semi_major_axis<br/>two-body specific energy；mu = 3.986004418e14]:::derived
        ELEMENT[(swarm_a_orbital_elements<br/>time_us；semi_major_axis_m；rejection_reason)]:::derived
        STATE --> READSTATE --> GCRF --> ENERGY --> ELEMENT
        META -.->|algorithm / mu / IERS data version| ELEMENT
    end

    subgraph p14[P1.4：已實作的基本 QC 與連續區間]
        QUALITY[prep_derived_pod_quality<br/>Q1 finite/time；Q5 bound-energy<br/>量測 native cadence]:::derived
        QTABLE[(swarm_a_pod_quality<br/>time_us；is_usable；rejection_reason；interval_id)]:::derived
        STATE --> QUALITY
        ELEMENT --> QUALITY --> QTABLE
    end

    subgraph later[後續資料集：規格已定，尚未實作]
        P15[P1.5：同一 interval 的 usable POD<br/>orbit-average / mean-element / short-period treatment<br/>10-minute bins 與 smoothing]:::planned
        ORBIT10[(planned: swarm_a_orbit_10min<br/>time_us；平滑半長軸；導數；decay rate；pod_count；gap；interval_id)]:::planned
        P16[P1.6：依 time_us 對齊 feature<br/>SYM-H exact 或 <= 2 min bracket interpolation<br/>Ap official 3-hour block<br/>前一日 F10.7 與 trailing F10.7A]:::planned
        ANALYSIS[(planned: swarm_a_analysis_10min<br/>P1.5 orbit 欄位 + SYM-H + Ap + F10.7/F10.7A<br/>source times + quality_flags)]:::planned
        P17[P1.7：重現性 metadata 與可選 CSV / Parquet export]:::planned
        QTABLE -.->|僅 is_usable = 1；不可跨 interval| P15
        ELEMENT -.-> P15
        P15 -.-> ORBIT10 -.-> P16 -.-> ANALYSIS -.-> P17
        GM -.-> P16
        SW -.-> P16
    end

    DENST -.->|現在不 join P1.6| HOLD[獨立保存，等待研究問題與對齊規則]:::stop
    LEGACY[已從目前工作樹刪除：J2 force、RK4、NRLMSIS、position error<br/>僅保留歷史證據，沒有現行呼叫鏈]:::stop
```

## 每一段實際做的事

| 階段 | 入口或模組 | 輸入 -> 輸出 | 不可忽略的規則 |
| --- | --- | --- | --- |
| POD 下載 | `python -m satellite_orbit.data.down_swarm_pod [FIRST_DAY]` | ESA listing -> `data/swarm_a_pod/*.ZIP` | 同日只取最高 product version；下載大小不符即刪除不完整檔。 |
| Space weather 下載 | `down_space_weather.download_space_weather()` | CelesTrak -> `SW-All.csv` | 沒有 CLI；已有本機檔直接返回，不自動更新。 |
| Geomagnetic 下載 | `python -m satellite_orbit.data.down_geomagnetic FIRST_DAY LAST_DAY` | WDC HAPI -> SYM-H / AE CSV | 下載後檢查首尾 observation 是否覆蓋 requested range；暫存 `.download` 只在驗證後取代正式檔。 |
| POD 解析 | `load_swarm_pod.py` | SP3 `*` / `P` / `V` -> `[state, ...]` | GPS time -> UTC；position km -> m；velocity dm/s -> m/s；state frame 暫標 `ITRF`。 |
| Weather 解析 | `load_space_weather.py` | daily row -> state + weather | 輸出有前一日 F10.7、當日 centered / trailing F10.7A、7 個 Ap 值與資料型別。 |
| Raw database | `prep_raw_database.py` | 四類本機 raw file -> SQLite | 順序固定為 weather -> SYM-H -> AE -> POD -> density，故 POD epoch 沒有對應 weather 3-hour block 就不寫入。 |
| P1.3 元素 | `python -m satellite_orbit.data.prep_derived_orbital_elements` | raw ITRF state -> GCRF -> 瞬時半長軸 | 不是 propagator。non-finite、零半徑或 unbound energy 寫 `rejection_reason`，不假造值。 |
| P1.4 QC | `python -m satellite_orbit.data.prep_derived_pod_quality` | raw state + P1.3 -> usability / interval | source boundary、前一筆 rejected、或 gap 大於測得 cadence 都會切新 interval。Q3 official flag、Q4 maneuver 尚未實作。 |

## SQLite 資料責任與重建邊界

```text
raw source files
  -> raw tables: 只新增或補齊，不用 derived calculation 覆寫
  -> derived tables: 每個 calculation 以 raw time_us 為 key 重建自己的結果
```

- `space_weather`：每 3 小時一列。`f107_sfu` 是前一日 `F10.7_OBS`；`f107a_sfu` 是當日 centered 81-day 值，只留給歷史 NRLMSIS 使用；`f107a_last81_sfu` 是 trailing 值，供未來 P1.6 使用。
- `geomagnetic`：同一 `time_us` 可先後補入 SYM-H 或 AE，但已有的同欄位值不覆寫。
- `swarm_a_states`：raw POD 的 `time_us` 是主追溯 key。相同檔名而 signature 改變會直接失敗，要求建立 fresh database，不能偷偷替換 raw record。
- `swarm_a_density`：已保存但未進主線；檔案判定仍只依 `source_file_name`，這是已知限制。
- `swarm_a_orbital_elements` 與 `swarm_a_pod_quality`：可以清空並由 raw tables 重建；不會改 raw records。

## P1.5 到 P1.7 的明確阻塞點

```text
P1.4 usable interval
  -> [未解] 驗證可處理 J2 / short-period variation 的 orbit-average 或 mean-element 方法
  -> [未解] 產生並驗證 10-minute orbit rows
  -> [未解] 依已固定時間規則實作 P1.6 join
  -> [未解] 寫 final SQLite dataset 與 release metadata
```

不能跳過這些阻塞點：直接對每 10 秒 osculating `semi_major_axis_m` 平滑或求導，會把 short-period variation 誤判成 decay。已淘汰的 direct Savitzky-Golay 與簡單 rectangular orbit average 都不能當 P1.5 輸出。

P1.6 實作後必須遵守：

- SYM-H 可 exact match；只有左右 observation 都存在且總 gap <= 2 分鐘時才可線性內插，並保存左右 source time。
- Ap 不內插，嚴格用 target 所在 official 3-hour block。
- F10.7 與分析用 F10.7A 都使用前一日來源；F10.7A 必須用 trailing `F10.7_OBS_LAST81`，不可用 centered average。
- feature 缺失時保留 orbit row，寫 `NULL` 和 `quality_flags`；不能為了 join 成功而刪除 orbit row。

## 現行程式與規格索引

| 類別 | 檔案 | 角色 |
| --- | --- | --- |
| 命令入口 | `satellite_orbit/data/down_swarm_pod.py`、`down_geomagnetic.py`、`prep_raw_database.py`、`prep_derived_orbital_elements.py`、`prep_derived_pod_quality.py` | 可直接執行的資料取得與資料庫階段。 |
| 讀取與 raw 寫入 | `satellite_orbit/data/load_*.py`、`prep_raw_*.py` | 原始格式、SI 轉換、raw SQLite 寫入。 |
| 計算 | `satellite_orbit/calculation/calc_time.py`、`calc_coordinates.py`、`calc_orbital_response.py` | GPS/UTC、ITRF/GCRF、two-body specific-energy 半長軸。 |
| 測試 | `tests/test_*.py` | 覆蓋時間、座標、瞬時半長軸、raw writer、weather、POD quality。 |
| 階段規格 | `PLAN.md`、`P1.4_TO_P1.7_EXECUTION_PLAN.md`、`P1.5_RESAMPLE_AND_DECAY.md`、`P1.6_ANALYSIS_SCHEMA.md` | 決定未實作階段的輸入、輸出、時間邊界與停止條件。 |

## 已知資料風險

- SP3 source files 實際跨 `IGb14`、`IGS20`、`IGb20`、`IGc20`，但 current loader 全部寫成 generic `ITRF`。正式做跨 transition 的 decay 分析前，必須保存 frame label、決定 transformation，並檢查半長軸連續性。
- GCRF conversion 依賴本機 IERS / leap-second data。批次分析要固定並記錄版本，不能依賴未記錄的自動更新。
- DNSAACC density、AE、NRLMSIS 都不是現行 P1.6 core feature。資料存在不等於可以加入分析欄位。
