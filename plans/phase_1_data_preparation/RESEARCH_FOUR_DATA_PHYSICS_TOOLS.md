# 四組資料的物理連結與現成工具

日期：2026-10-17
狀態：研究完成；未改程式；未建立 derived table。

## 結論

四組資料不是代入單一公式就能得到因果關係。可驗證的主線是：

```text
POD {time, r, v}
  -> mean orbit {mean_a_m, da_dt_m_day}

POD {time, lat, lon, altitude}
+ Space weather {F10.7, F10.7A, Ap[7]}
  -> NRLMSIS {model_density_kg_m3}

DNSAACC {observed_density_kg_m3}
  - model_density_kg_m3
  -> density_residual / density_ratio

{mean_a, da_dt, observed/model density, F10.7, Ap, SYM-H, AE}
  -> storm-response analysis
```

`SYM-H`、`AE` 是地磁擾動的解釋欄位；不是 NRLMSIS 2.0 的標準輸入。

## 現有資料能直接構成的輸入

```text
swarm_a_states
{
  time_us,
  position_m: [x, y, z],
  velocity_m_s: [vx, vy, vz],
  frame: ITRF in raw loader
}

space_weather
{
  f107_sfu,
  f107a_sfu,
  f107a_last81_sfu,
  ap_daily,
  ap_now,
  ap_3h,
  ap_6h,
  ap_9h,
  ap_12_to_33h_avg,
  ap_36_to_57h_avg
}

geomagnetic
{
  sym_h_nt,
  ae_nt
}

swarm_a_density
{
  density_kg_m3,
  altitude_m,
  latitude_deg,
  longitude_deg,
  local_solar_time_h
}
```

## 推薦工具與產物

### [A] Orekit: POD -> mean orbit

用途：把 POD 的 osculating state 轉成可分析長期變化的 orbit quantity。

```text
ITRF {time, r, v}
  -> GCRF {time, r, v}
  -> osculating orbit
  -> Brouwer-Lyddane mean orbit
  -> {mean_a_m, e, i_rad, ...}
  -> 10-minute {mean_a_m, da_dt_m_day}
```

