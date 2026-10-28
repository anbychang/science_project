# Phase 1 Space-Weather Lineage

現行輸出在 `phases/phase1/data/sqlite/swarm_a_analysis_2023_2026_phase_candidate_working_v1.sqlite` 與
`phases/phase1r/data/sqlite/swarm_a_analysis_2014_2026_phase_candidate_working_v2.sqlite`。
P1.5.1 checkpoint 保存 raw source；working copy 延續 raw table 並另寫 derived table。
下例取自三年 working copy。舊 `swarm_a_analysis_10min` 分支為 [retained]，不是現行 P1.6 輸出。

`space_weather` raw table 由 `prep_raw_weather.py` 自 `SW-All.csv` 建立；一個完整
UTC day 寫八個 3-hour rows，缺少任一 Ap slot 就拒絕該 day。
`time_us` 是 UTC 3-hour Ap slot 起點；下例的 Ap key 對應 2023-07-01T06:00:00Z。

#### [P1.6] space_weather -> causal feature fields [working]

```text
prep_15_phase_harmonic_features_v2.py -> write_phase_harmonic_features()
calc_feature_alignment.py -> align_space_weather()

Ap 取目標 epoch 所在的 3-hour slot。
F10.7 取前一個 UTC day 的 f107_sfu；F10.7A 取該 day 的 f107a_last81_sfu。
所有 source time <= 目標 time；缺來源則保留目標 row 並標記 quality_flags。
```

```text
space_weather (raw；欄位節錄) + P1.5.6 raw B-L v2 的目標 key
[
  {
    time_us: 1688191200000000 (us),
    ap_now: 3.000e0
  },
  {
    time_us: 1688083200000000 (us),
    f107_sfu: 1.622e2 (sfu),
    f107a_last81_sfu: 1.571e2 (sfu)
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
    ap_now: 3.000e0,
    ap_source_time_us: 1688191200000000 (us),
    f107_sfu: 1.622e2 (sfu),
    f107_source_time_us: 1688083200000000 (us),
    f107a_sfu: 1.571e2 (sfu),
    f107a_source_time_us: 1688083200000000 (us),
    f107_data_type: "OBS",
    quality_flags: "ok",
    algorithm_version: "causal_features_phase_harmonic_v2"
  },
  ...
]
```

目標 `time_us` 是 UTC POD 10-second epoch，不是 10-minute bin。F10.7A 的來源欄位是
`f107a_last81_sfu`，不是 raw `f107a_sfu`。兩個來源數值不同，不能互換。
