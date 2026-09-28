# Swarm-A 軌道衰減研究

本專案研究地磁暴如何影響 Swarm-A 的軌道衰減。XYZ 軌道預報是後續驗證工具，不是主要研究問題。

目前只進行第一階段：建立可重建、每 10 分鐘一列的分析資料集。正式規格見 [第一階段計畫](plans/phase_1_data_preparation/PLAN.md)。

## 結構

```text
satellite_orbit/
├─ data/           下載、讀取、SQLite 寫入
└─ calculation/    座標與物理計算

data/              原始資料與 SQLite 工作資料庫
plans/             現行計畫與封存提案
```

## 資料流程

```text
下載檔案
    -> load_*.py 讀取本機檔案
    -> prep_write_sqlite.py 寫入 raw SQLite
    -> load_sqlite_states.py 讀出 ITRF state
    -> calc_coordinates.py 轉成 GCRF state
    -> prep_write_orbital_elements.py 計算半長軸並寫回 SQLite
    -> prep_write_pod_quality.py 建立品質標記與連續 interval
```

`prep_write_sqlite.py` 只負責依序呼叫其他小檔案。weather、SYM-H、AE、POD、density 的 SQLite 寫入各自放在獨立檔案。

原始 SQLite table 不會被後續計算修改。新的計算一律讀取 raw table、建立自己的 derived table，再以相同的 `time_us` 保留可追溯關係。

## 軌道 state

```text
state = {
    time,
    frame,
    position_m: [x, y, z],
    velocity_m_s: [vx, vy, vz],

    # Added when the atmosphere is needed:
    f107_sfu,
    f107a_sfu,
    ap_values,
    f107_data_type,
    density_kg_m3,
}
```

- 函式之間只傳一個 `state`，不拆開傳時間、位置與速度。
- 一段軌道是 `[state, state, ...]`。
- 專案內部使用 SI 單位與 UTC。
- 主要計算座標系是 GCRF。
- 原始 POD 的實際 reference frame 必須從 SP3 header 保存，不能永遠只標成泛稱的 ITRF。

## 目前資料

```text
Swarm-A POD             已下載並寫入 SQLite
F10.7 / Ap              已下載並寫入 SQLite
SYM-H / AE              已下載 2021-01-01 至 2026-08-12，並寫入 SQLite
Swarm-A DNSAACC 密度    已由 loader 寫入 SQLite
```

## 建立 SQLite

```powershell
python -m satellite_orbit.data.prep_write_sqlite
```

輸出為 `data/swarm_a_data.sqlite`。原始資料保留不變；SQLite 可以由原始檔重新建立，因此不提交 Git。

## 目前限制

- 10 分鐘衍生資料集尚未完成。
- P1.4 的基本品質標記與連續 interval 已實作；ESA quality flag 與 maneuver
  candidate 規則尚待 audit、校準。
- P1.5 的 orbit-average、smoothing 與衰減率尚未實作；不可直接對 osculating
  semi-major axis 發布衰減率。
- Swarm-A 密度尚未加入軌道 state 或最終 10 分鐘資料集。
- NRLMSIS 2.0 可以計算密度，但大氣阻力尚未接進 RK4。
- `main_pod_error.py` 已正式退休，不再是專案入口。

P1.4 至 P1.7 的可執行工作拆分見
[執行計畫](plans/phase_1_data_preparation/P1.4_TO_P1.7_EXECUTION_PLAN.md)。
