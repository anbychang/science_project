# Swarm-A Orbit Project - Time Log

最後更新：2026-09-27

這份檔案是本專案的共同外部記憶。它記錄已確認的決策、已做過的事情、刻意不做的事情，避免之後重複討論或把測試資料誤當研究資料。

## 1. 合作方式與程式規則

- 用繁體中文，先講結論，再講原因。
- 解釋要非常白話；一次只處理一個觀念。
- 程式碼不是只要能跑，還要讓人一眼看懂。
- 不用壓縮寫法：不用 list comprehension、generator expression、巢狀函式、過度抽象的 class 或工具層。
- 函式名稱要說清楚物理意義與單位，例如 `position_m`、`velocity_m_s`、`a_dot_m_s`。
- 程式註解盡量使用簡單英文；真的無法說清楚時才使用中文。
- 英文使用常見單字與短句，重點是容易理解，不追求複雜文法。
- docstring 用短格式與括號表示資料，例如：

  ```python
  """Input: {orbital_response, weather_points}
  Output: [{time, a_mean_m, a_dot_m_s, sym_h_nT, ...}, ...]"""
  ```

- 不把「檢查用、驗證用、一次性實驗用」程式混進主程式。真的需要時再另外寫。
- 不要靠很多層資料夾假裝整理。應刪掉不必要的東西；保留的檔名要能直接說用途。
- 檔名前綴統一為四個字母：`calc_` 是計算、`down_` 是下載、`load_` 是讀取本機檔案、`prep_` 是建立整理後資料。

## 2. 目前研究目標

2026-09-27 定案：研究主題是「地磁暴如何影響 Swarm-A 軌道衰減」。

XYZ 軌道預報是後續驗證研究結果的工具，不是主要研究問題。通訊系統不在範圍內。

目前只做第一階段資料準備：POD 品質檢查、半長軸、衰減率、10 分鐘時間對齊與可重建的分析資料集。正式規格以 `plans/phase_1_data_preparation/PLAN.md` 為準。

機器學習的 target 尚未決定，不阻擋第一階段。

## 3. 資料來源：已確認的事實

### TLE、OEM、POD 的差別

- `TLE`：兩行平均軌道元素，給 SGP4 用。它是擬合過的簡化描述，不能當精密觀測真值。
- `OEM`：一種軌道檔案格式，不等於精密資料；裡面可能是預報、操作用軌跡或 POD。
- `POD`：由實際量測資料重建的高品質位置與速度序列，才適合當本研究的「觀測軌道」。
- 更原始的 GNSS／測距量測也可以用，但必須自己做軌道決定；目前不走這條路。

### Swarm-A 的正式資料

- 主資料：ESA `SP3ACOM_2_` reduced-dynamic POD。
- 每 10 秒一筆位置與速度，官方另有品質報告。
- 原始時間是 GPS time。SP3 header 跨越 `IGb14`、`IGS20`、`IGb20` 與 `IGc20`；舊 loader 統稱為 `ITRF` 只是暫時簡化，正式跨時段分析前必須保存真正 frame label。
- Kinematic 軌道只做後續比較；主資料不用它，因為主資料已直接提供速度。
- Swarm-A 有可協助理解非重力加速度與大氣阻力的公開科學資料；這是選它的主要優勢。

## 4. 座標、時間與單位：已定案

