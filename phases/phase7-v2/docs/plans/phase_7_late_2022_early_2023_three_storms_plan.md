# Phase 7 V2：三場外部事件處理計畫

## 決定

狀態：[done]。新增 `S20221107T1720` 後，三場事件寫入 `phases/phase7-v2/`。
`phases/phase7/` 的兩事件輸出保留不動。所有新結果使用 SQLite。

```text
P7.0 raw source audit
  -> P7.1 Phase 1R POD minute means
  -> P7.2 frozen Phase 2R event windows
  -> P7.3 Phase 3 quiet R and quiet density
  -> P7.4 fixed Phase 4 V2 tau/G and retrospective R_fit
  -> P7.5 frozen Phase 5 V2 Ridge R
  -> P7.6 fixed Phase 6 B_eff decay comparison
```

## 固定事件

| `storm_id` | t0 UTC | SYM-H 最低值 |
| --- | --- | ---: |
| `S20221107T1720` | 2022-11-07 17:20 | -117 nT |
| `S20230227T1212` | 2023-02-27 12:12 | -161 nT |
| `S20230324T0521` | 2023-03-24 05:21 | -170 nT |

三場均為 compound storm，且 frozen Phase 2R 的 L2／MSIS paired coverage 為 100%。

## 方法界線

- P7.3 沿用 Phase 3 near-zero quiet 規則與七欄 `ap=4` NRLMSIS 2.0。
- P7.4 固定讀取 Phase 4 V2 的 `tau=4.75 h` 與共同 `G`；`R_fit` 只作同場回溯答案。
- P7.5 固定讀取 Phase 5 V2 三因素 Ridge 的標準化參數、係數與截距；不重訓。
- P7.6 固定讀取 Phase 6 `B_eff`；不以三場新事件重擬合。
- 六日窗口下降包含背景下降，沒有 quiet counterfactual，不得稱為磁暴額外下降。

## 重算入口

在 PowerShell 設定以下環境變數後，依序執行四個既有入口。預設不設環境變數時仍是
兩事件 `Phase 7`，不會覆寫 V2。

```powershell
$env:PHASE7_RUN_ROOT='phases/phase7-v2'
$env:PHASE7_RUN_LABEL='late_2022_early_2023_three_storms'
$env:PHASE7_STORM_IDS='S20221107T1720,S20230227T1212,S20230324T0521'
python -m phases.phase7.code.down_phase7_dnsapod
python -m phases.phase7.code.prep_phase7_density
python -m phases.phase7.code.calc_phase7_decay
python -m phases.phase7.code.prep_phase7_figure
```

既有 manifest、SQLite 與圖會拒絕覆寫。
