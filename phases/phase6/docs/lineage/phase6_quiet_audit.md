# Phase 6 平靜期候選窗資料血緣

狀態：[working]。此稽核只建立密度與 Phase 1 逐圈半長軸可配對的平靜期**候選窗**；它不校準 `B_eff`，不產生 drag acceleration 或實際軌道衰減結論。輸出是本機 `phases/phase6/data/sqlite/swarm_a_phase6_quiet_audit_v1.sqlite`。來源 SQLite 與 Phase 0 raw 檔都以唯讀方式開啟。

#### [P6.0] Phase 1 逐圈半長軸 + SME + DNSAPOD -> 平靜期候選窗 [done]

```text
prep_phase6_quiet_audit.py -> run()

讀取 Phase 1 `swarm_a_phase_orbit_mean_v2` 的 UTC 範圍與 `space_weather.ap_now`。
一天必須有八筆 Ap，且每筆 Ap <= 7；同日 SME CSV 必須有 1,440 個連續 UTC 分鐘，且最大 SME < 300 nT。
保留具有有效 `rho_l2_orbitmean_kg_m3` 的 DNSAPOD 日檔。相鄰兩天組成候選窗；每圈以最近的 DNSAPOD 樣本配對，時間差必須 <= 60 s。
候選窗不代表已完成 maneuver 或 POD quality 稽核，因此 `selection_status` 固定為 `candidate`。
```

```text
swarm_a_phase_orbit_mean_v2 (derived；Phase 1；欄位節錄)
[
  {
    time_us: 1694308752000000 (us),
    orbit_start_time_us: 1694303102000000 (us),
    phase_weighted_mean_semi_major_axis_m: 6.857e6 (m),
  },
  ...,
]

space_weather (raw；Phase 1；欄位節錄)
[
  {
    time_us: 1694304000000000 (us),
    ap_now: 5.000e0,
  },
  ...,
]

SME_20230910.csv (raw；Phase 0)
[
  {
    tval: 1694304000,
    SME: 6.194e1 (nT),
  },
  ...,
]

SW_OPER_DNSAPOD_2__20230910T000000_20230910T235930_0301.ZIP (raw；Phase 0)
[
  {
    time_us: 1694308740000000 (us),
    rho_l2_orbitmean_kg_m3: 7.605e-13 (kg/m^3),
  },
  ...,
]
```

```text
phase6_quiet_window_v1 (derived；欄位節錄)
[
  {
    window_id: Q20230910,
    start_time_us: 1694304000000000 (us),
    stop_time_us: 1694476800000000 (us),
    ap_max: 7.000e0,
    sme_max_nt: 2.405e2 (nT),
    orbit_count: 30,
    paired_orbit_count: 30,
    selection_status: candidate,
  },
  ...,
]

phase6_quiet_orbit_pair_v1 (derived；欄位節錄)
[
  {
    window_id: Q20230910,
    time_us: 1694308752000000 (us),
    mean_semi_major_axis_m: 6.857e6 (m),
    density_time_us: 1694308740000000 (us),
    rho_l2_orbitmean_kg_m3: 7.605e-13 (kg/m^3),
    density_offset_s: -1.200e1 (s),
  },
  ...,
]
```

`time_us` 是每個 Phase 1 完整相位圈結束的 UTC 時刻；`density_time_us` 是最近 DNSAPOD 樣本的 UTC 時刻。`window_id` 是候選窗第一個 UTC 日，並非 maneuver-free 或物理校準標記。
