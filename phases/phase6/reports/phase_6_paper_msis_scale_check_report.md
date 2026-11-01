# Phase 6：2024 校準、2026 跨時間檢查

## 結果

固定 2024 conversion scale 後，NRLMSIS 2.0 對 2026 平靜遞減率的預測是 `23.25 m/day`；論文值是 `79.43 m/day`。低估 `56.18 m/day`，相對誤差 `-70.7%`。

**判定：這個比例不能直接跨到 2026 使用。**

## 第一步：只用 2024 決定比例

2024-05-04 的輸入：

| 量 | 值 |
| --- | ---: |
| 論文平靜遞減率 | 19.91 m/day |
| NRLMSIS 平靜日平均密度 | 1.262e-12 kg/m³ |
| Swarm-A 日平均高度 | 482.88 km |
| 日平均半長軸 | 6,845.60 km |
| conversion scale | 0.003495 m²/kg |

兩天的 NRLMSIS 都保留當日 F10.7 與 F10.7A，七欄 Ap 固定為 `4`。conversion scale 只在這一步計算一次。

## 第二步：固定比例預測 2026

2026-01-31 的輸入與結果：

| 量 | 值 |
| --- | ---: |
| NRLMSIS 平靜日平均密度 | 1.479e-12 kg/m³ |
| Swarm-A 日平均高度 | 435.39 km |
| 日平均半長軸 | 6,797.90 km |
| 由固定 scale 預測的遞減率 | 23.25 m/day |
| 論文平靜遞減率 | 79.43 m/day |
| signed error | -56.18 m/day |
| relative error | -70.7% |

NRLMSIS 平靜密度只增加 `17.2%`；論文遞減率增加到原本的 `3.989` 倍。半長軸平方根修正很小，因此固定 2024 scale 只能預測到原本約 `1.168` 倍，也就是 `23.25 m/day`。

## 可以下的結論

- 2024 calibration 本身可以完成，model-specific scale 是 `0.003495 m²/kg`。
- 該 scale 配合 NRLMSIS quiet density ratio，無法重現 2026 論文 rate。
- 不應把 2026 論文值拿來重新調第二個 scale；那會失去跨時間驗證。
- 目前不能用這個固定 scale 直接推全部 25 場磁暴。

## 這個失敗代表什麼

目前無法只靠這兩天分辨原因。可能來源包括 NRLMSIS 的跨高度／solar state density ratio、Swarm-A 姿態或有效迎風面積變化、daily slope estimator 差異，或論文兩個 quiet day 的其他環境差異。

這不是 NRLMSIS 與 POD 的完整驗證，也不是 physical `B_eff` 校準。它只否定目前最簡單的假設：`2024 的單一 conversion scale` 可以不變地套到 `2026`。

資料契約見[跨時間 scale 檢查血緣](../docs/lineage/phase6_paper_msis_scale_check.md)。論文來源：Tulasi Ram et al. (2026), [Quasi-Homologous Solar Flares and Impacts on Thermospheric Density and Satellite Orbital Drag](https://doi.org/10.1029/2026GL125768)。