Orekit 的 frame 文件將 ITRF 定義為 terrestrial frame、GCRF 定義為 celestial frame；frame transform 可處理位置與速度導數。[Orekit Frames architecture](https://test.orekit.org/site-orekit-development/architecture/frames.html)

`KeplerianOrbit` 的半長軸單位為 m、角元素為 rad，且輸入 frame 必須是 pseudo-inertial；近圓軌道的 element representation 要審核，不能只因 API 可用就假定每個 Keplerian angle 穩定。[Orekit KeplerianOrbit API](https://test.orekit.org/site-orekit-13.1.2/apidocs/org/orekit/orbits/KeplerianOrbit.html)

`BrouwerLyddanePropagator.computeMeanOrbit(...)` 提供 osculating-to-mean conversion；其解析模型處理 J2 至 J5，不是大氣阻力模型。[Orekit analytical propagation API](https://www.orekit.org/site-orekit-latest/apidocs/org/orekit/propagation/analytical/package-summary.html)

推薦範圍：P1.5 先以 synthetic case 與真實 POD residual 驗證 mean-orbit contract，通過後才寫 `mean_a_m` 與 `da_dt_m_day`。

不推薦：目前的 instantaneous `semi_major_axis_m` 直接平滑後稱為 decay；本專案已量到 km 級 short-period variation，該方法已淘汰。

### [B] POD state -> instantaneous angular motion

用途：描述衛星當下的運動，不是 drag 或 decay 的替代量。

```text
GCRF {r_m, v_m_s}
  -> h_m2_s = r x v
  -> omega_rad_s = |h| / |r|^2

mean_a_m
  -> mean_motion_rad_s = sqrt(mu_m3_s2 / mean_a_m^3)
```

`omega_rad_s` 是 state 的瞬時角速度；`mean_motion_rad_s` 只在 mean semi-major axis 已被定義後才有清楚的長期軌道意義。兩者都只需要 POD 與既有 Earth `mu`，不需要 density 或 weather。

推薦範圍：作為 P1.5 diagnostic column 或 quality audit。

不推薦：把 density 帶入上述式子，或把 `omega` 當大氣阻力。

### [C] NRLMSIS 2.0: 軌道位置 + weather -> model density

用途：在 Swarm 所在時間、地點，計算模型中性總質量密度，作為 DNSAACC observation 的比較基準。

```text
POD / density location
{
  UTC,
  altitude_km,
  geodetic_lat_deg,
  lon_deg
}
+ weather
{
  F10.7_previous_day,
  F10.7A_81_day,
  Ap[7]
}
  -> NRLMSIS 2.0
  -> {model_density_kg_m3, temperature_K, species_density...}
```

NRLMSIS 2.0 官方程式與資料樣本由 NRL 發布。[NRLMSIS official directory](https://map.nrl.navy.mil/map/pub/nrl/NRLMSIS/)

官方模型論文列出：模型需要 F10.7、81-day F10.7 average、Ap；storm-time 模式可使用 3-hour Ap history，並依賴時間與地理位置。[NRLMSIS 2.0 paper](https://repository.library.noaa.gov/view/noaa/53074/noaa_53074_DS1.pdf)

推薦範圍：

```text
observed_density_kg_m3 / model_density_kg_m3
  -> density_ratio

observed_density_kg_m3 - model_density_kg_m3
  -> density_residual_kg_m3
```

這兩個量能把 solar-cycle / location baseline 與 observation 的偏離分開，適合和 `Ap`、`SYM-H`、`AE`、mean-orbit response 並列。

需要先確認：模型標準 retrospective input 通常描述為 centered 81-day average；資料庫同時存有 `f107a_sfu` 與因果分析用 `f107a_last81_sfu`。實作前必須明定哪個欄位對應 NRLMSIS，不能默默替換。

不推薦：將 NRLMSIS output 當成真實觀測，或只用 `SYM-H` / `AE` 取代官方 Ap vector 作 NRLMSIS input。

### [D] DNSAACC: observation density

用途：提供衛星所在位置的 thermospheric mass-density observation。

```text
DNSAACC
{
  UTC,
  density_kg_m3,
  altitude_m,
  latitude_deg,
  longitude_deg,
  local_solar_time_h
}
  -> observed density at Swarm-A location
```

ESA product definition 描述 DNSAACC 為沿軌 UTC time series，cadence 10--30 s，含 density uncertainty 與 quality flag；處理使用 calibrated accelerometer、position/velocity、attitude 與 aerodynamic/radiation-pressure / thermosphere models。[ESA DNSAACC product definition](https://swarm-diss.eo.esa.int/?do=download&file=swarm%2FMultimission%2FCombined_Mission_Data%2FConjunction%2FSW-TN-DUT-GS-129-01_TOLEOS_Product_Definition_Document.pdf)

推薦範圍：先保留 product quality / uncertainty（目前 raw schema 尚未存），再做 10-minute robust aggregation，例如 `{median_density, count, spread}`。需先核對實際 CDF 的 quality / uncertainty variable 名稱。

不推薦：把 DNSAACC 當完全獨立於軌道與衛星模型的 ground truth；它本身是 accelerometer-derived product，應保存 product version / quality metadata。

### [E] SYM-H / AE: storm descriptors

用途：標示與量化地磁擾動時段，作為比較與分層欄位。

```text
SYM-H {1-minute, nT}
  -> ring-current / Dst-like storm level

AE {1-minute, nT}
  -> auroral electrojet activity
```

Kyoto WDC 說明 SYM-H 類似 Dst；AE 反映高緯電流活動。[Kyoto geomagnetic data guide](https://wdc.kugi.kyoto-u.ac.jp/wdc/expdata.html)

AE 由 auroral-zone station 的 horizontal magnetic variation 建構，`AE = AU - AL`，代表 overall electrojet activity。[Kyoto AE definition](https://wdc.kugi.kyoto-u.ac.jp/aedir/ae2/onAEindex.html)

推薦範圍：

```text
10-minute analysis row
{
  sym_h_mean_nt,
  sym_h_min_nt,
  ae_mean_nt,
  ae_max_nt,
  source_time_us
}
```

不推薦：拿 `SYM-H` 或 `AE` 直接算 density、drag acceleration、或直接覆寫 Ap。

## 四資料可解釋關係

```text
space_weather {F10.7, F10.7A, Ap[7]}
  -> NRLMSIS baseline density

DNSAACC observed density - NRLMSIS baseline density
  -> density anomaly

geomagnetic {SYM-H, AE}
  -> storm phase / high-latitude activity descriptor

mean orbit {mean_a, da_dt}
  <- compare with density anomaly and storm descriptor
```

這是 observation + model + response 的關係，不是已識別的因果係數。任何 lag、correlation、regression 都要在 P1.5 mean-orbit gate 通過、資料 coverage 和 product quality 釘死後才可做。

## 明確不能從現有四資料得出的量

```text
density + position
  -/-> drag acceleration
  -/-> ballistic coefficient
  -/-> causal decay rate
```

drag acceleration 至少還需要 `{Cd, area_m2, mass_kg}` 或可辨識的 ballistic coefficient，以及相對大氣速度 / atmosphere co-rotation 定義。現有 raw tables 沒有這些受控衛星參數；不可假設後寫入資料集。

## 建議的最小下一步

1. P1.5：以 Orekit mean-orbit conversion 定義與驗證 `mean_a_m`；先不寫 drag propagator。
2. density：審核一個實際 DNSAACC CDF 的 quality / uncertainty 欄位，再決定 raw schema 是否應補 source metadata。
3. P1.6：以完全版 `Ap[7]` 組 NRLMSIS input；明定 `f107a_sfu` 或 `f107a_last81_sfu` 的分析語義。
4. P1.7：只在以上 contract 固定後建立 `{observed_density, model_density, density_ratio, storm descriptors, mean_a, da_dt}` 的 derived analysis table。

## 來源範圍

僅使用 Orekit、NRL、ESA、Kyoto WDC 的官方文件或官方發布論文。沒有使用 blog、套件二手文件或非官方教學作為結論依據。