- 軌道流程只使用一種 state：`{time, frame, position_m, velocity_m_s}`。
- loader、座標轉換、力模型、RK4 與誤差計算之間只傳一個 state，不再分開傳 time、position、velocity。
- 二體重力與 J2 也接收完整 state；一致性比少傳幾個未使用欄位更重要。
- state 代表一個時間點的完整快照。F10.7、Ap 與大氣密度等會隨時間改變的資料可以直接加入 state；地球常數與衛星固定參數不放入。
- 大氣函式接收 GCRF state，內部計算衛星的地理位置，再回傳加入 `density_kg_m3` 的同一種 state。
- 原始 F10.7 與 Ap 使用 CelesTrak `SW-All.csv`，保存於 `data/space_weather/`，不修改內容。
- `load_space_weather(state)` 會加入 `f107_sfu`、`f107a_sfu`、7 個 `ap_values` 與 `f107_data_type`。
- NRLMSIS 的 F10.7 使用前一天觀測值；F10.7A 使用當天為中心的 81 日平均。
- 太空天氣下載器只在原始檔不存在時下載。loader 第一次使用時建立本機資料索引，之後所有 state 直接重用，不重掃 CSV，也不重新下載。
- 每個函式都必須用短 docstring 寫出 Input 與 Output；資料形狀優先用 `[]`、`{}` 與 `...` 畫出來，不用長句解釋。
- prepared data 採用單一 SQLite 檔案 `swarm_a_data.sqlite`，不再按月份切 CSV。
- `prep_write_sqlite.py` 將本機原始資料 insert／replace 進資料庫；相同 `time_us` 不會重複。
- 資料庫保留 ITRF POD，查出需要的短區間後才批次轉成 GCRF。
- `load_sqlite_states(start_time, end_time)` 只查需要的時間範圍，並回傳帶有 F10.7、F10.7A 與 Ap 的 ITRF `[state_1, state_2, ...]`；座標轉換在 calculation 層進行。
- 一段軌道資料是 `[state, state, ...]`，不使用 `{times: [...], states: [...]}`。
- `position_m = [x, y, z]`，`velocity_m_s = [vx, vy, vz]`；不用難讀的六維 `values[0]`。
- 半長軸等衍生時間序列仍使用一個時間一列的 row-based 格式。
- 主要座標系：`GCRF`。
- 主要時間：`UTC`。
- 位置與距離：`m`。
- 速度：`m/s`。
- 加速度：`m/s^2`。
- 角度：`rad`。
- 質量：`kg`。
- 面積：`m^2`。
- 大氣密度：`kg/m^3`。
- 原始 POD 的 `km` 與 `dm/s` 只在 loader 轉換一次；內部不再來回換單位。
- NRLMSIS 的接口要求角度使用 `deg`、高度使用 `km`，因此只在呼叫 pymsis 前由 `rad` 與 `altitude_m` 轉一次。
- F10.7 與 Ap 沒有一般 SI 替代，保留 NRLMSIS 規定的原生單位。
- 軌道狀態與 RK4 傳播使用 GCRF。
- Swarm-A 原始 POD 讀入時，必須先處理 GPS time 與 ITRF；不要假裝它原本就是 UTC／GCRF。
- J2、大氣阻力、POD 比較或地面位置需要時，暫時轉到 ITRF；算完加速度後再轉回 GCRF。
- 大氣模型需要經緯度高度時，由 ITRF 再轉成地理座標。
- `RTN` 只用來拆解位置誤差，不作為 RK4 主座標。
- GCRF／ITRF 狀態與向量轉換使用 Astropy，不自行簡化地球旋轉公式。
- Astropy 使用 IERS 資料處理歲差、章動、地球自轉與極移。
- 未來阻力公式中的 `v_rel` 是相對大氣速度，必須扣掉地球自轉造成的大氣速度；不能直接拿 `vx, vy, vz`。

## 5. 軌道反應訊號

舊方案使用約 90 分鐘 trailing average，再用相鄰點有限差分計算 `a_dot_m_s`。這個方案已被 2026-09-27 的第一階段計畫取代，只保留作歷史比較。

目前方案：先按資料 gap 與品質切成連續區間，建立 10 分鐘資料點，再在每個區間內獨立校準 B-spline 並由 spline 求導數。不可跨 gap、來源邊界或 maneuver candidate 平滑。

衰減率定義為 `decay_rate_m_day = -da_dt_m_s * 86400`；正值代表半長軸下降。細節以 `plans/phase_1_data_preparation/PLAN.md` 為準。

## 6. 地磁與太陽資料

- `SYM-H(t)`：主要地磁暴強度訊號。
- 是否使用 `d(SYM-H)/dt` 尚未決定；若需要，會由原始 SYM-H 計算，不另外下載。
- `AE(t)` 已下載並保存，但是否列為正式分析特徵尚未決定。
- `F10.7(t)`：太陽背景活動。
- `F10.7A(t)`：F10.7 的 81 日平均；不是 `F81`。
- Dst 可作為較長時間尺度的輔助資料，非主訊號。

軌道反應和太空天氣資料需要對到相同 UTC 時間點。官方 POD 為每 10 秒一筆；F10.7 為每日資料，Ap 為每三小時資料。

## 7. 大氣密度與後續模型

阻力加速度：

```text
a_drag = -0.5 * Cd * A / m * rho * |v_rel| * v_rel
```

舊方案曾考慮從 POD 與物理傳播反推 `C_rho`，再用 GPR 預測。這個方案已被「Swarm L2 密度與 NRLMSIS 獨立比較」的方向取代，不再是目前方法。

2026-09-19 已完成第一段大氣程式：

```text
ITRF [x, y, z]
-> WGS84 [longitude, latitude, altitude]
-> NRLMSIS 2.0
-> density_kg_m3
```

