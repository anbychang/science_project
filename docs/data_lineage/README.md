# 資料血緣索引

Phase 1／1R 是未校準的候選工作庫；Phase 2／2R 與 Phase 3 已結案，詳細入口見下方「文件」。Phase 4 已有 25 場留一場 GPR 衍生結果，模型判讀仍在進行。各步以所屬 Phase 的血緣文件與報告為準。

## Phase 1／1R 工作資料庫

目前保留兩份完成 P1.5.1 的 checkpoint：

- `phases/phase1r/data/sqlite/swarm_a_analysis_2014_2026_p1_5_iter5000.sqlite`
- `phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_p1_5_iter5000.sqlite`

兩份 checkpoint 都停在 P1.5.1。三年下游 working copy 是
`phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite`；
12 年下游 working copy 是
`phases/phase1r/data/sqlite/swarm_a_analysis_2014_2026_phase_candidate_working_v2.sqlite`。
兩者都有 P1.5.6 raw/joint v2、P1.6 features v2 與 P1.7 audit v2。
P1.7 各 6 項 violation 均為 0，metadata status 為 `pass`；仍是 working copy，
不是已校準的 decay release。三年 checkpoint 的 raw states 是全期資料，
只有 mean-element table 限定三年。
整庫複製入口是 `prep_mean_orbit_checkpoint.py downstream SOURCE TARGET`（SOURCE 為 `p1_5.sqlite` 中途檢查點）；
`prep_phase1_from_frozen.py` 與 `prep_phase1_rebuild.py` 是重新建立資料庫的其他路徑，不代表這份 working copy 的整庫複製步驟。

```text
POD -> P1.5.1 mean-element checkpoint
  -> P1.5.6 raw B-L / joint H2/H3 v2 局部 slope
weather + geomagnetic -> P1.6 shared causal features v2
  -> P1.7 v2 working audit
```

舊版 `working_audit_pass` 是 v1 long-candidate branch 的狀態，不能當作 v2 結果。
現行 v2 的 `pass` 只表示 key、rate validity、feature causality、有限值及
SQLite integrity 通過，不代表 slope 已校準為真實 drag。
cache 只避免重跑相同的 mean-orbit work，不是第二份資料或 release。

## 主線

```text
POD ZIP
  -> swarm_a_states
  -> orbital elements + POD quality + mean orbit
  -> mean-element checkpoint (file name: p1_5.sqlite)
  -> full copy -> three-year / 12-year working copy
                   |-> P1.5.4 phase-orbit mean v2
                   |-> P1.5.5 H2/H3 diagnostic v1
                   -> P1.5.6 raw B-L / joint H2/H3 sets v2

weather CSV + geomagnetic CSV
  -> P1.6 shared causal features v2
  -> P1.7 audit v2 + manifest

P1.5.2--P1.5.3 的 10-minute branch 與 v1 long-candidate branch 是
retained legacy，不是上述 v2 主線的輸入。
```

## 規則

完整的 lineage 寫作、Input/Output contract、資料不可變性、Phase 1 contract 與證據規則：
[RULES.md](RULES.md)。

## 文件

