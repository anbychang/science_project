# Phase 1 Geomagnetic Lineage

現行輸出在 `phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite` 與
`phases/phase1r/data/sqlite/swarm_a_analysis_2014_2026_phase_candidate_working_v2.sqlite`。
P1.5.1 checkpoint 保存 raw source；working copy 延續 raw table 並另寫 derived table。
下例取自三年 working copy。舊 `swarm_a_analysis_10min` 分支為 [retained]，不是現行 P1.6 輸出。

#### [P1.6] geomagnetic -> causal SYM-H feature [working]

```text
prep_15_phase_harmonic_features_v2.py -> write_phase_harmonic_features()
calc_feature_alignment.py -> align_sym_h()

Exact observation 直接使用；否則只在左右觀測間距 <= 120 s 時線性內插。
缺來源則保留目標 row 並標記 quality_flags。AE 不加入此 feature table。
```

```text
geomagnetic (raw；欄位節錄) + P1.5.6 raw B-L v2 的目標 key
[
  {
    time_us: 1688197860000000 (us),
    sym_h_nt: -1.600e1 (nT)
  },
  {
    time_us: 1688197920000000 (us),
    sym_h_nt: -1.600e1 (nT)
  },
  ...
]
target time_us: 1688197912000000 (us)
```

```text
swarm_a_phase_harmonic_features_v2 (derived；欄位節錄)
[
  {
    time_us: 1688197912000000 (us),
    sym_h_nt: -1.600e1 (nT),
    sym_h_left_time_us: 1688197860000000 (us),
    sym_h_right_time_us: 1688197920000000 (us),
    quality_flags: "ok",
    algorithm_version: "causal_features_phase_harmonic_v2"
  },
  ...
]
```

目標 `time_us` 是 UTC POD 10-second epoch；右端觀測在目標時刻之後 8 s，
但因左右觀測只差 60 s，符合內插條件。不能將此 feature 解讀為嚴格只使用當下已發布的 SYM-H。