- 使用 `pymsis 0.12` 呼叫 NRLMSIS 2.0；程式明確指定 `version=2.0`，不使用預設的 2.1。
- NRLMSIS 輸入為 UTC、經度、緯度、高度、前一天 F10.7、81 日 F10.7A 與 Ap。
- 地磁暴模式使用 7 個 Ap 值：`[daily, now, -3h, -6h, -9h, avg_12_to_33h, avg_36_to_57h]`。
- `SYM-H` 與 `AE` 不直接輸入 NRLMSIS；它們保留給後續分析，機器學習方法與 target 尚未決定。
- 目前只完成密度計算，尚未把阻力加速度接進 `calc_forces.py` 或 RK4。
- 單點測試：2025-01-01、赤道、450 km、F10.7 = 150、F10.7A = 150、Ap = 4，得到約 `9.58e-13 kg/m^3`。這只是程式測試，不是真實研究資料。
- `data/swarm_density_acc/` 已有 61 個 Swarm-A `DNSAACC` 原始 ZIP：2024 年 5 月 31 天與 2025 年 11 月 30 天。
- 密度 ZIP 已有 `load_swarm_density.py`，並已寫入 SQLite；尚未和 NRLMSIS 比較。
- 未來機器學習的 target 暫緩決定。

## 8. 平滑方法的更新

- 114 小時平滑窗口遠大於想找的 1 到 6 小時延遲，會抹掉訊號，也可能製造假的時間偏移；不可用。
- 90 分鐘 trailing average 是舊方案，不再是正式方法。
- 新方案使用 10 分鐘資料點與分區間 B-spline；spline degree 與 smoothing strength 必須用資料校準，不先寫死。
- Swarm-A 的主資料採用 Reduced-dynamic POD；瞬時半長軸不是直接量到的 drag。

## 9. 資料保存與目前資料狀態

原則：

- 真實來源資料保存原始檔，不覆寫內容。
- 所有整理後資料放在單一 `swarm_a_data.sqlite`，可以隨時由原始資料重建。
- `time_us` 是 Unix microseconds 整數主鍵；再次執行只補新增或已改變的來源檔案。
- SQLite 保存在 SSD，但不提交 Git。
- 太空天氣涵蓋 1957 至 2026；Swarm-A 軌道只能涵蓋衛星發射後且本機已有 POD 的時段。

目前 `data/` 包含：

- `swarm_a_pod/`：ESA 原始 POD ZIP。
- `space_weather/SW-All.csv`：原始 F10.7 與 Ap。
- `geomagnetic/`：2024-05-09 至 2024-05-14 的原始 SYM-H 與 AE。
- `swarm_density_acc/`：Swarm-A `DNSAACC` 原始密度 ZIP。
- `swarm_a_data.sqlite`：單一整理結果，包含太空天氣表與 Swarm-A state 表。
- 已匯入 14,558,400 個 Swarm-A state，時間範圍為 2021-12-31 23:59:42 UTC 至 2026-08-12 23:59:32 UTC。
- 已整理 201,861 個三小時太空天氣區段，範圍由 1957 至 2026。
- SQLite 已有 8,640 個 geomagnetic 時間點；每點都有 SYM-H 與 AE。
- SQLite 有 436,708 個 Swarm DNSAACC density point，來自 61 個原始 ZIP。
- 舊的 `prepared_swarm_a_2025-01.csv` 已刪除；不再保留月檔。

## 10. 已刪除或刻意不保留的資料

舊的 ISS TLE 與暫時操作軌跡已移除；它們不屬於 Swarm-A 的正式 POD 資料。

舊的 ISS 假軌道與假太空天氣 CSV 也已移除；正式流程只保留官方原始資料與可重新產生的 SQLite。

也不保留主套件內的驗證腳本與 Python cache。

## 11. 現有程式結構

```text
satellite_orbit/
  data/
    down_swarm_pod.py               下載 Swarm-A POD 原始檔
    down_space_weather.py           下載原始 F10.7 與 Ap
    down_geomagnetic.py             下載原始 SYM-H 與 AE
    load_swarm_pod.py               讀取本機 Swarm-A POD ZIP
    load_space_weather.py           從本機原始檔取得 F10.7 與 Ap
    load_geomagnetic.py             讀取本機 SYM-H 或 AE CSV
    load_swarm_density.py           讀取本機 DNSAACC density ZIP
    load_sqlite_states.py           依 UTC 範圍查詢並組成 ITRF states
    prep_write_sqlite.py            依序更新單一 SQLite 資料庫
    prep_sqlite_common.py           共用時間與檔案資訊工具
    prep_sqlite_tables.py           建立 SQLite tables
    prep_sqlite_weather.py          寫入 F10.7 與 Ap
    prep_sqlite_sym_h.py            寫入 SYM-H
    prep_sqlite_ae.py               寫入 AE
    prep_sqlite_pod.py              寫入 POD 軌道 state
    prep_sqlite_density.py          寫入 DNSAACC density
    prep_write_orbital_elements.py  計算並寫入瞬時半長軸
  calculation/
    calc_coordinates.py             GCRF／ITRF 狀態與向量轉換
    calc_atmosphere.py              NRLMSIS 2.0 大氣密度
    calc_time.py                    GPS time 轉 UTC
    calc_forces.py                  二體重力、J2 與狀態導數
    calc_integrator.py              fourth-order Runge-Kutta（RK4）傳播
    calc_position_error.py          計算預測位置與官方位置的距離
    calc_orbital_response.py        從一個 GCRF state 計算瞬時半長軸
data/
  swarm_a_pod/                      Swarm-A 官方 POD
  space_weather/                    原始 F10.7 與 Ap
  geomagnetic/                      原始 SYM-H 與 AE
  swarm_a_data.sqlite               全部整理資料，不提交 Git
README.md
AGENTS.md
TIMELOG.md
```

