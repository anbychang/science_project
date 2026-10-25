# Phase 2 最終整理

## 狀態

Phase 2 資料準備於 2026-10-24 完成並固定。交付物是三年 pilot 的可追溯一分鐘分析資料、25 場磁暴的描述性 peak QC，以及每場一張檢查圖。此階段不再改動；新研究方法須另立工作，不覆寫本次檢查點。

「完成」指資料與 QC 契約已產出且通過下列檢查，不表示已證明 SME 到密度的因果延遲或 Swarm-A 真實軌道衰減。正式方法見[計畫](PLAN.md)與[方法報告](PHASE_2_SME_REPORT.md)，逐步來源鍵與範例見[資料血緣](../../data_lineage/phase_2_storm_dataset.md)。

## 範圍與固定流程

來源涵蓋 2023-07-01 至 2026-06-30 UTC。現行事件分鐘實際範圍是 2023-08-03T05:02:00Z 至 2026-04-22T07:59:00Z。Phase 1 的 10 秒軌道結果只用來對齊相位與既有 rate；Phase 2 不重算 Phase 1，也不把密度接入 propagator。

```text
SME／SYM-H／ap／CelesTrak + Phase 1 軌道 + DNSAPOD
  -> P2.0 source audit -> P2.1 一分鐘地磁 -> P2.2 事件
  -> P2.3 v5 同相位分鐘特徵 -> P2.4 v5 L2／MSIS 配對
  -> P2.5 v2 一分鐘分析 view -> P2.6 final 平滑 peak QC
  -> output/image/Phase2/P2.6/YYYY-MM-DD.png（25 張）
```

P2.3 依 raw SYM-H 最低點 `t0` 的軌道相位，保留前 31、後 62 圈的分鐘資料；這是資料保存窗。P2.6 的 peak 候選窗另固定為 `t0 - 12 h` 至 `t0 + 24 h` 的閉區間，不從完整事件窗選峰。等值最大值取較早分鐘，不依預期先後順序手動改配。

F10.7A 直接取樣本當日 CelesTrak `F10.7_OBS_CENTER81`，不自行平均前 81 日。每日 F10.7 仍取前一 UTC 日；只接受 `OBS`／`INT`，不用 `PRD`／`PRM`。SME 採 15-minute centered mean；密度殘差 `log_ratio_obs = ln(rho_l2 / rho_msis)` 採 `u_rel_rad +/- pi` 的 centered one-orbit mean。平滑窗口須完整且有效值比例 >= 80%；`t0` 保持 raw SYM-H 最低點。來源置中 81 日與 centered smoothing 都含未來觀測，只適用離線回溯；Phase 1 P1.6 的 trailing feature 未更改。

## 唯一現行檢查點

以下檔案位於 `data/sqlite/2023/`。每步複製上游 SQLite，新增衍生 table 或 view；raw observation 不更新。舊版衍生 SQLite 已退出工作區，不是替代輸入。

| 步驟 | 檔案 | SHA-256 | 主結果 |
| --- | --- | --- | --- |
| P2.0 | `swarm_a_phase2_sme_p2_0_v2.sqlite` | `5b6261af40f00ac2b0f3f70af1965b497f46bf1b9e4e7511e1f28d3c003ddf10` | 來源稽核 1 列 |
| P2.1 | `swarm_a_phase2_sme_p2_1_v2.sqlite` | `9e2aad566d1fb75ead1974351ff3f9ac438474f633d1de98148c97778100ffdd` | 一分鐘地磁 1,578,240 列 |
| P2.2 | `swarm_a_phase2_sme_p2_2_v2.sqlite` | `55e726b9bbf2bd0469e1f316bf2b81d80a05b752ea0b950ecaff56efb2585eb7` | 25 場事件 |
| P2.3 | `swarm_a_phase2_sme_p2_3_t0_phase_v5.sqlite` | `1dc9034ecb781a9bf444f95f7f8c401e7166615d0c7faa4ab19e8eac7a846a89` | 分鐘特徵 217,912 列 |
| P2.4 | `swarm_a_phase2_sme_p2_4_density_t0_phase_v5.sqlite` | `5f5423b426ec0bd556f9e8f7378135b59ce9d3a1ae60f82f332f5b0e17493e7e` | 配對密度 217,912 列；coverage 25 列 |
| P2.5 | `swarm_a_phase2_sme_p2_5_minute_analysis_v2.sqlite` | `fbabfaab3035fab2301e7da55d720692ec9659a210b9aa7949d74c616de9c0cd` | `storm_minute_analysis_v2` 217,912 列 |
| P2.6 | `swarm_a_phase2_sme_p2_6_final.sqlite` | `ab49465ab672d98dd513c1169cb37c6fcb4488b98cade7b6ed66b151398c30de` | `storm_minute_smooth_v4` 54,025 列；`storm_minute_peak_qc_v4` 25 列 |

