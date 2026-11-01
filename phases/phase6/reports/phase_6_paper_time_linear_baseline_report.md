# Phase 6 論文時間線性背景結果

## 決定

目前不用逐場平靜日 selection，改用一條隨時間連續變化的直線。起點是論文 2024-05-04 quiet day 的 `-19.91 m/day`；終點是 2026-01-31 quiet day的 `-79.43 m/day`。

## 公式

從 2024-05-04 12:00 UTC 起，每過一天，背景下降率增加 `0.093438 m/day`。負號表示半長軸下降：

$$
r(t)=-19.91-0.093438D(t)\quad\text{m/day},
$$

其中 $D(t)$ 是事件 `t0` 距離 2024-05-04 12:00 UTC 的天數。每場只再做：

```text
paper expected change = r(t0) * actual event duration
extra loss = paper expected change - observed six-day change
```

`extra loss > 0` 代表實際下降比該時點的線性背景更快。

## 結果

2023--2026 的 25 場全部可評估；20 場為正值。

| Storm | Rate m/day | Method | Observed m | Expected m | Extra loss m | Increased |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| S20230805T0546 | 5.62 | backward extrapolation | -163.9 | 33.5 | 197.4 | 1 |
| S20231021T0728 | -1.58 | backward extrapolation | -285.1 | -9.4 | 275.7 | 1 |
| S20231105T1654 | -3.02 | backward extrapolation | -387.1 | -18.0 | 369.1 | 1 |
| S20231201T1330 | -5.43 | backward extrapolation | -283.4 | -32.4 | 251.1 | 1 |
| S20240303T1800 | -14.14 | backward extrapolation | -305.2 | -84.1 | 221.1 | 1 |
| S20240324T1621 | -16.10 | backward extrapolation | -408.1 | -95.7 | 312.4 | 1 |
| S20240419T1921 | -18.54 | backward extrapolation | -462.6 | -110.2 | 352.4 | 1 |
| S20240511T0214 | -20.53 | interpolation | -423.0 | -120.7 | 302.4 | 1 |
| S20240628T1206 | -25.05 | interpolation | -366.4 | -148.8 | 217.6 | 1 |
| S20240804T1704 | -28.53 | interpolation | -404.4 | -169.4 | 235.0 | 1 |
| S20240812T1652 | -29.27 | interpolation | -642.0 | -173.8 | 468.2 | 1 |
| S20240917T0424 | -32.59 | interpolation | -405.4 | -193.4 | 212.0 | 1 |
| S20241010T2314 | -34.81 | interpolation | -563.0 | -206.5 | 356.6 | 1 |
| S20241109T1237 | -37.57 | interpolation | -676.1 | -222.7 | 453.4 | 1 |
| S20250101T1640 | -42.54 | interpolation | -625.2 | -254.6 | 370.5 | 1 |
| S20250416T1743 | -52.36 | interpolation | -522.7 | -312.7 | 210.0 | 1 |
| S20250517T0516 | -55.20 | interpolation | -285.8 | -326.0 | -40.2 | 0 |
| S20250601T1030 | -56.63 | interpolation | -315.3 | -334.4 | -19.0 | 0 |
| S20250613T2015 | -57.79 | interpolation | -269.9 | -341.2 | -71.2 | 0 |
| S20250930T0759 | -67.92 | interpolation | -658.6 | -400.5 | 258.1 | 1 |
| S20251112T0359 | -71.92 | interpolation | -633.8 | -428.4 | 205.4 | 1 |
| S20260120T1152 | -78.40 | interpolation | -631.1 | -466.4 | 164.7 | 1 |
| S20260321T0139 | -83.97 | forward extrapolation | -432.3 | -499.1 | -66.7 | 0 |
| S20260402T0841 | -85.12 | forward extrapolation | -562.4 | -505.8 | 56.6 | 1 |
| S20260418T0754 | -86.61 | forward extrapolation | -323.6 | -514.5 | -190.9 | 0 |

## 主張界線

- 每場按實際日期取得不同 rate，2025 也沒有固定年度值。
- 兩錨點之間 15 場是內插；錨點前 7 場與錨點後 3 場是外推。
- 2023-08-05 外推為 `+5.62 m/day`，等於背景半長軸上升。這是延長直線造成的數學結果，不是可信的 drag 背景。
- 兩個錨點的高度約為 480 km 與 430 km，local time 也不同。這條線把時間、軌道高度與 local time 的共同變化混在一起。
- 目前只能說「相對於這條簡化背景線的描述性差異」，不能說是已校準的磁暴因果量。

論文來源：Tulasi Ram et al. (2026), [Quasi-Homologous Solar Flares and Impacts on Thermospheric Density and Satellite Orbital Drag](https://doi.org/10.1029/2026GL125768)。資料契約見[論文時間線性背景血緣](../docs/lineage/phase6_paper_time_linear_baseline.md)。
