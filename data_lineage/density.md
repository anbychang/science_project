# Density Data Lineage

```text
ESA DNSAACC archive -> local DNSAACC ZIP [paused]
  -> partial swarm_a_density raw SQLite [in progress]
  -> partial swarm_a_density_10min derived SQLite [next]
  -> full-inventory evidence release [after download resumes]
  -> read-only Phase 1 case comparison [next]
```

## [0] ESA archive -> local DNSAACC ZIP [paused]

```text
satellite_orbit/data/density/down_swarm_density.py
  -> download_swarm_a_density_since("2010-01-01")

list ESA Entire_mission_data/DNS/ACC/Sat_A
keep one highest-version ZIP per available UTC day
skip existing ZIP only when local size equals ESA source size
download and size-verify every other selected ZIP
```

```text
ESA archive request
{
  product: "DNSAACC Swarm-A",
  first_day: 2010-01-01 UTC
}
```

```text
Local files
{
  folder: "data/swarm_density_acc",
  ZIP_count: 917,
  acquisition_status: "paused",
  ESA_available_days: 1431,
  ESA_available_coverage:
    [2014-02-01, 2014-12-31] + [2015-01-01, 2015-12-31] +
    [2016-01-01, 2016-12-31] + [2024-01-01, 2024-12-31] +
    [2025-11-01, 2025-11-30]
}
```

先前完成的 396 份 ZIP audit：每個 ZIP 與 CDF 都可讀；每個 CDF 都有 `time`、`density`、`altitude`、`latitude`、`longitude`、`local_solar_time`；每檔有 8,640 個固定 10 s cadence timestamps。`2,605,058 / 3,421,440` density values 是 positive finite；其餘 `816,382` 是 CDF fill value；沒有 `0`、negative 或 `NaN` density。CDF 沒有 per-record quality field，所以只排除 fill values，不能替其餘值假設 ESA quality flag。

下載完成前不得 import。現有 `data/swarm_a_phase1_rebuild.sqlite` 仍是 frozen 61-source-file product，不得混入新 ZIP。

目前使用者已明確選擇處理已下載 ZIP，因此先建立 partial evidence release。它的檔名、metadata 與 lineage 都必須標示 `partial`；完成下載後仍從完整 inventory 重建正式 full release，不把新檔 append 到 partial release。

## [0.4] paused local ZIP -> partial raw density SQLite [in progress]

Storage target: `data/swarm_a_phase2_density_partial.sqlite`, table `swarm_a_density`。

```text
Input
  data/swarm_density_acc/*.ZIP at the paused local inventory

Process
  create a new SQLite database
  load only positive finite density records
  store partial status and ZIP/source-file counts in metadata

Output
  swarm_a_density
  metadata {density_release_status: "partial", density_zip_file_count, ...}
```

這個 database 只供目前已下載資料的 aggregate 與 audit；不得當成完整 archive 或最終 Phase 2 evidence。

## [0.5] complete ZIP inventory -> full raw density SQLite [next]

Storage target: `data/swarm_a_phase2_density_full.sqlite`, table `swarm_a_density`。這是新的 evidence release；不修改 `data/swarm_a_phase1_rebuild.sqlite`。

```text
Input
  data/swarm_density_acc/*.ZIP
  + ESA selected-day / size inventory

Process
  1. confirm every selected ESA day has one local ZIP with the expected size
  2. read every CDF and record readable-file / record-count / fill-value audit
  3. load only positive finite density records into a new raw SQLite database
  4. retain time, density, altitude, latitude, longitude, local solar time,
     and source_file; never interpolate a missing source record

Output
  data/swarm_a_phase2_density_full.sqlite
  -> swarm_a_density
```

```text
swarm_a_density:
[{time_us, density_kg_m3, altitude_m, latitude_deg, longitude_deg,
  local_solar_time_h, source_file}, ...]
```

這一步完成後，local archive、file audit、raw SQLite 三者的檔案數與 record count 必須可追溯；raw table 完成後不 update 或 delete。

## [0.6] full raw density -> full 10-minute density [next]

Storage target: `data/swarm_a_phase2_density_full.sqlite`, table `swarm_a_density_10min`。

```text
Input
  swarm_a_density

Process
  group observed positive finite records into UTC [time_us - 600 s, time_us)
  retain count, first/last source time, and largest observed source gap

Output
  swarm_a_density_10min
  [{time_us, density_count, first_source_time_us, last_source_time_us,
    max_source_gap_s, density_mean_kg_m3, density_median_kg_m3,
    density_min_kg_m3, density_max_kg_m3}, ...]
```