P2.5 的 `log_ratio_obs` 有 217,613 筆非 NULL。P2.6 的 54,025 筆候選分鐘中，SME 平滑值全部有效，密度平滑值有 53,700 筆有效。25 場中，16 場 SME peak 早於密度 peak，9 場相反；反序列照實保留。

## 圖與重現

`output/image/Phase2/P2.6/` 直接保存 25 張 `YYYY-MM-DD.png`，一場一張，沒有版本子目錄或舊圖。每張顯示 SME、密度殘差與 SYM-H 三個 panel 的 raw／smoothed 曲線；數值以 P2.6 SQLite 為準，圖不是另一份資料產品。繪圖入口：

```powershell
python -m output.report.prep_phase2_smoothed_candidate_figures
```

此入口只適用圖檔尚未存在的新工作區；若目標已有任一同名圖，會拒絕覆寫。需要重繪檢查時，呼叫 `draw_figures(output_directory=...)` 指向新的暫存目錄，不改封存圖。

資料寫入入口依序位於 `satellite_orbit/phase2/prep_20_source_checkpoint.py`、`prep_21_geomag_1min.py`、`prep_22_storm_event.py`、`prep_23_t0_phase_window.py`、`prep_24_density_t0_phase.py`、`prep_25_minute_analysis.py`、`prep_26_smoothed_peak_qc.py`。P2.0 的來源 JSON 由 `prep_20_source_audit.py` 產生。現行 writer 遇到既有 output 會拒絕覆寫；重建須另選輸出路徑，不能改寫封存檢查點。原始 CSV／ZIP 及 Phase 1 輸入保留原位。

## 驗證證據

- 7 個現行 SQLite 的 SHA-256 均與上表相符；`integrity_check = ok`，foreign key 違規均為 0。
- P2.0–P2.6 及 MSIS 相關測試 22 項通過。
- 25 張圖的 UTC 日期與 `storm_minute_peak_qc_v4` 的 25 場事件一一對應；無缺圖、重複日期或額外圖檔。
- P2.6 metadata 記錄上游 P2.5 SHA-256、平滑規則、80% 有效門檻及 `[-12,24]` 小時候選窗。
- 現行圖目錄已有檔案時，繪圖入口拒絕覆寫；7 個資料 writer 同樣拒絕覆寫既有檢查點。
- 研究文件的本機連結及現行程式路徑已核對；舊 SYM-H 單來源與舊合併事件 writer 及其測試已移至 Windows 資源回收筒，可復原，不屬現行鏈。

## 未宣稱的結果

25 場中 24 場標為複合事件。P2.6 在限定候選窗取兩條平滑序列各自的全域最大值，可能把不同 pulse 配成一對；9 場反序不能直接解讀成負延遲。SuperMAG `tval` 的分鐘區間位置仍採工作假設。密度比較尚未消除 POD 共同來源、產品高度基準及機動等系統誤差。

本階段沒有 local pulse pairing、因果延遲模型、已校準的軌道衰減標籤、GPR、12 年擴充或 drag propagator。這些不列為 Phase 2 未完成項；若未來要做，應另立工作與新輸出，不回寫本次結果。歷史演進只見[TIMELOG](../../TIMELOG.md)，不作現行操作指引。
