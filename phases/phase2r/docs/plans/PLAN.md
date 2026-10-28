# Phase 2R 計畫：12 年同方法重現

## 狀態 [done]

Phase 2R 將已封存的 Phase 2 final 科學方法套用到
`2014-07-01T00:00:00Z <= time < 2026-07-01T00:00:00Z`。Phase 2 的程式介面可重用，
`phases/phase2/data/sqlite/` 檢查點與 25 張圖不修改。本次新輸出放在
`phases/phase2r/data/sqlite/` 與 `phases/phase2r/figures/`。`phases/phase2r/data/sqlite/` 代表以 2014
起始的完整 12 年範圍，不是只含 2014 單年。

```text
12 年 SME／SYM-H／AE／ap／F10.7 + Phase 1 + DNSAPOD
  -> P2R.0 來源稽核
  -> P2R.1 一分鐘地磁檢查點
  -> P2R.2 相同 SYM-H 事件規則
  -> P2R.3 相同 t0 相位分鐘窗
  -> P2R.4 相同 DNSAPOD／NRLMSIS 配對
  -> P2R.5 一分鐘分析 view
  -> P2R.6 相同平滑與 peak QC
```

## 不變的方法

- SYM-H 低於 `-100 nT` 的局部最小值；72 小時內合併。
- P2R.3 保留 `t0` 前 31 圈、後 62 圈的同相位分鐘。
- 每場只可使用包含 `t0` 的單一連續 Phase 1 `chunk_id`；不跨缺口或機動分段。
- F10.7 取前一 UTC 日；F10.7A 取樣本當日 CelesTrak `F10.7_OBS_CENTER81`。
- L2 與 L2／MSIS paired coverage 各自必須 `>= 80%`。
- SME 用 15-minute centered mean。
- `log_ratio_obs` 用 `u_rel_rad +/- pi` centered one-orbit mean。
- peak 候選窗是 `t0 - 12 h` 至 `t0 + 24 h`；同值取較早分鐘。
- 只用於離線描述性 QC；不宣稱因果延遲、真實軌道衰減標籤或即時預報。

## 獨立性與重現

- P2R.0／P2R.1 只新增 12 年來源範圍適配層。
- P2R.2、P2R.4、P2R.5、P2R.6 直接呼叫 Phase 2 final writer 的既有 interface。
- P2R.3 重用 Phase 2 的相位計算；新增 `chunk_id` 邊界排除表，不把不連續軌道接起來。
- 每步建立新 SQLite，寫入上游 SHA-256，既有 output 時拒絕覆寫。
- DNSAPOD 只下載 P2R.3 實際事件分鐘觸及的 UTC 日，不盲目下載全 12 年。

## 目前結果

- P2R.0：4,383 天；6,311,520 分鐘格。
- P2R.1：6,311,520 列；有效 SME 6,232,475 列。
- P2R.2：49 場事件，46 場為複合事件。
- P2R.3：46 場可用，400,696 分鐘列；3 場因 Phase 1 連續相位不足排除。
- P2R.4：324 個 DNSAPOD UTC 日，400,696 列；46 場全數通過 80% coverage。
- P2R.5：400,696 列 analysis view；minute key mismatch 為 0。
- P2R.6：99,406 個候選分鐘、46 場 QC；33 場 SME peak 較早，13 場反序。

最終 checkpoint hash、驗證與科學界線見[Phase 2R 最終報告](../../reports/phase_2r_final_report.md)。