這只描述已觀測 density；沒有資料的 10-minute bin 不產生假資料。

## [0.7] full 10-minute density -> event baseline [next]

Storage target: `data/swarm_a_phase2_density_full.sqlite`, table `swarm_a_density_event_baseline_10min`。

```text
Input
  swarm_a_density
  + swarm_a_density_10min
  + fixed event peak and pre-storm cutoff

Process
  apply the existing same-direction / latitude / altitude / local-solar-time
  earlier-orbit baseline contract; preserve failed coverage or control matches

Output
  swarm_a_density_event_baseline_10min
  [{event_id, time_us, density_*, baseline_density_*, density_ratio_median,
    control_match_status}, ...]
```

P2 density baseline 可以涵蓋所有有 density 的時段；但下一步的 orbital-decay comparison 只能選 density 與 Phase 1 同時存在的時段。

## [0.8] density baseline + Phase 1 analysis -> descriptive case comparison [next]

```text
Input
  data/swarm_a_phase2_density_full.sqlite
  -> swarm_a_density_event_baseline_10min

  data/swarm_a_phase1_rebuild.sqlite
  -> swarm_a_analysis_10min

Process
  read-only join on time_us
  keep only control_match_status = "ok" and explicit coverage fields
  compare density ratio with SYM-H, Ap, F10.7, F10.7A, and decay columns
  report rows with missing density or failed baseline separately

Output
  a case-comparison result with source coverage and match status
```

目前 Phase 1 orbit analysis coverage 是 `2022-01..2026-08`；ESA density archive coverage 是 `2014..2016`、`2024`、`2025-11`。兩者可直接比較的交集只有 `2024` 與 `2025-11`。下載較早年份不會擴大這個交集；若要比較 `2014..2016`，必須另行擴充 Phase 1 POD / orbit analysis，這不是本輪 Phase 2 的工作。

## [1] one ZIP -> CDF records

```text
load_swarm_density.py -> load_swarm_density()

open ZIP
extract .cdf
read time / density / altitude / latitude / longitude / local solar time
skip density <= 0 or >= 1e30 kg/m^3
```

```text
{
  file_name: "SW_OPER_DNSAACC_...ZIP",
  ZIP: {density.cdf}
}
```

```text
[
  {
    time: 2024-05-10 14:20:00 UTC,
    density: 3.2e-12 kg/m^3,
    altitude: 465000 m,
    latitude: 42.1 deg,
    longitude: 121.4 deg,
    local_solar_time: 15.2 h
  },
  ...
]
```

## [2] [DensityRecord, ...] -> SQLite

```text
prep_raw_density.py -> write_density_folder()
time_to_us() -> time_us
```

```text
[
  {
    time: 2024-05-10 14:20:00 UTC,
    density: 3.2e-12 kg/m^3,
    altitude: 465000 m,
    latitude: 42.1 deg,
    longitude: 121.4 deg,
    local_solar_time: 15.2 h
  },
  ...
]
```

```text
SQLite
{
  swarm_a_density:
  [
    {
      time: 2024-05-10 14:20:00 UTC,
      density: 3.2e-12 kg/m^3,
      altitude: 465000 m,
      latitude: 42.1 deg,
      longitude: 121.4 deg,
      local_solar_time: 15.2 h,
      source_file: "SW_OPER_DNSAACC_...ZIP"
    },
    ...
  ]
}
```

`swarm_a_density` 是 shared immutable raw table；後續步驟不得 update 或 delete raw records。

## [3] raw density SQLite -> 10-minute density SQLite [done]

Storage: `data/swarm_a_phase1_rebuild.sqlite`, table `swarm_a_density_10min`.

```text
satellite_orbit/phase2/prep_density_10min.py -> write_density_10min()

read time_us / density_kg_m3
keep positive finite density
group UTC [time_us - 600 s, time_us) bins
replace only swarm_a_density_10min
```

```text
SQLite
{
  swarm_a_density: [DensityRecord, ...]
}
```

```text
SQLite
{
  swarm_a_density_10min:
  [
    {
      time: 2024-05-10 14:30:00 UTC,
      density_count: 60,
      first_source_time: 2024-05-10 14:20:00 UTC,
      last_source_time: 2024-05-10 14:29:50 UTC,
      max_source_gap: 10 s,
      density_mean: 3.2e-12 kg/m^3,
      density_median: 3.1e-12 kg/m^3,
      density_min: 2.8e-12 kg/m^3,
      density_max: 3.7e-12 kg/m^3
    },
    ...
  ]
}
```

