# Density Data Lineage

```text
DNSAACC ZIP -> CDF records -> DensityRecord -> SQLite
```

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
