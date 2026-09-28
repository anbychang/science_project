# 2026-09-28 全專案 Clean Code Review

## 結論

已逐一檢查 `satellite_orbit/` 與 `tests/` 的全部 Python 檔案。這次採用的規則是：
只有在新寫法同時更短、更直接或讓錯誤更容易測試時才改。沒有為了形式上符合
Clean Code 規則而新增 dataclass、Enum、wrapper 或抽象 base class。

這是刻意的取捨：本專案的 orbit state 是資料管線共同使用的動態 dict。把它改成多個
class、把 SQLite entry point 的路徑參數包成 config object，會增加檔案與轉換，沒有解決
目前問題。因此外來 skill 的「所有公開函式都要 type hint」與「所有函式最多三個參數」
不機械套用；專案的簡單 state shape 與最小抽象原則優先。

## 本次實際修改

| 原本目標與寫法 | 比較後保留的簡單版本 | 理由 |
| --- | --- | --- |
| SYM-H 與 AE 用 `write_geomagnetic(..., index_name)` 共用，靠 selector 與 column mapping 決定行為。 | 同一檔內改成 `write_sym_h()` 與 `write_ae()`；共用的只有 CSV-to-row 轉換。 | 兩種 index 是固定的兩件事。明確函式比 selector 更容易讀，也沒有動態 SQL。 |
| `starts_new_interval()` 接收目前 row、前一時間、前一 source、前一 usable、cadence 共五個值。 | 前一筆品質資訊收成一個 `previous_quality_row`，函式只收目前列、前列、cadence。 | 呼叫端少了平行變數，前一筆資料不會互相失去同步。 |
| orbital-element writer 把 `source_id` group 叫作 day。 | 改名為 source range/source file。 | 實際依據是 `source_id`，不是日曆日。名稱現在描述真實資料模型。 |
| GPS sequence conversion 用兩段 append loop。 | 用兩個直接的 list comprehension。 | 輸入輸出相同，少了可變暫存 list。 |
| Ap 的 3 小時區段與兩種歷史平均範圍散在函式內。 | 用 `AP_BLOCK_HOURS` 與兩個明確的 history range。 | 來源資料的時間規則有一個名稱，不再靠裸數字閱讀。 |
| POD source 更新函式叫 `source_id_for_file()`。 | 改成 `prepare_source_file()`；weather block 名稱也改明確。 | 該函式不只是取得 id，還會處理已變更 source 的既有列。 |
| 舊的 `load_swarm_pod_period()` 與 ZIP 搜尋 helper 沒有任何呼叫者。 | 刪除。 | 現行流程從 SQLite 讀時間範圍；保留舊入口只增加四參數 API 與維護面積。 |
| 二體與 J2 加速度對地心 position 直接除以零。 | 對 non-finite 或零距離明確拋出 `ValueError`，各有 unit test。 | 這是實際邊界條件，不是防禦性裝飾。 |

## 逐檔決定

`維持` 代表已比較過，重寫只會增加抽象或不會提升可讀性；不是漏看。

