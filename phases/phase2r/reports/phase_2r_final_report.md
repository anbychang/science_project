# Phase 2R 12 年同方法重現最終報告

## 狀態

Phase 2R 於 2026-10-25 完成並固定。它不是新科學方法，而是把 Phase 2 final
相同的事件、相位、密度、平滑與 peak QC 套用到 12 年範圍，並把連續
`chunk_id` 明定為可稽核的資料完整性邊界。
Phase 2 的 7 個 checkpoint hash 全部不變。

範圍：`2014-07-01T00:00:00Z <= time < 2026-07-01T00:00:00Z`。實際入選事件分鐘範圍是
2015-01-05 10:33 UTC 至 2026-04-22 07:59 UTC。逐步資料契約與可查回範例見
[Phase 2R lineage](../docs/lineage/phase_2r_12year_replication.md)。

## 固定方法

- SYM-H `< -100 nT` local minima，72 小時內合併。
- `t0` 前 31 圈、後 62 圈的同相位分鐘窗。
- F10.7 取前一 UTC 日；F10.7A 取當日 `F10.7_OBS_CENTER81`。
- DNSAPOD 30 秒樣本與 NRLMSIS 2.0 使用同位置、同時間配對。
- L2 coverage 與 L2／MSIS paired coverage 各自 `>= 80%`。
- SME 15-minute centered mean；density residual 用 `u_rel_rad +/- pi` centered one-orbit mean。
- peak 候選窗固定為 `t0 - 12 h` 至 `t0 + 24 h`；同值取較早分鐘。

P2R.3 多了一個必要的資料邊界顯式化：事件只能用包含 `t0` 的單一連續
Phase 1 `chunk_id`。不跨缺口或機動分段；前 31 圈或後 62 圈不足就排除。
這沒有改變物理窗口，只是讓三年 pilot 未觸發的連續性前提可稽核。

## 結果

- P2R.0：4,383 天，6,311,520 個分鐘格。SYM-H 與 AE 無缺分鐘。
- SME：6,232,475 個有效分鐘；79,045 個來源填充分鐘保留為缺值。
- P2R.2：2,461 個 local minima 合併為 49 場，46 場 `compound = 1`。
- P2R.3：46 場、400,696 個分鐘 key。3 場因 Phase 1 連續相位不足排除。
- P2R.4：324 個 DNSAPOD 日檔、933,120 個 30 秒樣本。weather 與 MSIS 缺值都是 0。
- 46 場全數通過兩個 80% coverage 門檻；最低 coverage 是 0.9344902885。
- P2R.5：400,696 列，P2R.3／P2R.4 minute key mismatch 雙向都是 0。
- P2R.6：99,406 個候選分鐘；density smoothing 有效 98,946 列。
- 46 場中 33 場 SME peak 較早，13 場反序；反序照實保留。

排除的三場是：

| storm_id | t0 UTC | 原因 |
| --- | --- | --- |
| `S20220114T2217` | 2022-01-14 22:17 | t0 前 31 圈不足 |
| `S20230424T0403` | 2023-04-24 04:03 | t0 後 62 圈不足 |
| `S20230506T0511` | 2023-05-06 05:11 | t0 沒有連續 Phase 1 相位 |

## 固定檢查點

以下檔案位於 `phases/phase2r/data/sqlite/`。SQLite 不上傳 Git；程式、資料契約與 hash 可以上傳。

| 步驟 | 檔案 | SHA-256 | 主結果 |
| --- | --- | --- | --- |
| P2R.0 | `swarm_a_phase2r_p2r_0_source_v1.sqlite` | `db72986f74f27450044c925c652d75cc701e7553908ef3a9e5b5f27c13d067d8` | 來源 audit 1 列 |
| P2R.1 | `swarm_a_phase2r_p2r_1_geomag_v1.sqlite` | `723439b466da2dd7ff601d325b15e20a24c816101b129a569b147be97abea87e` | 6,311,520 分鐘 |
| P2R.2 | `swarm_a_phase2r_p2r_2_storms_v1.sqlite` | `4d3d2d00da0a962576448a19e0c55456d32f86543c0ab6cbb6781182509b055f` | 49 場候選 |
| P2R.3 | `swarm_a_phase2r_p2r_3_t0_phase_v1.sqlite` | `b5d37b2f03dcc393df1fc46e40814899e62d2ee287fc8e33a68b4b1b9ab48b20` | 46 場；400,696 分鐘；排除 3 場 |
| P2R.4 | `swarm_a_phase2r_p2r_4_density_v1.sqlite` | `3a0c5ffb103808b521cd480401c99bc935376fe07e125503e42a4bf3034143b9` | density 400,696 列 |
| P2R.5 | `swarm_a_phase2r_p2r_5_minute_analysis_v1.sqlite` | `2eb117bd77af53d90f34d120db25fae770a89e69f8e6423189a97a530f3e4448` | analysis view 400,696 列 |
| P2R.6 | `swarm_a_phase2r_p2r_6_final_v1.sqlite` | `d201583de003713a28f9fd1276d33ac45ea247af5e0634d7c3f608115b43c42e` | smooth 99,406 列；QC 46 列 |

## 圖與重現

`phases/phase2r/figures/P2R.6/` 有 46 張 `YYYY-MM-DD.png`，與 QC 事件 UTC 日期一對一。
圖與數值來自 P2R.6，繪圖入口為：

```powershell
python -m phases.phase2r.code.prep_phase2r_smoothed_candidate_figures
```

完整重建順序與明確輸出路徑見[PLAN](../docs/plans/PLAN.md)。每個 writer 在目標存在時都拒絕覆寫。

## 驗證

- 7 個 Phase 2R SQLite：`integrity_check = ok`，foreign key violation 為 0。
- 結案當時全專案 pytest：200 passed。Orekit／JVM 在 Windows 印出 access-violation 診斷，
  但 pytest exit code 為 0；這是已知環境警告，不應被隱藏。
- 46 張圖與 46 場 QC 日期一對一；無缺圖、重複日期或額外圖。
- Phase 2 七個已封存 checkpoint 的 SHA-256 重新核對，7／7 與 Phase 2 final report 一致。

## 科學界線

Phase 2R 證明同一資料契約可以擴充到 12 年，不證明 SME 與 density peak 是同一 pulse。
49 場中 46 場是 compound；13 場反序不可解讀為負物理延遲。SME 在 2026-05-08 至
2026-06-30 全是來源填充值，但入選事件分鐘最晚只到 2026-04-22，未影響本次 46 場。

本階段沒有 local pulse pairing、因果 delay kernel、已校準的軌道衰減標籤、GPR 或 drag propagator。
這些必須使用新 phase 與新輸出，不回寫 Phase 2 或 Phase 2R。
