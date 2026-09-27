# 2026-09-28 變更與專案盤點報告

## 結論

P1.4 至 P1.7 的執行順序、可平行工作、停止條件與輸出 schema 已寫成可直接照做的
計畫。程式的資料責任邊界也做了兩個必要修正：RK4 不再遺失 state 的額外欄位，P1.4
品質表重跑時不會保留 raw POD 已不存在的舊列。

本次沒有開始 P1.5 smoothing、P1.6 join 或 ML。這是刻意的：P1.4 的 Q3/Q4 和
P1.5 短週期項處理尚未做出可驗證決策，現在硬做只會製造看似完整但不可解釋的資料。

## 新增或更新的文件

- `P1.4_TO_P1.7_EXECUTION_PLAN.md`：P1.4-C/D、P1.5-A 至 D、P1.6-A/B、P1.7 的
  執行步驟、依賴圖、可平行工作、測試與 release gate。
- `PLAN.md`：統一衰減率欄位為 `da_dt_smooth_m_s` 與
  `decay_rate_smooth_m_day`；修正 F10.7/F10.7A 各自需要 source time；更新 IERS
  現況。
- `P1.5_RESAMPLE_AND_DECAY.md`：P1.5 輸出欄位改為 orbit-mean、smooth 與 smooth
  derivative，避免和 P1.3 的瞬時 `semi_major_axis_m` 混淆。
- `POD_FINAL_OUTPUT_SPEC.md`：重新界定為 P1.5 軌道中間表規格。P1.7 完整資料集
  另有 geomagnetic/space-weather feature，不能再把兩者說成同一張表。
- `README.md`：資料流程與 P1.4/P1.5 實際進度已同步。

## 程式重構與修正

### 保留完整 state

`calc_integrator.py` 的 `shifted_state()` 與 `rk4_step()` 以前只建立四個軌道欄位，
會丟掉 `f107_sfu`、`ap_values`、`density_kg_m3` 等 state 附帶資料。現在先複製原
state，再只更新時間、位置、速度。這符合全專案只傳遞一個 state 的約定。

新增 `test_calc_integrator.py`，確認兩個路徑都保留 weather 欄位。

### 可重建的 P1.4 derived table

`prep_write_pod_quality.py` 現在每次建立 `swarm_a_pod_quality` 前會清空舊的
derived rows。raw `swarm_a_states` 完全不會被修改。這修正了 raw POD 改變後，quality
table 可能留下孤兒列的問題。

程式同時在沒有足夠 raw state 可量測 cadence 時明確失敗，而不是在後續以 `None`
比較後產生不清楚的錯誤；讀取 cursor 也會確實關閉。

新增 integration test：先放入兩筆 raw POD 與一筆過期 quality row，rebuild 後只留下
對應 raw POD 的兩筆 derived row。

### 現有資料 I/O 的責任分離

這批變更也把 SYM-H/AE 的 CSV parsing 集中在 `load_geomagnetic.py`，讓兩個 SQLite
writer 只負責 table row shape；Swarm DNSAACC density 則有獨立 loader、writer 與 raw
table。`prep_write_sqlite.py` 保持為順序協調器，而不是塞入 parsing 邏輯。

## 專案級盤點

### 已修正的衝突

| 衝突 | 修正 |
| --- | --- |
| P1.3 的瞬時半長軸與 P1.5 平滑半長軸同時被叫作 `semi_major_axis_m` | P1.5 改用 `semi_major_axis_orbit_mean_m`、`semi_major_axis_smooth_m`、`da_dt_smooth_m_s`。 |
| P1.5 軌道表與 P1.7 完整分析表界線不清 | 明確分成 `swarm_a_orbit_10min` 與 `swarm_a_analysis_10min` 的規劃。 |
| F10.7 與 F10.7A 其實來自不同日期，卻只有一個 source timestamp | final schema 改成 `f107_source_time_us` 與 `f107a_source_time_us`。 |
| RK4 破壞 state shape | 改成 copy-and-update，並有測試。 |
| P1.4 重跑可能混入舊 derived row | rebuild 前清空 derived table，並有 integration test。 |

### 尚未解決，且不能假裝已完成的項目

1. `source_files` 只有檔名與 signature，沒有 SP3 frame label、coverage 或 epoch
   metadata。跨 `IGb14`/`IGS20`/其他 transition 的長期比較尚不安全。
2. Q3 沒有確認 ESA 是否提供可用 per-epoch quality field；Q4 也還沒有用 residual
   分布校準。P1.4 尚未完成。
3. 直接對 osculating 半長軸做 spline 已觀察到不合理的導數；P1.5 不能發布，直到
   orbit-average/short-period 方法、參數選擇和 synthetic validation 完成。
4. `swarm_a_density` 目前以單一 `time_us` 作 primary key，且以檔名判斷是否已匯入。
   若 DNSAACC source file 有重疊 epoch 或同檔名更新，可能覆蓋或跳過資料。它不在
   P1.4-P1.7 核心範圍，先不要重建 1 GiB database；等 density 成為研究輸入時再做
   signature/provenance 與 key migration。
5. `swarm_a_pod_quality` 一列只能保存一個 `rejection_reason`。若 Q3/Q4 需要和既有
   Q1/Q5 同時保留，就新增 keyed-by-`time_us` 的 flag table，不能塞成逗號字串。
6. `ruff.toml` 已存在，但本機沒有 `ruff` executable。本次以 unittest、compileall
   與 `git diff --check` 驗證；lint 要在開發環境明確安裝後才可列為 gate。

## 驗證結果

```text
python -m unittest discover -s tests -v
14 tests passed

python -m compileall -q satellite_orbit tests
passed

git diff --check
passed
```

## 明天的起點

先看 `P1.4_TO_P1.7_EXECUTION_PLAN.md` 的「依賴與可平行工作」表。最安全的第一批
工作是 P1.4-C、P1.4-D 的 pure residual/sample audit、P1.5-A 的 synthetic/bin helper，
以及 P1.6-A 的 pure join tests；它們互不寫同一張 derived table。
