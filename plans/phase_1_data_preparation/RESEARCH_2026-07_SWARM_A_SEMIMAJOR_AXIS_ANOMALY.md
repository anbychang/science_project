# 2026-07-21 至 2026-07-23 Swarm-A 半長軸上跳：官方文件查核

## 結論

這不是未標記的資料異常。ESA 官方週報已確認：`2026-07-21` 至 `2026-07-31` 進行
Swarm-A/C lower pair 的 orbit-raising campaign。它直接覆蓋本機半長軸上跳的
`2026-07-21` 至 `2026-07-23` 時段。

因此此時段必須標記為 `planned_orbit_raise_campaign`，從自然軌道衰減與
geomagnetic-storm response 統計排除，並切開 chunk；不能保留為 Q4 audit-only。

官方週報也記錄：

- `2026-07-22 02:13:59` 至 `02:14:05 UTC` 發生 Swarm-A telemetry anomaly，造成
  全部 instrument 的小型 data gap。
- campaign 的十天期間，attitude-control errors 可能影響 L1B/L2 data quality；但這
  不是已證實的 POD orbit-solution failure。
- Swarm-A VFM--ASM residual 在 `7/21`、`7/22`、`7/23` 有 threshold violation；
  standard deviation 在 `7/21`、`7/23` 有 violation。這是 magnetic instrument
  quality evidence，不可誤解為半長軸或 SP3 position/velocity quality flag。

## 第一方官方證據

