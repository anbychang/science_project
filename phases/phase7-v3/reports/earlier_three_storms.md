# 往前三場磁暴結果

目前五場共同計分見[逐圈計分報告](five_storm_orbit_scores.md)；2018 年事件已從目前計分排除。下方六日終點比較保留作歷史尺度。

狀態：[done: exploratory]。使用固定 Phase 4 V2 `tau/G`、Phase 5 V2 Ridge 與 Phase 6 `B_eff`；三場均未參與 25 場訓練。26 個 DNSAPOD 日檔已核對，兩個衍生 SQLite `integrity_check=ok`，共有 25,593 個配對分鐘。

| 事件 | `R_phase3` | `R_fit` | Ridge R | 有效分鐘 | POD 下降 | M0 下降 | Ridge 下降 | 較接近 POD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 2018-08-26 | 0.5056 | 0.8033 | 0.9213 | 8,590 | -59.07 m | -73.36 m | -65.17 m | Ridge |
| 2021-11-04 | 0.8795 | 1.0405 | 1.2453 | 8,437 | -151.37 m | -179.91 m | -212.52 m | M0 |
| 2022-03-13 | 0.7784 | 0.9094 | 1.0353 | 8,566 | -282.73 m | -331.51 m | -339.26 m | M0 |

2021-11-04 的 Phase 2R 配對完整度是 99.08%；其餘兩場是 100%。缺口保留，積分不跨缺口。三場的 Ridge R 都高於同場回溯 `R_fit`。下降量一場 Ridge 較近、兩場 M0 較近。六日下降含背景，不能全歸因於磁暴。

重算時設定 `PHASE7_RUN_ROOT=phases/phase7-v3`、`PHASE7_RUN_LABEL=earlier_three_storms`、`PHASE7_STORM_IDS=S20180826T0711,S20211104T1244,S20220313T2337`，依序執行 `down_phase7_dnsapod`、`prep_phase7_density`、`calc_phase7_decay`、`prep_phase7_figure.draw_individual_figures()`。