- [POD lineage](../../phases/phase1/docs/lineage/orbit_analysis.md): POD 到 final orbit / rate / audit。
- [Space-weather lineage](../../phases/phase1/docs/lineage/space_weather.md): Ap、F10.7、F10.7A。
- [Geomagnetic lineage](../../phases/phase1/docs/lineage/geomagnetic.md): SYM-H。
- [Phase 2 最終報告](../../phases/phase2/reports/phase_2_final_report.md)：交付檢查點、SHA-256、驗證與科學限制。
- [Phase 2 計畫](../../phases/phase2/docs/plans/PLAN.md)：已完成的工作包、輸出與驗收。
- [Phase 2 SME 方法主報告](../../phases/phase2/reports/phase_2_sme_report.md)：唯一的方法規格；三年資料準備與 P2.6 final 描述性 peak QC。
- [Phase 2 來源研究](../../phases/phase2/docs/plans/research_phase_2_data_sources.md)：官方時間語意、版本與未解事項。
- [Phase 2 SME 分鐘資料血緣](../../phases/phase2/docs/lineage/phase_2_storm_dataset.md)：P2.0–P2.6 的實際 Action、Input、Output 與驗證結果。
- [Phase 2R 12 年最終報告](../../phases/phase2r/reports/phase_2r_final_report.md)：12 年同方法重現的結果、checkpoint hash 與科學限制。
- [Phase 2R 12 年計畫](../../phases/phase2r/docs/plans/PLAN.md)：P2R.0–P2R.6 的固定方法與驗收結果。
- [Phase 2R 12 年資料血緣](../../phases/phase2r/docs/lineage/phase_2r_12year_replication.md)：每一步的 Action、Input、Output 與可查回範例。
- [Phase 3 三年 25 場資料血緣](../../phases/phase3/docs/lineage/phase_3_25_storm_prediction.md)：已結案的 $R_k$ 校準、SME 濾波、MSIS 配對、共同延遲與逐場回溯密度曲線。
- [Phase 4 一圈 GPR 資料血緣](../../phases/phase4/docs/lineage/phase_4_gpr_loso.md)：25 折留一場的凍結來源、相位錨點與衍生預測。
- [Phase 4 GPR 結果報告](../../phases/phase4/reports/phase_4_gpr_loso_report.md)：逐場圖、誤差、涵蓋率與適用範圍。

Phase 2 原始下載檔保留 CSV／ZIP；正式衍生結果只讀取 `phases/phase2/data/sqlite/` 的版本化 SQLite。
Phase 2R 重用相同資料契約，獨立檢查點只寫入 `phases/phase2r/data/sqlite/`。

## Phase 2 P2.0 SME 原始下載 [done]

```text
down_supermag_sme.py -> download_range()

SuperMAG indices.php -> 按 UTC 日請求 sme,num -> 保留 tval,SME,SMEnum 原值與逐檔 SHA-256
不補值、不改正負號；來源填充值留在 raw CSV，後續 P2.1 才轉成缺值。
```

```text
SuperMAG indices.php (UTC 日請求；不含登入識別)
{
  start: 2014-01-01T00:00,
  extent: 86400 (s),
  indices: sme,num
}
```

```text
phases/phase0/data/raw/sme/SME_20140101.csv (raw；首筆)
[
  {
    tval: 1388534400.0 (UTC Unix s),
    SME: 1.096e+2 (nT),
    SMEnum: 125
  },
  ...
]

phases/phase0/data/raw/sme/manifest_p2_0_sme.json (raw 檔案索引；首筆欄位節錄)
[
  {
    file_name: SME_20140101.csv,
    row_count: 1440,
    downloaded_at_utc: null,
    sha256: 39b261c9e18b4ff7d524537e507b6de1ccc8b4fb0a59bbae7012415362f66509
  },
  ...
]
```

2026-10-23 UTC 已完成 `2014-01-01` 至 `2026-06-30` 的 4,564 個日檔，總計
6,572,160 個整分鐘格點。全檔逐筆核對：日期連續、每日 1,440 筆、時間格點無錯、
CSV 與 manifest 的 SHA-256 全部相符；manifest SHA-256 為
`297591e5092abe14cc2dde7673761073a639b8ef954260fe5c6d20df6a4b434d`。
原始 API 回應未提供產品版號；`tval` 所代表分鐘的區間起點／中點仍待來源確認。

有效 SME 共 6,493,115 分鐘，占 98.797%。從 `2026-05-07T02:35:00Z` 到
`2026-06-30T23:59:00Z` 連續 79,045 分鐘為 `SME = 999999`、`SMEnum = 0`；
最後有效分鐘為 `2026-05-07T02:34:00Z`。有效分鐘的 `SMEnum` 範圍為 1–158，
其中 781 分鐘不超過 3 站；不能僅憑非填充值判定品質足夠。末段沒有 SME 實測，
不可把 4,564 個日檔誤寫成完整有效觀測，也不可跨這段長缺口內插。

斷點續傳會讓既有檔案的 `downloaded_at_utc` 成為 null；本次總 manifest 有 3,132 檔
缺逐檔精確下載時刻，另 1,432 檔記錄 2026-10-23 UTC 的下載時刻。歷史 manifest
`manifest_p2_0_sme_2014.json` 與 `manifest_p2_0_sme_20230701_20260630.json` 保留原始批次證據。
本節 `tval` 範例是 UTC 分鐘格點，不代表已確認觀測區間語意。