唯一需要依據的事件文件是 ESA QRAS 的
[Swarm DISC Weekly L1B Report, Week 30 (20--26 July 2026)](https://ftp-qras.earth.esa.int/swarm/swarm_instruments/weekly/2026/swarm--swarm_instruments--weekly--20260720--l1b.pdf)。

| 官方資料 | 日期 / 頁 | 可支持的事實 |
| --- | --- | --- |
| amendment record | first issue `2026-08-14`, p. 3 | 這是事後公開的週報，不是事件當日的即時公告。 |
| orbit-raise description | p. 7 | campaign 為 `2026-07-21` 至 `2026-07-31`；目的是因 solar-maximum atmospheric drag 將 Alpha/A、Charlie/C lower pair 各提升約 `5 km`，避免過早 re-entry。A 有 4 次 maneuver，C 有 2 次長時間 maneuver。 |
| data-quality caveat | p. 7 | campaign 十天內的 attitude-control errors 可能影響 L1B/L2 product quality；A/C along-track separation 暫時由正常 `4..10 s` 變為 `85..90 s`。 |
| Swarm-A telemetry anomaly | p. 8 | `2026-07-22 02:13:59..02:14:05 UTC` telemetry missing；all instruments affected。 |
| VFM--ASM quality observations | p. 10 | A 的 residual threshold violations 為 `7/21`、`7/22`、`7/23`；standard-deviation threshold violations 為 `7/21`、`7/23`。 |
| no stronger orbit-product claim | pp. 9, 21 | report 同時將 attitude observations 列為 `Nominal. Nothing to report`，且 special investigations 為 `Nothing to report`；不可因此宣告 SP3 POD 解算已失效。 |

### maneuver 細節：官方有與沒有的內容

這份 22 頁週報的 campaign 描述只在 p. 7。它明載 date-level window、A/C 對象、
`A=4`、`C=2`、C 為 long-duration manoeuvres，及兩星約 `5 km` altitude raise。
它**沒有**列出六次 maneuver 個別的 UTC、burn start/stop、duration、burn direction、
delta-v、哪一天由哪一顆執行，或精確 altitude increment。因此：

```text
official campaign window: known
per-maneuver UTC / burn geometry: not provided by this weekly report
```

不可從半長軸曲線反推並假稱每一個 10 分鐘上跳就是某次已知 firing。現階段正確規則是
完整 date-level exclusion；若未來拿到 ESA maneuver timeline，再考慮縮窄 exclusion。

### L1B/L2、telemetry 與 SP3 POD 的證據邊界

| 項目 | 文件實際支持 | 不支持的推論 |
| --- | --- | --- |
| L1B/L2 | p. 7 說十天內 attitude-control errors *may have affected* L1B/L2 quality，並說 temporary A/C configuration degraded several L2 products。 | 不能說所有 L1B/L2 product 都失效，或將此語句轉成 POD error。 |
| telemetry gap | p. 8 給出 A 在 `2026-07-22 02:13:59..02:14:05 UTC` 的 missing telemetry，all instruments affected。 | 不能用 6 秒 gap 單獨解釋多日、公里級的 campaign altitude raise。 |
| orbit/attitude monitoring | p. 8 的 orbit check 是 `MODx_SC_1B` medium-accuracy orbit 相對 `GPSxNAV_0` on-board solution；該頁明說相關 threshold 尚未 assessed。p. 9 的 attitude status 是 nominal。 | 這不是 `SP3ACOM` precise reduced-dynamic product 的 validation。 |
| SP3 POD | official `SP3xCOM_2_` catalogue 指定 quality report 為獨立 `SP3xVAL_2_`。 | 沒有 `SP3xVAL_2_` 或另一份明確 POD notice 前，不能宣稱此 campaign 造成 `SP3ACOM` 解算品質失效。 |

ESA QRAS 查詢未顯示在 `2026-07-21..23` 當天公開的 Swarm report；上述 `2026-08-14`
週報是目前找到的日期精確第一方回溯文件。這不降低其對 campaign existence 的證據力，
但需如實保留公告時間。

## 事件日的官方 POD source

frozen rebuild 使用 ESA SW-DISS 的 `SW_OPER_SP3ACOM_2_`。它是 dynamic
center-of-mass position/velocity product；quality report 是獨立的 `SP3xVAL_2_`，
不是 state record 的逐 epoch quality flag。

| source validity UTC | 檔案版本 | official HDR `Creation_Date` | HDR 值 |
| --- | --- | --- | --- |
| `2026-07-20T23:59:42` .. `2026-07-21T23:59:42` | `0203`, creator `44.88` | `2026-08-07T01:09:08` | `Product_Err=0`, `Quality_Indicator=000` |
| `2026-07-21T23:59:42` .. `2026-07-22T23:59:42` | `0203`, creator `44.88` | `2026-08-08T00:34:41` | `Product_Err=0`, `Quality_Indicator=000` |
| `2026-07-22T23:59:42` .. `2026-07-23T23:59:42` | `0203`, creator `44.88` | `2026-08-09T01:05:15` | `Product_Err=0`, `Quality_Indicator=000` |

直接官方檔案：

- [2026-07-21 coverage](https://swarm-diss.eo.esa.int/?do=download&file=swarm%2FLevel2daily%2FLatest_baselines%2FPOD%2FRD%2FSat_A%2FSW_OPER_SP3ACOM_2__20260720T235942_20260721T235942_0203.ZIP)
- [2026-07-22 coverage](https://swarm-diss.eo.esa.int/?do=download&file=swarm%2FLevel2daily%2FLatest_baselines%2FPOD%2FRD%2FSat_A%2FSW_OPER_SP3ACOM_2__20260721T235942_20260722T235942_0203.ZIP)
- [2026-07-23 coverage](https://swarm-diss.eo.esa.int/?do=download&file=swarm%2FLevel2daily%2FLatest_baselines%2FPOD%2FRD%2FSat_A%2FSW_OPER_SP3ACOM_2__20260722T235942_20260723T235942_0203.ZIP)

這些 header 值只描述檔案層 metadata。它們不能否定已公告的 campaign，不能判定
單一 epoch 沒有 maneuver，也不能取代 `SP3xVAL_2_`。產品定義見
[ESA/TU Delft SP3xCOM catalogue](https://swarm-disc.github.io/product-catalogue-tools/SW_SP3xCOM_2_.html)。

## 對流程的必要修正

```text
2026-07-21 .. 2026-07-31
  -> official planned_orbit_raise_campaign
  -> mark unusable for natural-decay / storm-response analysis
  -> terminate preceding chunk and start following chunk
  -> rebuild all downstream mean-orbit, 10-min, backward-12h and analysis tables
```

- date-level exclusion 是資料公開程度所容許的最窄可重現規則；週報提供 maneuver
  數量但不提供每次 firing UTC。
- 不應用 `2026-07-22` 的 6 秒 telemetry gap 單獨解釋整段多日上跳；主因已有
  公開的 orbit-raise campaign。
- 不可把 L1B magnetic residual alert 延伸解讀成 `SP3ACOM` 半長軸公式、單位或
  frame conversion 錯誤。
