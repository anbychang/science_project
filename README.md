# Swarm-A 軌道衰減研究

目標：研究地磁暴與 Swarm-A 軌道衰減的關係。

目前範圍：可重建的 10 分鐘分析資料集。XYZ 預報、machine learning、drag propagator 均不在此階段。

正式規格：[第一階段計畫](plans/phase_1_data_preparation/PLAN.md)。

## 專案地圖

```text
satellite_orbit/
├─ data/          [下載 | 讀取 | SQLite]
└─ calculation/   [座標 | 物理 | 數值]

data/
├─ swarm_a_pod/        raw POD ZIP
├─ geomagnetic/        raw SYM-H / AE CSV
├─ space_weather/      raw F10.7 / Ap CSV
├─ swarm_density_acc/  raw DNSAACC density ZIP；目前不進主分析
└─ swarm_a_data.sqlite 可重建的 working database；含 raw 與 derived table

plans/            現行規格、階段證據與歷史報告
```

## 資料流

```text
[raw files]
  -> [raw SQLite]
  -> [GCRF + orbital elements]
  -> [quality + continuous intervals]
  -> [10-minute orbit]
  -> [analysis features]
```

| 前綴 / 模組 | 責任 |
| --- | --- |
| `load_*` | 讀取本機檔案或 SQLite |
| `down_*` | 下載來源資料 |
| `prep_raw_*` | 原始資料寫入 raw table |
| `prep_derived_*` | raw table 產生 derived table |
| `calc_*` | 物理與數值計算 |

raw table 不可修改。每個 calculation 建立自己的 derived table，以原始 `time_us` 追溯來源。

## 共用資料形狀

```text
state = {
  time, frame,
  position_m: [x, y, z],
  velocity_m_s: [vx, vy, vz],
  ...space_weather_or_density,
}

orbit_series = [state, ...]
```

`state` 不拆成時間、位置、速度三組參數。內部單位是 SI；時間是 UTC；主要計算 frame 是 GCRF。

## 現況

| 資料 / 階段 | 狀態 |
| --- | --- |
| POD、F10.7、Ap、SYM-H、AE | 已寫入 SQLite |
| P1.4 基本 QC、interval | 已完成；Q3/Q4 待校準 |
| P1.5 orbit-average、衰減率 | 未完成；不可直接用 osculating 半長軸推估 |
| P1.6 最終 join | 等待 P1.5 schema |
| DNSAACC density | 已保存；不是 P1.6 core feature |
| NRLMSIS 2.0 | 可算密度；未接入 RK4 |

## 重建 raw SQLite

```powershell
python -m satellite_orbit.data.prep_raw_database
```

輸出：`data/swarm_a_data.sqlite`。可由原始檔重建，不提交 Git。

下一步拆分與停止條件：[P1.4 至 P1.7 執行計畫](plans/phase_1_data_preparation/P1.4_TO_P1.7_EXECUTION_PLAN.md)。

資料血緣入口：[Phase 1 data lineage](plans/phase_1_data_preparation/data_lineage/README.md)。