2026-10-22 再查詢 SuperMAG 時，環境沒有 `SUPERMAG_USER_ID`；空白識別的 API
請求回傳 `Invalid username`，公開 HAPI 介面回傳維護頁。因此沒有重新下載或覆寫
既有 1,096 個 SME 日檔；79,045 分鐘來源填充值仍是未解缺口。

2026-10-23 UTC 使用已提供的 SuperMAG 識別名稱逐日查詢 `2026-05-07` 至
`2026-06-30`，共 55 日。`2026-05-07` 只有首 155 分鐘有效，
`2026-05-08` 至 `2026-06-30` 的有效值均為 0；來源仍未補回缺口。
這次只查詢，不另存重複的填充值，也不修改既有 raw CSV、manifest 或 SQLite。

## Phase 2 P2.0 GFZ ap 原始下載 [done]

```text
down_gfz_ap.py -> download_ap()

GFZ API -> 驗證 3-hour UTC 起點、def 狀態及完整格點 -> 保存原始 JSON 與 SHA-256 manifest
```

```text
GFZ /app/json/ (UTC 請求)
{
  start: 2023-07-01T00:00:00Z,
  end: 2026-06-30T23:59:59Z,
  index: ap,
  status: def
}
```

```text
phases/phase0/data/raw/geomagnetic/gfz_ap_2023-07-01_2026-06-30.json (raw；aligned arrays 首筆節錄)
{
  datetime: [
    2023-07-01T00:00:00Z,
    ...
  ],
  ap: [
    7.000e0,
    ...
  ],
  status: [
    def,
    ...
  ]
}

phases/phase0/data/raw/geomagnetic/gfz_ap_2023-07-01_2026-06-30.manifest.json (raw 檔索引；欄位節錄)
{
  retrieved_at_utc: 2026-10-22T14:31:38.938510+00:00,
  slot_count: 8768,
  sha256: 246375edb66c1cd2ca3eb9287de5f24c0a94085732ee9b3fd1018f5565ca71de
}
```

GFZ JSON 的 8,768 個 slot 全是 `def`；首筆為 `[2023-07-01T00:00:00Z, 2023-07-01T03:00:00Z)`，末筆起點為 `2026-06-30T21:00:00Z`。與既有 CelesTrak `AP1`–`AP8` 逐格比對，差異為 0；兩個來源仍分開保留。`def` 是現在取得的 retrospective 版本，不證明當時已有此值。

## Phase 2 P2.0 來源稽核 [done]

```text
prep_20_source_audit.py -> build_audit()

原始 SME／京都指數／GFZ ap／CelesTrak 檔 -> 逐格、重疊值、來源旗標與雜湊稽核 -> JSON 摘要
```

```text
phases/phase0/data/raw/sme/manifest_p2_0_sme.json (raw；files[0] 欄位節錄)
{
  file_name: SME_20230701.csv,
  row_count: 1440,
  sha256: d26aed933af1e33bdb0364618e2a7178c1c3a6ac841de5ace63497d112e9f9c1
}

phases/phase0/data/raw/geomagnetic/gfz_ap_2023-07-01_2026-06-30.manifest.json (raw；節錄)
{
  raw_file: gfz_ap_2023-07-01_2026-06-30.json,
  slot_count: 8768
}

phases/phase0/data/raw/geomagnetic/sym_h_2023-01-01_2023-12-31.csv (raw；2023-07-01 首筆節錄)
{
  Time: 2023-07-01T00:00:00Z,
  symHValue: -14,
  versionCode: 10
}

phases/phase0/data/raw/geomagnetic/ae_2023-01-01_2023-12-31.csv (raw；2023-07-01 首筆節錄)
{
  Time: 2023-07-01T00:00:00Z,
  aeValue: 51,
  versionCode: 0
}

phases/phase0/data/raw/space_weather/SW-All.csv (raw；2023-07-01 欄位節錄)
{
  DATE: 2023-07-01,
  AP1: 7,
  F10.7_OBS: 1.655e2,
  F10.7_DATA_TYPE: OBS
}
```

