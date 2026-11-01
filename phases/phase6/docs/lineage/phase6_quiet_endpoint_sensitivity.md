# Phase 6 平靜期端點敏感度資料血緣

狀態：[working]。此步量測候選半長軸下降量對端點擬合圈數的敏感度。它不增加 POD systematic、maneuver 或 physical drag 的不確定度；6 圈 OLS sigma 只能作為殘差造成的下限。輸出是本機 `phases/phase6/data/sqlite/swarm_a_phase6_quiet_endpoint_sensitivity_v1.sqlite`。

#### [P6.2] 平靜期 orbit-density pairs -> 端點擬合敏感度 [done]

```text
calc_phase6_quiet_endpoint_sensitivity.py -> run()

每個候選窗分別以最前與最後 4、6、8 個 `mean_semi_major_axis_m` 作 OLS 線性擬合。
在該段第一個或最後一個 `time_us` 評估 fitted a；兩端相減得到 `delta_a_N_m`。
6 圈值保存由兩段 OLS prediction sigma 合成的 `delta_a_ols_sigma_6_m`；三個 delta 的 max-min 是 `delta_a_endpoint_span_m`。
```

```text
phase6_quiet_orbit_pair_v1 (derived；Phase 6 平靜期稽核；欄位節錄)
[
  {
    window_id: Q20230910,
    time_us: 1694308752000000 (us),
    mean_semi_major_axis_m: 6.857e6 (m),
  },
  ...,
]
```

```text
phase6_quiet_endpoint_sensitivity_v1 (derived；欄位節錄)
[
  {
    window_id: Q20230910,
    delta_a_4_m: -4.924e1 (m),
    delta_a_6_m: -4.859e1 (m),
    delta_a_8_m: -5.489e1 (m),
    delta_a_ols_sigma_6_m: 5.230e0 (m),
    delta_a_endpoint_span_m: 6.293e0 (m),
  },
  ...,
]
```

`delta_a_endpoint_span_m` 是設定敏感度，不是 statistical confidence interval。每個窗的 OLS 端點段都只含 4--8 個逐圈點，且不含 shared systematic error；因此不得將 `delta_a_ols_sigma_6_m` 單獨解釋為完整觀測不確定度。