這個 writer 只重建 `swarm_a_density_10min`，不讀寫 `swarm_a_analysis_10min`。

## [4] raw density + 10-minute density -> event baseline SQLite [done]

Storage: `data/swarm_a_phase1_rebuild.sqlite`, table `swarm_a_density_event_baseline_10min`.

```text
satellite_orbit/phase2/prep_density_event_baseline.py
  -> write_density_event_baselines()

read swarm_a_density from month start through event peak + 72 h
classify observed orbit from continuous latitude crossings
ignore a crossing or direction across source gap > 60 s
reference pool: month start through peak - 24 h
match only earlier references with same direction,
latitude +/- 1 deg, altitude +/- 5 km, local solar time +/- 15 min
median one density median per reference orbit
require at least 5 reference orbits per raw source point
aggregate accepted raw baselines into UTC [time_us - 600 s, time_us) bins
read swarm_a_density_10min for observed density coverage
replace only swarm_a_density_event_baseline_10min
```

```text
SQLite input
{
  swarm_a_density: [DensityRecord, ...],
  swarm_a_density_10min: [Density10Minute, ...]
}
```

```text
SQLite output
{
  swarm_a_density_event_baseline_10min:
  [
    {
      event_id: "2024-05" | "2025-11",
      time: 2024-05-10 14:30:00 UTC,
      density_count: 60,
      max_source_gap: 10 s,
      density_mean: 3.2e-12 kg/m^3,
      baseline_source_count: 60,
      baseline_density_median: 2.1e-12 kg/m^3,
      baseline_reference_orbit_count_min: 5,
      baseline_reference_orbit_count_median: 18,
      density_ratio_median: 1.5,
      control_match_status: "ok"
    },
    ...
  ]
}
```

固定個案是 `2024-05` peak `2024-05-11 02:14 UTC` 與 `2025-11` peak `2025-11-12 03:59 UTC`；各自存 864 個 10-minute rows。coverage gate 是 `density_count >= 30` 且 `max_source_gap_s <= 120`，baseline gate 是 `baseline_source_count >= 30`。`control_match_status` 會記錄 `ok`、`insufficient_density_coverage`、`insufficient_baseline_sources` 或兩個失敗原因的組合。

這個 table 還沒有讀取或寫入 `swarm_a_analysis_10min`。

## [5] (plan) density baseline + Phase 1 analysis -> case comparison SQLite

第一個完成個案是 `2024-05`。`2025-11` 目前只有 `20 / 864` rows 的 `control_match_status = "ok"`，保留作 coverage-limited case，不先當作第一個科學結果。

Storage target: `data/swarm_a_phase1_rebuild.sqlite`, new derived table `swarm_a_density_case_comparison_10min`。不更新或刪除任何既有 table。

```text
Input
  swarm_a_density_event_baseline_10min
  [{event_id, time_us, density_*, baseline_density_*, density_ratio_median,
    control_match_status}, ...]

  swarm_a_analysis_10min
  [{time_us, da_dt_12h_backward_m_day, pod_count, max_pod_gap_s,
    sym_h_nt, ap_now, f107_sfu, f107a_sfu, quality_flags}, ...]
```

```text
Process
  select event_id = "2024-05"
  left join baseline rows to analysis rows on time_us
  retain all 864 event 10-minute rows
  copy density, baseline, space-weather, decay, POD coverage, and status fields
  do not interpolate missing density, baseline, POD, or space-weather values
  do not calculate causal coefficients or make a causal claim
```

```text
Output
  swarm_a_density_case_comparison_10min
  [
    {
      event_id: "2024-05",
      time_us,
      density_mean_kg_m3,
      baseline_density_median_kg_m3,
      density_ratio_median,
      control_match_status,
      da_dt_12h_backward_m_day,
      pod_count,
      max_pod_gap_s,
      sym_h_nt,
      ap_now,
      f107_sfu,
      f107a_sfu,
      analysis_quality_flags
    },
    ...
  ]
```

第一個 case 完成後，`2025-11` 與未來新 density event 都使用相同 Input -> Process -> Output contract；coverage 或 baseline 不足的 row 必須留在 output，不能消失。