| 檔案 | 目標 | 決定 |
| --- | --- | --- |
| `satellite_orbit/__init__.py` | package 標記。 | 維持；只有必要 module docstring。 |
| `calculation/__init__.py` | calculation package 標記。 | 維持。 |
| `calc_atmosphere.py` | GCRF state 與 solar/geomagnetic input 交給 NRLMSIS，回傳加上密度的 state。 | 維持；把 pymsis input 拆成 class 或 wrapper 會遮住唯一外部 API call。單位轉換註解保留，因為它說明外部 library 邊界。 |
| `calc_coordinates.py` | 在 GCRF、ITRF、geodetic 間轉換 state/vector。 | 維持；單筆與批次轉換都有直接用途，批次版本避免逐筆 Astropy 呼叫。 |
| `calc_forces.py` | 二體重力、J2、合重力與 state derivative。 | 修改；對零/非有限 distance 加明確 guard，避免除以零。公式沒有拆分，避免隱藏物理式。 |
| `calc_integrator.py` | RK4 推進完整 state。 | 維持；RK4 四個 stage 的重複是演算法本體，抽成過度通用 helper 反而難讀。保留附帶 state 欄位的修正與測試。 |
| `calc_orbital_response.py` | 從 GCRF state 算瞬時半長軸。 | 維持；距離、能量、bound orbit guard 都是必要物理邊界。 |
| `calc_position_error.py` | 比較同 frame 的 position distance。 | 維持；三行計算已是最小正確版本。 |
| `calc_time.py` | GPS datetime 轉 UTC。 | 修改；刪除中間 list 與 append loop，保留 leap-second offset 最佳化。 |
| `data/__init__.py` | data package 標記。 | 維持。 |
| `down_geomagnetic.py` | 從 Kyoto 下載 SYM-H、AE。 | 維持；兩個 dataset 的 metadata 是固定來源設定，不是可擴充框架。 |
| `down_space_weather.py` | 下載 CelesTrak `SW-All.csv`。 | 維持；已是一個簡單且 idempotent 的下載函式。 |
| `down_swarm_pod.py` | 列出 ESA POD、選每日期最新版、下載。 | 維持；檔名解析、版本挑選和下載各自已有小函式。 |
| `load_geomagnetic.py` | 讀單一 SYM-H/AE CSV，輸出共用 observation shape。 | 維持；兩種檔案格式相同，這個共用 parser 是真的 DRY。 |
| `load_space_weather.py` | 對一個 state 加入 F10.7、F10.7A 與 Ap history。 | 修改；3 小時 block 與 history range 具名化，平均函式由四參數降為三參數。 |
| `load_sqlite_states.py` | 由 raw SQLite 查出 ITRF state 與對應 weather。 | 維持；row-to-state 的轉換是唯一需要，query 與輸出 shape 對應直接。 |
| `load_swarm_density.py` | 解開 DNSAACC CDF 並濾掉 fill value。 | 維持；列處理直接反映 CDF 變數，沒有多餘層次。 |
| `load_swarm_pod.py` | 讀 POD SP3、轉 SI 與 UTC。 | 修改；刪除未使用的 period loader 和 ZIP 搜尋 helper，轉 UTC 的 list 建立改成直接形式。 |
| `prep_sqlite_common.py` | SQLite preparation 共用的 time/signature 工具。 | 維持；兩個函式很小且真正共用。 |
| `prep_sqlite_density.py` | 將 density raw observations 寫入 SQLite。 | 維持；保留目前獨立責任。source signature/key migration 是資料模型變更，等 density 加入研究主線時再做。 |
| `prep_sqlite_geomagnetic.py` | 寫入 SYM-H 與 AE。 | 修改；拿掉 selector abstraction，保留兩個明確 writer 與一個共用 row converter。 |
| `prep_sqlite_pod.py` | 將 POD 寫入 raw state table 並依 weather block 對齊。 | 修改；`weather_block_time` 與 `prepare_source_file` 名稱說明真正行為，過濾改成單一 list comprehension。 |
| `prep_sqlite_tables.py` | 建立 raw SQLite schema。 | 維持；schema 集中在一處是正確的 single source of truth。 |
| `prep_sqlite_weather.py` | 將 weather CSV 展成 3 小時 raw rows。 | 維持；signature guard 和 incomplete-row skip 是資料完整性需要。 |
| `prep_write_orbital_elements.py` | 由 raw state 建立瞬時半長軸 derived table。 | 修改；source-file terminology 取代 day terminology。逐 source commit 是長資料工作需要，不抽象。 |
| `prep_write_pod_quality.py` | 重建 POD quality 與 continuous interval derived table。 | 修改；interval decision 改為傳遞一個前筆 context，減少平行參數。Q3/Q4 仍未實作，沒有假造通用 quality framework。 |
| `prep_write_sqlite.py` | 協調所有 raw data writer。 | 修改；`available_weather_times` 用名稱與 set comprehension 表達查詢目的。五個可注入 path 參數保留，因為它是唯一的 batch entry point；額外 config class 只會增加層次。 |
| `tests/test_calc_coordinates.py` | 驗證最新 POD 日期的 frame round trip 與 IERS freshness。 | 維持；這是外部資料邊界測試，不能為了速度改成 mock。 |
| `tests/test_calc_forces.py` | 驗證 gravity zero-distance guard。 | 新增；兩個小型 unit test 各驗證一個 public force function。 |
| `tests/test_calc_integrator.py` | 驗證 RK4 不丟失附帶 state 欄位。 | 維持；這是之前修正的直接 regression test。 |
| `tests/test_calc_orbital_response.py` | 驗證 circular orbit、frame 與 bound-orbit guard。 | 維持；涵蓋主要物理邊界。 |
| `tests/test_prep_pod_quality.py` | 驗證 Q1/Q5、interval boundary、derived rebuild。 | 修改；更新為三參數 interval API，補連續列與前列 rejected 的 branch。保留 in-memory/small SQLite test，不讀正式資料庫。 |
| `tests/test_prep_sqlite.py` | 驗證 SYM-H/AE 可以共存同一 geomagnetic row。 | 修改；改呼叫兩個明確 writer，測試不再依賴 selector。 |
| `tests/test_prep_sqlite_pod.py` | 驗證 POD UTC time 對齊正確的 3 小時 weather block。 | 新增；覆蓋 02:59 與 03:00 boundary。 |

## 刻意不做的改動

1. 不把 state dict 改成 dataclass 或 TypedDict。這會迫使所有 loader、座標轉換、force、
   atmosphere、RK4 改寫，卻沒有修正現在已知問題。
2. 不把物理常數改成 Enum。`MU_M3_S2`、`R_EARTH_M`、`J2` 是數值常數，不是離散狀態。
3. 不把 `write_sqlite_database()` 的多個 path 參數封成 config object。它是測試與 batch
   重建需要的少數注入點，現在比另一個 class 更直接。
4. 不為每個 SQL statement 或外部 API 再包一層 repository/service。SQLite 和官方資料
   loader 已是清楚邊界，額外層沒有收益。

## 驗證標準

完成後必須通過：

```powershell
python -m unittest discover -s tests -v
python -m compileall -q satellite_orbit tests
git diff --check
```

`ruff.toml` 存在，但本機沒有 ruff executable；不把不存在的工具假裝成通過的 gate。

## 實際執行結果

除 unit tests 外，已在目前的本機 SQLite 執行三個正式 entry point：

```text
prep_write_sqlite
weather rows added: 0
POD files changed: 0
orbit states added: 0

prep_write_orbital_elements
POD source files: 1,685
missing POD source files written: 0
rows rejected: 0

prep_write_pod_quality
swarm_a_states rows: 14,558,400
swarm_a_pod_quality rows: 14,558,400
is_usable = 1 rows: 14,558,400
interval count: 1,685
```

這驗證的是現行本機 raw SQLite 的重建/讀取流程；下載器沒有執行，避免在 code review
時發起新的外部下載。
