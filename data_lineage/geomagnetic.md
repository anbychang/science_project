# Phase 1 Geomagnetic Lineage

```text
SYM-H CSV + AE CSV
  -> geomagnetic
  -> SYM-H in swarm_a_analysis_10min
```

## Raw table

```text
prep_raw_geomagnetic.py -> write_sym_h(), write_ae()

{
  geomagnetic: [
    {time_us, sym_h_nt, ae_nt, sym_h_version, ae_version},
    ...
  ]
}
```

跳過 comment row 與 fill value。AE 在 Phase 1 保留 raw-only。

## Analysis fields

```text
prep_08_analysis_10min.py -> align_sym_h()

{
  sym_h_nt,
  sym_h_left_time_us,
  sym_h_right_time_us
}
```

有 exact SYM-H observation 時直接使用；否則只允許 right source 在 orbit time 後
120 seconds 內的 interpolation。
