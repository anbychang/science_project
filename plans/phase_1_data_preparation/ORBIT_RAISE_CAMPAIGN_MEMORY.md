# Swarm-A orbit-raise evidence memory

## 決定

這是 Phase 1 對 Swarm-A 半長軸上升與 orbit maneuver 證據的唯一集中記錄，不只是
campaign 日期表。它要同時記住官方 campaign、已檢查的觀測上升時段，以及尚未能確認的
證據邊界。P1.4 的 `OFFICIAL_SWARM_A_ORBIT_EVENTS` 必須與本頁官方事件表完全一致。
原始 POD 保留；所有官方 event 區間內 state 不得用於自然軌道衰減或
geomagnetic-storm response。

時間規則一律是 UTC half-open interval：`[start, stop)`。

## 已確認 campaign

| ID | UTC exclusion interval | 影響衛星 | 官方可支持的事實 | maneuver 細節可得性 | 主要證據 |
| --- | --- | --- | --- | --- | --- |
| `SWA_C_ORBIT_RAISE_2022` | `[2022-05-03T00:00:00Z, 2022-07-09T00:00:00Z)` | A/C | A/C orbit-raise campaign；目標高度提升 `45 km`。 | ESA 報導提及 10 週內各 25 次；沒有本專案使用的逐次 UTC log。 | [ESA 2022-07-14](https://www.esa.int/Space_Safety/Swarm_dodges_collision_during_climb_to_escape_Sun_s_wrath)；[NASA ILRS mission news](https://ilrs.gsfc.nasa.gov/missions/satellite_missions/Mission_News.html) |
| `SWA_C_ORBIT_RAISE_2023_PHASE_II` | `[2023-04-26T00:00:00Z, 2023-06-08T00:00:00Z)` | A/C | orbit-raise campaign Phase II。 | 沒有公開逐次 UTC log。 | [ESA campaign notice](https://earth.esa.int/eogateway/news/swarm-alpha-and-charlie-orbit-raise-campaign-starting-on-26-april-2023-potential-impact-on-data-quality) |
| `SWA_C_ORBIT_RAISE_2026` | `[2026-07-21T00:00:00Z, 2026-08-01T00:00:00Z)` | A/C | A 有 4 次 maneuver；C 有 2 次 long-duration maneuver；兩星各約抬升 `5 km`。目的為降低 solar-maximum drag 下的過早 re-entry 風險。 | 沒有每次 UTC、burn duration、direction、delta-v 或逐次高度增量。 | [ESA QRAS Week 30 L1B report](https://ftp-qras.earth.esa.int/swarm/swarm_instruments/weekly/2026/swarm--swarm_instruments--weekly--20260720--l1b.pdf), p. 7 |

## 已確認的單日 maneuver

| ID | kind | UTC exclusion interval | 官方可支持的事實 | 主要證據 |
| --- | --- | --- | --- | --- |
| `SWA_ORBIT_CONTROL_2022-01-13` | `orbit_control_manoeuvre` | `[2022-01-13T00:00:00Z, 2022-01-14T00:00:00Z)` | Swarm-A 在 1/13 執行 orbit-control manoeuvre。沒有公開 burn UTC 或 delta-v。 | [ESA-prepared CGMS report, p. 18](https://www.cgms-info.org/Agendas/GetWpFile.ashx?aid=4fafae3c-cc18-435d-a9c9-d82d0d036fe5&wid=dfc681dd-16f6-41a0-a923-c854e330489c) |
| `SWA_CAM_2023-01-06` | `collision_avoidance_manoeuvre` | `[2023-01-06T00:00:00Z, 2023-01-07T00:00:00Z)` | Swarm-A/C 各於 1/6 執行一次 CAM。沒有公開 burn UTC 或 delta-v。 | [ESA-prepared CGMS report, p. 14](https://www.cgms-info.org/Agendas/GetWpFile.ashx?aid=4d8a2caa-2bbf-44a8-8723-a5847e1b1ce5&wid=dfc681dd-16f6-41a0-a923-c854e330489c) |

## 已檢查的觀測上升時段

下表不是逐次 firing log。它保留每一次實際被本研究檢查過的半長軸上升或異常結構，
避免日後只記住 campaign 名稱、遺失觀測問題。

| ID | observation UTC | 數據層 | 判定 | 與官方 campaign 的關係 | 不可聲稱的事 |
| --- | --- | --- | --- | --- | --- |
| `SWA_OBS_2023-05-09_0520_0620` | `2023-05-09T05:20:00Z..06:20:00Z` | SP3ACOM `0203` 的 raw state / instantaneous semi-major axis 檢查 | 已檢查的 POD structure；個別 maneuver 與 POD quality 均為 `unknown`。 | 位於 `SWA_C_ORBIT_RAISE_2023_PHASE_II`。 | 不可把 HDR `Product_Err=0`、`Quality_Indicator=000` 或檔案連續性解讀成沒有 maneuver 或 epoch-level quality pass。 |
| `SWA_OBS_2026-07-21_2026-07-23` | `2026-07-21T00:00:00Z..2026-07-24T00:00:00Z` | 10-minute semi-major-axis inspection | 多日上跳；campaign 本身已由官方確認。 | 位於 `SWA_C_ORBIT_RAISE_2026`。 | 不可把每一個 10-minute 上跳配對成官方已知 firing；週報沒有逐次 UTC。 |

## 數值資料的唯一位置

不把每一筆 POD 數值複製進 Markdown。這會造成第二份不會同步的資料。數值記錄保持在
SQLite，這份 memory 只保存可追溯的索引與判定：

```text
swarm_a_states + swarm_a_orbital_elements
  -> all raw-time instantaneous semi-major-axis observations,
     including campaign dates

swarm_a_orbit_decay_10min
  -> accepted non-campaign 3h/6h/12h comparisons;
     da_dt_Hh_backward_m_s < 0 means a(t) > a(t - Hh)
```

campaign rows 不會出現在第二張表，這是刻意的品質排除，不是資料遺失。若要為某個
campaign 產生可引用的數值 uplift ledger，必須從第一條 raw 軌跡另建 diagnostic export，
清楚標成 `instantaneous` 或獨立算出的 `mean-orbit`；不能把已排除的 row 偷放回 Phase 1
自然衰減資料集。

## 2026 附帶資料品質資訊

這些訊息不能改寫成 `SP3ACOM` POD error：

- `2026-07-22T02:13:59Z..02:14:05Z`：Swarm-A missing telemetry，all instruments affected。
- campaign 期間，attitude-control errors *may* affect L1B/L2 quality；A/C along-track separation 可達 `85..90 s`。
- Swarm-A VFM--ASM alert 在 `7/21..23`；這是 magnetic product evidence，不是 precise orbit validation。
- QRAS 報告的 orbit check 是 `MODx_SC_1B` 與 `GPSxNAV_0`；`SP3ACOM` quality 仍需獨立 `SP3xVAL_2_`。

## 使用規則

```text
official Swarm-A orbit event
  -> add {id, kind, [start, stop)} to P1.4 event table
  -> regression-test start and stop boundaries
  -> rebuild quality -> mean orbit -> 10-minute -> backward 3h/6h/12h -> analysis -> P1.7
  -> update row counts, chunks, and release manifest

observed uplift / anomaly review
  -> append one observation record above
  -> link exact source, observation interval, numerical layer, and evidence status
  -> keep it separate from official maneuver confirmation
```

- 不可把 campaign 或單日 maneuver window 內每個 10 分鐘上跳叫作已知 firing。
- 不可由沒有公告推出沒有 maneuver。
- campaign 外的 candidate 維持 Q4 audit-only，除非新增可查核的官方證據。

## 來源筆記

- [2022--2023 campaign research](RESEARCH_2022_2023_ORBIT_RAISE_CAMPAIGNS.md)
- [2026 campaign research](RESEARCH_2026-07_SWARM_A_SEMIMAJOR_AXIS_ANOMALY.md)
- [完整操作 catalog 稽核](RESEARCH_SWARM_A_ORBIT_RAISE_CATALOG_AUDIT.md)
- [P1.4 quality policy](P1.4_QUALITY_CONTROL.md)