```text
phases/phase2/data/sqlite/phase2_p2_0_source_audit.json (derived；欄位節錄)
{
  date_range_utc: [
    2023-07-01,
    2026-06-30
  ],
  sme: {
    valid_minutes: 1499195,
    invalid_minutes: 79045
  },
  gfz_ap: {
    slot_count: 8768,
    celestrak_ap_mismatch_slots: 0
  }
}
```

稽核 JSON SHA-256 為 `db225aaf7b2007ffffce64fd425af766f408e920f6e332e45821231c1ee323e3`。
SYM-H／AE 各有 1,578,240 個獨立分鐘、無 fill 或時間缺口；重疊 CSV 無衝突。
SYM-H 版本全為 10；AE 的版本 0 有 1,571,040 分鐘、版本 10 有 7,200 分鐘。
CelesTrak 涵蓋 1,096 日，F10.7 有 1,092 個 `OBS` 日、4 個 `INT` 日：
`2024-08-26`、`2025-02-12`、`2025-02-17`、`2026-05-09`。
這份 JSON 已封存在 P2.0 `swarm_a_phase2_sme_p2_0_v2.sqlite` 的 `source_audit_v2`；P2.1、P2.2、P2.3 v5、P2.4 v5、P2.5 v2 與 P2.6 final 依序複製前一步。P2.3/P2.4 的單日 F10.7 使用前一日 `F10.7_OBS`；F10.7A 使用樣本當日來源 `F10.7_OBS_CENTER81`。`OBS`／`INT` 可用，`PRD`／`PRM` 不可進入研究資料。完整檢查點契約見 [Phase 2 SME 分鐘資料血緣](../../phases/phase2/docs/lineage/phase_2_storm_dataset.md)。

## Phase 2 DNSAPOD 三年原始檔補齊 [done]

```text
down_dnsapod_three_year.py -> download_three_year()

ESA Sat_A DNS/POD 日檔清單 -> 2023-07-01 至 2026-06-30 UTC 每日取最新版 -> 驗證既有 ZIP 並下載缺檔 -> 三年 manifest
只擴充 raw 來源；不改 SQLite、已下載 ZIP 與既有 manifest。
```

```text
ESA Sat_A DNS/POD listing (raw；首筆欄位節錄)
[
  {
    name: SW_OPER_DNSAPOD_2__20230701T000000_20230701T235930_0301.ZIP,
    path: swarm/Level2daily/Entire_mission_data/DNS/POD/Sat_A/SW_OPER_DNSAPOD_2__20230701T000000_20230701T235930_0301.ZIP,
    size: 139503 (bytes),
    mtime: 1726631350 (UTC Unix s)
  },
  ...
]
```

```text
phases/phase0/data/raw/swarm_density_pod/manifest_dnsapod_20230701_20260630.json (raw 檔案索引；files[0] 欄位節錄)
[
  {
    name: SW_OPER_DNSAPOD_2__20230701T000000_20230701T235930_0301.ZIP,
    source_mtime_utc: 2024-09-18T03:49:10+00:00,
    local_mtime_utc: 2026-10-22T17:14:16.614001+00:00,
    size_bytes: 139503 (bytes),
    sha256: 6f55661c0aebd85e1cfd9c8c30eb0648f03ba30d31e7a380191bfbce87e63f3c
  },
  ...
]
```

2026-10-22 UTC 完成 1,096 個日檔，沿用 217 個事件窗口原始檔，新增 879 個；
檔名版本均為 `0301`，合計 152,923,221 bytes。每檔已核對 ESA byte count、ZIP
完整性與 SHA-256，日期無缺漏；manifest SHA-256 為
`47c55aaf2f25b7adb373148786e7b36b00c54b1b655250cc36810bbdfd159152`。
重現入口：`python -m phases.phase0.code.data.density.down_dnsapod_three_year`；
已有 manifest 時會拒絕覆寫。原始 ZIP 未匯入 SQLite；P2.4 v5 依 P2.3 v5 的 t0 相位分鐘窗讀取需要的日檔，衍生 SQLite 位於 `phases/phase2/data/sqlite/`。