歷史上曾用官方 POD 跑通以下位置誤差測試：

```text
依時間讀取 prepared ITRF states 並轉成 GCRF
-> 取出起點與未來官方位置
-> 二體重力 + J2 + RK4
-> 與未來官方 POD 比較位置誤差
```

歷史測試結果：

```text
起點：2025-01-01 00:00:02 UTC
模型：二體重力 + J2 + RK4
步長：10 秒
預測：10 分鐘
位置誤差：29.295 m
```

2026-09-27 決定正式退休並刪除 `main_pod_error.py`。以上數字只保留為歷史記錄；目前沒有正式指令入口可直接重跑。

RK4 是目前唯一保留的數值積分器。Euler step 原本只為比較 RK4 與 Euler 而存在，現在已移除。也已移除 `make_derivative` 這類函式內函式的寫法。

## 12. 目前需要注意的檔案

- `plans/phase_1_data_preparation/PLAN.md` 是第一階段唯一正式規格。
- `plans/phase_1_data_preparation/archive/RESEARCH_PLAN.md` 是外部提案快照，不代表目前決策或已完成結果。
- 舊的 CSV、ISS OEM、reboost 讀取程式與 `main_pod_error.py` 已移除。

## 13. Git

- 2026-09-15：建立本機 Git repository。
- 2026-09-15：已建立私有 GitHub repository：`https://github.com/anbychang/science_project`。
- `master` 已連到 `origin/master`；目前沒有未推送 commit，但有尚未提交的文件與資料夾重組。

## 14. 下一步，尚未做

依 `plans/phase_1_data_preparation/PLAN.md`：

1. audit POD coverage、native cadence、gap 與 SP3 frame label。
2. 實作半長軸品質檢查與 continuous interval。
3. 建立 10 分鐘 bin 與 B-spline derivative。
4. 對齊 SYM-H、Ap 與 F10.7，保留 source timestamp。
5. 發布可重建的第一階段衍生資料集與 metadata。

Swarm 密度 loader 與獨立密度比較可平行準備，但不應混進第一階段的核心產物。

## 15. 2026-09-28 P1.4 至 P1.7 交接

- `plans/phase_1_data_preparation/P1.4_TO_P1.7_EXECUTION_PLAN.md` 是明天執行
  P1.4 至 P1.7 的工作拆分；先做 P1.4-C/D、P1.5-A、P1.6-A 的獨立準備，P1.5 正式
  smoothing 必須等待 short-period 方法決定。
- P1.5/P1.7 的欄位已統一：`da_dt_smooth_m_s` 與
  `decay_rate_smooth_m_day`；F10.7 與 F10.7A 要分別保存 source time。
- `swarm_a_pod_quality` 可安全 rebuild，並不會修改 raw POD；RK4 會保留 state 的
  額外 weather/atmosphere 欄位。
- 仍未完成：SP3 frame inventory、Q3/Q4 校準、P1.5 short-period 處理、P1.6 join、
  P1.7 release。詳情見 `CHANGE_REPORT_2026-09-28.md`。

## 多 chat 協作規則

當同一件工作由多個 chat 同時處理時：

```text
主 chat：討論方向、做最後決策
工作 chat：執行一個明確的小任務
TIMELOG.md：共同的決策與目前事實
Git：每次完成後保存版本
```

- 只能有一個主 chat 負責最後決策。
- 不同 chat 不可同時修改同一個檔案。
- 重要決策只寫進 `TIMELOG.md`，不要只留在聊天裡。
- 完成一件事就 commit；下一個 chat 開始前先讀 `TIMELOG.md` 與最新 Git 狀態。
- 需要交接時，只傳「做了什麼、改了什麼、下一步是什麼」的短摘要，不轉貼整段聊天。
