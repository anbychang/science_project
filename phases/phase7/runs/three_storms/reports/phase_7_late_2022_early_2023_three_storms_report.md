# Phase 7 三事件批次：2022 年末與 2023 年初

目前五場共同計分見[逐圈計分報告](../../../reports/five_storm_orbit_scores.md)。下方六日終點分數是歷史尺度，不再作主要模型排名。

狀態：[done: exploratory external-event validation]。三場均以 frozen Phase 0–6 方法重算；
沒有重訓 Ridge、重選參數或重擬合 `B_eff`。結果不支持 Ridge 取代 M0。

## 事件與資料

| 事件 | t0 UTC | SYM-H 最低值 | valid phase 分鐘 |
| --- | --- | ---: | ---: |
| 2022-11-07 | 17:20 | -117 nT | 8,644 |
| 2023-02-27 | 12:12 | -161 nT | 8,635 |
| 2023-03-24 | 05:21 | -170 nT | 8,632 |

三場 Phase 2R L2 coverage 與 L2/MSIS paired coverage 都是 100%。輸出有 25,911 個
有效相位分鐘與同數量 POD/density 完整配對分鐘。

## Phase 3 quiet R

| 事件 | pre quiet UTC | `R_phase3` | post diagnostic R | post/pre 差 |
| --- | --- | ---: | ---: | ---: |
| 2022-11-07 | 2022-10-26 04:29–13:49 | 0.7977 | 0.7374 | -7.6% |
| 2023-02-27 | 2022-12-18 04:26–08:23 | 0.7263 | 1.0595 | +45.9% |
| 2023-03-24 | 2023-03-13 20:14–2023-03-14 00:00 | 1.0413 | 0.7376 | -29.2% |

三場 pre/post raw density coverage 都是 100%。2023-02-27 的 pre quiet run 距第一個強
minimum 約 71 天，仍是主要不確定來源。

## Phase 4／5 density

`R_fit` 固定 Phase 4 V2 的 `tau=4.75 h` 與共同 `G`，使用同場 L2 回溯求得。它是外部事件
答案，不是預報。Ridge 完全讀取 25 場訓練後保存的係數。

| 事件 | `R_fit` | Ridge R | Ridge - fit | M0 log RMSE | fitted-R log RMSE | Ridge log RMSE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2022-11-07 | 1.0062 | 0.9216 | -0.0846 | 0.1571 | 0.1475 | 0.1717 |
| 2023-02-27 | 0.8160 | 0.9335 | +0.1175 | 0.3025 | 0.2387 | 0.2740 |
| 2023-03-24 | 0.8734 | 1.1376 | +0.2642 | 0.1622 | 0.0591 | 0.2708 |

Ridge 只有 2023-02-27 的 direct density RMSE 低於 M0；其餘兩場較高。三場都輸給使用同場
L2 的 fitted-R 曲線，這不是公平預報比較，但表示 Ridge 仍未穩定重現事件倍率。

## Phase 6 six-day decline

| 事件 | POD (m) | M0 (m) | M0 error (m) | Ridge (m) | Ridge error (m) | 較接近 POD |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 2022-11-07 | -198.60 | -195.17 | +3.43 | -195.06 | +3.54 | M0 |
| 2023-02-27 | -406.09 | -475.97 | -69.88 | -457.03 | -50.94 | Ridge |
| 2023-03-24 | -366.23 | -425.52 | -59.29 | -499.93 | -133.71 | M0 |

| 三場指標 | M0 | Ridge |
| --- | ---: | ---: |
| MAE | 44.20 m | 62.73 m |
| RMSE | 52.95 m | 82.64 m |

六日窗口包含背景下降，沒有 quiet counterfactual；表中的總下降不可解讀為全數由磁暴造成。

## 可重現性

| 輸出 | SHA-256 |
| --- | --- |
| raw manifest | `3a76c920bc6ad92df45e6f3b5d1b3c49295ab53dbcafccee573ceff090d8c896` |
| density SQLite | `25b519165f6b30b0eebf575b8e03eed13544f66b1ca9e32225053cf3fa2c2d53` |
| decay SQLite | `46a7b7e7163021602393cf68e8073d5077d854f259d16e08734624d2627f3ed7` |
| figure | `5ab26f43f031d04055b3d484157c4c0a38a61869c24b25f458a853eff7458658` |

兩個 SQLite 的 `PRAGMA integrity_check` 都是 `ok`。圖檔為
`figures/phase7_late_2022_early_2023_three_storms.png`。
三張個別圖同在 `figures/`，檔名末尾分別是三個 `storm_id`。
