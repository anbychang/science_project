# 第二階段計畫：SME 與密度分鐘資料

## 結案決定 [done]

Phase 2 於 2026-10-24 完成並固定。三年 pilot 的交付鏈是 P2.0–P2.2、P2.3 v5、P2.4 v5、P2.5 v2、P2.6 final；不再修改本階段方法或覆寫檢查點。交付的是可重現的一分鐘分析資料與描述性 peak QC，不是因果延遲或軌道衰減標籤。交付結果見[最終報告](PHASE_2_FINAL_REPORT.md)，各步驟 Input／Output 見[資料血緣](../../data_lineage/phase_2_storm_dataset.md)。

```text
原始 SME／SYM-H／ap／F10.7 + Phase 1 軌道 + DNSAPOD
  -> P2.0–P2.2 來源稽核、分鐘地磁與事件
  -> P2.3 v5 t0 同相位分鐘窗
  -> P2.4 v5 L2／MSIS 配對密度
  -> P2.5 v2 分鐘分析 view
  -> P2.6 final 平滑後的限定窗口 peak QC
```

## 工作包與驗收

| 步驟 | 狀態 | 現行輸出／驗收 |
| --- | --- | --- |
| P2.0–P2.2 | [done] | 來源稽核、1-minute 地磁資料與 25 場 SYM-H 事件；原始觀測不改寫。 |
| P2.3 v5 | [done] | `storm_minute_feature_v5`：以 t0 相位前 31、後 62 圈保留 217,912 筆分鐘資料。這是資料保存窗，不是 peak 選擇窗。 |
| P2.4 v5 | [done] | DNSAPOD 原生 30 秒位置／時間與 NRLMSIS 2.0 配對；25 場 L2 與 paired coverage 均 >= 80%。 |
| P2.5 v2 | [done] | `storm_minute_analysis_v2`：217,912 筆分鐘列；不在此步平滑或取峰。 |
| P2.6 final | [done] | `storm_minute_smooth_v4`：54,025 筆候選分鐘；`storm_minute_peak_qc_v4`：25 場各一列。SQLite integrity、foreign key 與相關測試已通過。 |

## P2.6 final 固定方法

- F10.7A 直接用 CelesTrak 樣本當日 `F10.7_OBS_CENTER81`；每日 F10.7 仍取前一 UTC 日。只用 `OBS`／`INT`，不使用 `PRD`／`PRM`。置中 81 日含未來觀測，只可做離線回溯。Phase 1 P1.6 trailing feature 不變。
- SME 用 15-minute centered mean；`log_ratio_obs` 用 `u_rel_rad +/- pi` 的 centered one-orbit mean。窗口要完整、有效值比例 >= 80%；SYM-H `t0` 取 raw 最低點。
- Peak 僅從 `t0 - 12 h` 至 `t0 + 24 h` 的閉區間取平滑最大值；同值取較早分鐘。不可回到 P2.3 的完整資料保存窗找峰，也不可依預期順序人工改配。
- 唯一現行資料庫：`data/sqlite/2023/swarm_a_phase2_sme_p2_6_final.sqlite`。25 場圖直接位於 `output/image/Phase2/P2.6/`，各一張 `YYYY-MM-DD.png`，不設圖版本子目錄。每張都有 SME、密度殘差與 SYM-H 三個 panel。圖只供檢查，數值以 SQLite 為準。

## 重現與研究界線

依 P2.3、P2.4、P2.5、P2.6 順序執行 `satellite_orbit/phase2/` 的對應 `prep_` 模組；新工作區可用 `python -m output.report.prep_phase2_smoothed_candidate_figures` 產生全部事件圖。繪圖程式只讀 P2.6 final SQLite，在 `output/image/Phase2/P2.6/` 產生 25 張 PNG；同名圖已存在時會拒絕覆寫。檢查點路徑、SHA-256 與驗證結果見[最終報告](PHASE_2_FINAL_REPORT.md)。

16 場 SME peak 早於 density peak，9 場相反。25 場中 24 場為複合事件；全域最大值可能跨 pulse 錯配。因果延遲標籤須另立工作，先定 local pulse segmentation、pairing 與敏感度規則，不覆寫本版 QC。機動排除、衰減標籤、GPR 與 12 年擴充不屬於已完成的 Phase 2。
