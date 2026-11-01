# Phase 7：2023 年初兩場磁暴外部事件處理計畫

## 決定

狀態：[done]。`S20230227T1212` 與 `S20230324T0521` 使用新的 Phase 7
輸出，不回寫 frozen Phase 2／2R、Phase 3、Phase 4、Phase 4 V2、Phase 5 V2
或 Phase 6。

```text
P7.0  Phase 0 raw source audit
  -> P7.1 Phase 1R POD mean elements
  -> P7.2 Phase 2R event/minute snapshot
  -> P7.3 Phase 3 quiet R and quiet-density reconstruction
  -> P7.4 fixed Phase 4 V2 tau/G response and retrospective R target
  -> P7.5 frozen Phase 5 V2 Ridge R prediction
  -> P7.6 fixed Phase 6 B_eff decay comparison
```

## 固定事件

| `storm_id` | `t0` UTC | SYM-H 最低值 |
| --- | --- | ---: |
| `S20230227T1212` | 2023-02-27 12:12 | -161 nT |
| `S20230324T0521` | 2023-03-24 05:21 | -170 nT |

兩場都由 frozen Phase 2R 選出，且 Phase 2R L2／MSIS paired coverage 為 100%。
兩場也都是 compound storm；結果只作描述性外部事件檢查。

## 方法邊界

- P7.3 沿用 Phase 3 的近零響應 quiet-run 規則與七欄 `ap=4` NRLMSIS 2.0。
- P7.4 固定讀取 Phase 4 V2 的 `tau=4.75 h` 與共同 `G`，不重新選 tau 或重估 G。
- P7.4 的回溯 `R_fit` 只作外部事件答案，用同場 L2 計算，不進 Ridge 輸入。
- P7.5 固定使用 Phase 5 V2 已保存的三個因素、標準化參數、係數與截距。
- P7.6 固定使用 Phase 6 的 `B_eff`，不以兩場新事件重擬合。
- P7.6 比較的是六日完整窗口總下降，不把全部下降歸因於磁暴。
- 不新增模型、特徵、超參數搜尋、drag propagator 或 XYZ forecast。

## 輸出

- `phases/phase7/data/raw/manifest_dnsapod_early_2023_two_storms.json`
- `phases/phase7/data/sqlite/swarm_a_phase7_density_v1.sqlite`
- `phases/phase7/data/sqlite/swarm_a_phase7_decay_v1.sqlite`
- `phases/phase7/figures/phase7_early_2023_two_storms.png`
- `phases/phase7/reports/phase_7_early_2023_two_storms_report.md`

所有新計算結果使用 SQLite；raw ZIP 保留在既有 Phase 0 raw folder，manifest 只記錄
本次實際使用的檔案與 hash。
