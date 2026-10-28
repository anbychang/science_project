# P1.6 特徵對齊

NOTE: 本文件原本描述 10-minute backward-rate branch；該 branch 是 retained legacy。現行
phase-harmonic v2 使用 `swarm_a_phase_harmonic_features_v2`：每個 usable 10-second
`time_us` 一列，供 raw B-L 與 joint H2/H3 兩張 rate table 共用，不複製四份 feature。
三年 feature table 有 9,469,438 rows；12 年 writer metadata 記錄 38,378,878 rows。
兩份 P1.7 v2 audit 各有 6 項、violation 全為 0；這不代表物理衰減率已校準。

欄位型態、最終分析 schema 與每個 feature 從原始來源到 P1.6 的完整追溯，見
`p1_6_analysis_schema.md`。

## 已完成範圍

以下 P1.6-A/B 的 12 小時與 10 分鐘內容是舊分支紀錄，不是現行 v2 feature
的 Input／Output。現行 feature 以 P1.5.6 v2 的 `time_us` 為 key，兩張 rate table 共用。

POD 的實際 native cadence 是每 10 秒，不是每 1 秒。舊分支由 P1.5 建立 10 分鐘列；
現行 P1.6 v2 對齊 P1.5.6 v2 的 10 秒 `time_us`。

## 已固定的對齊規則

| 特徵 | P1.6 輸出 | 來源規則 | 缺失規則 |
| --- | --- | --- | --- |
| SYM-H | `sym_h_nt` | exact minute；否則只在相鄰兩筆總 gap 不超過 2 分鐘時線性內插 | 缺一側或 gap 超過 2 分鐘即 `NULL` |
| Ap | `ap_now` | 取 target 所在 official 3-hour block | 沒有該 block 即 `NULL` |
| F10.7 | `f107_sfu` | 使用前一日值；`f107_source_time_us` 是前一日 UTC 00:00 | 前一日來源缺失即 `NULL` |
| F10.7A | `f107a_sfu` | 使用前一日 `F10.7_OBS_LAST81`；`f107a_source_time_us` 是前一日 UTC 00:00 | 前一日來源缺失即 `NULL` |

SYM-H 的 right endpoint 是唯一可能晚於 target 的 source time；它只可在兩分鐘內、且
左右 observation 都存在時使用。Ap、F10.7 與 F10.7A 的 source time 都必須不晚於
target。

原本 SQLite 的 `f107a_sfu` 是 `F10.7_OBS_CENTER81`。置中 81 日平均包含未來日期，
不能作為這份禁止 future leakage 的分析 feature。它保留給既有 NRLMSIS state；SQLite
新增 `f107a_last81_sfu` 保存 `F10.7_OBS_LAST81`，供 P1.6 使用。
[CelesTrak 格式文件](https://celestrak.org/SpaceData/SpaceWx-format.php) 將兩者分別定義為
centered 與 last 81-day arithmetic average。

## 來源盤點結果

| 資料 | 筆數 | UTC 範圍 | 可否覆蓋目前 POD |
| --- | ---: | --- | --- |
| POD | 14,558,400 | 2021-12-31 23:59:42 至 2026-08-12 23:59:32 | 研究輸入 |
| space weather | 201,861 | 1957-10-03 09:00:00 至 2026-11-02 21:00:00 | 可以 |
| SYM-H | 2,952,000 | 2021-01-01 00:00:00 至 2026-08-12 23:59:00 | 可以 |
| AE | 2,952,000 | 2021-01-01 00:00:00 至 2026-08-12 23:59:00 | 尚未列為正式 feature |

SYM-H 相鄰最大 gap 是 60 秒，沒有超過兩分鐘的 source gap，完整覆蓋本機 POD 範圍。

Swarm DNSAACC density 不是 P1.6 核心 feature，依第一階段規格維持獨立資料來源，沒有
強行 join。

## 已保存規則與驗證證據

- 本文件定義 exact/interpolation/gap、future source、02:59:59/03:00:00 Ap boundary 與
  F10.7 source time 的驗收規則。
- P1.6-B 已用這些規則寫入 final table，並完成 exact/interpolation/gap、Ap boundary 與前一日 solar source 的 contract tests。
- `research_workspace/phases/phase0/tests/test_load_space_weather.py`：驗證 raw CSV 的 trailing 81-day 欄位被保留。
- 已重建 `space_weather`：201,861 列都有 `f107a_last81_sfu`。
- WDC Kyoto 的 SYM-H 年度 query 曾在 2025-10-18 被截斷；下載器現在每次最多 180 天，
  並驗證 CSV 最後一筆確實到達 requested end date。

## 最終寫入結果

- `swarm_a_orbit_10min`：224,928 列；P1.6 不重算它的 orbit feature。
- `swarm_a_analysis_10min`：舊分支 224,280 列，保存 3/6/12 小時 rates，並排除每個連續 run 的前 72 列。
- `quality_flags`：226,367 列 `ok`、1 列 `missing_sym_h`；該列三個 SYM-H 欄位皆為 `NULL`，weather feature 完整。這是既定缺失契約，不可補未來 observation。
- P1.7 source-time audit：Ap、F10.7、F10.7A 沒有 future reference；SYM-H 亦沒有不合規 future reference。
- DNSAACC density 保持 raw `swarm_a_density`，不 join `swarm_a_analysis_10min`。
