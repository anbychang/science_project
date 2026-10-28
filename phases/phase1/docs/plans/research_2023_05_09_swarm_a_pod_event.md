# 2023-05-09 Swarm-A POD 異常時段：官方文件查核

## 結論

- 查核時段：`2023-05-09 05:20:00` 至 `06:20:00 UTC`。
- ESA 已公告 `2023-04-26` 至 `2023-06-07` 的 Swarm-A/C orbit-raise campaign；本時段落在該 campaign 內。因此自然軌道衰減分析必須排除這個 date-level window。公開資料仍未提供每次 firing 的精確時刻。
- 本研究目前採用的當日 ESA 檔案是後續重處理產物：檔名版本 `0203`，其 HDR 的 `Creation_Date` 是 `2026-08-25`，不是 2023 年當時的 operational 產物。因此不能用它倒推「2023 當日地面處理沒有問題」。
- 該 ZIP 的 HDR 只有檔案級 `Product_Err=0` 與 `Quality_Indicator=000`。ESA catalog 指定的品質資料是獨立 `SP3xVAL_2_` validation report；HDR 這兩個值本身不能用來宣告該時段每一個 epoch 都通過品質或沒有 maneuver。
- SP3 資料中的 position/velocity 定義與單位沒有歧義：中心質量的 Earth-fixed 動態 state、10 秒 cadence、position `km`、velocity `dm/s`。但實際 2023-05-09 檔案 SP3 header 標記為 `IGS20`，而 catalog 以一般名稱寫為 ITRF；後續 frame conversion 必須以檔案的 `IGS20` label 為準，不應把兩者無條件當成同一個未註明的 frame。

## 官方產品定義

ESA 與 TU Delft 的 `SP3xCOM_2_` catalog 對 `SW_OPER_SP3ACOM_2_` 指定如下。

| 項目 | 官方定義 | 直接來源 |
|---|---|---|
| 產品 | Swarm-A 的 precise reduced-dynamic orbit solution。 | [ESA/TU Delft product catalogue](https://swarm-disc.github.io/product-catalogue-tools/SW_SP3xCOM_2_.html) |
| state | 每顆衛星 center of mass 的 dynamic position 與 velocity time series，Earth-fixed ITRF。 | [ESA/TU Delft product catalogue](https://swarm-disc.github.io/product-catalogue-tools/SW_SP3xCOM_2_.html) |
| 時間與 cadence | GPS time，10 秒。 | [ESA/TU Delft product catalogue](https://swarm-disc.github.io/product-catalogue-tools/SW_SP3xCOM_2_.html) |
| 單位 | position 為 `km`；velocity 為 `dm/s`。 | [ESA/TU Delft product catalogue](https://swarm-disc.github.io/product-catalogue-tools/SW_SP3xCOM_2_.html) |
| 檔案時間窗 | 30 小時有 overlap 的 daily batch，選中央 24 小時輸出。 | [ESA/TU Delft product catalogue](https://swarm-disc.github.io/product-catalogue-tools/SW_SP3xCOM_2_.html) |
| 品質來源 | catalog 將 quality indicator 指向獨立的 `SP3xVAL_2_` validation report。 | [ESA/TU Delft product catalogue](https://swarm-disc.github.io/product-catalogue-tools/SW_SP3xCOM_2_.html) |

這支持目前以完整 `{XYZ, VX, VY, VZ}` 計算半長軸；`XYZ` 單獨不是此產品所定義的完整軌道 state。

## 事件日原始 ESA 檔案

查核的 source 是：

`SW_OPER_SP3ACOM_2__20230508T235942_20230509T235942_0203.ZIP`

[ESA SW-DISS 直接下載](https://swarm-diss.eo.esa.int/?do=download&file=swarm%2FLevel2daily%2FLatest_baselines%2FPOD%2FRD%2FSat_A%2FSW_OPER_SP3ACOM_2__20230508T235942_20230509T235942_0203.ZIP)

解讀 ZIP 內官方 `HDR` 與 `sp3` header 的結果：

| 檢查 | 觀測值 | 能得出的結論 |
|---|---|---|
| `Validity_Start` / `Validity_Stop` | `2023-05-08T23:59:42` 至 `2023-05-09T23:59:42 UTC` | 目標時段在同一份 source file 內，不是相鄰 ZIP 的交界。 |
| `File_Version` / `Creator_Version` | `0203` / `44.88` | 這是選取的 product baseline 版本。 |
| `Creation_Date` / `Proc_Time` | `2026-08-25T09:10:47 UTC` | 這份 2023 coverage 的檔案經過後續處理；不可視為當天即時 POD 產物。 |
| HDR `Product_Err` | `0` | 只記錄 HDR 欄位值；無可用規格把它轉成逐 epoch 精度或 maneuver 判定。 |
| HDR `Quality_Indicator` | `000` | 同上；不能取代 catalog 指定的獨立 `SP3xVAL_2_`。 |
| SP3 第一行 | `#dV ... IGS20 FIT TUD` | 本檔明示 velocity records，並標記 `IGS20` frame label。轉到 GCRF 時必須保留此 provenance。 |
| `P` / `V` record | `P` 與 `V` record 長度為 60 字元；沒有 trailing per-epoch maneuver/accuracy 欄位 | 該 source 內沒有可直接套用的 per-epoch maneuver/position-sigma filter。 |

上表的事件日欄位均來自同一個官方 ZIP；直接下載連結在本節開頭。`Product_Err=0` 與 `Quality_Indicator=000` 是原樣摘錄，沒有賦予其未經文件支持的品質含義。

## `SP3xVAL_2_` 與公開事件紀錄的可得性

1. 官方 catalog 確認 `SP3xVAL_2_` 是 `SP3xCOM_2_` 的獨立 validation report，而不是此 ZIP 的 epoch 欄位。[來源](https://swarm-disc.github.io/product-catalogue-tools/SW_SP3xCOM_2_.html)
2. 本機 `phases/phase0/data/raw/swarm_a_pod/` 的下載集僅保存 `SP3ACOM` ZIP；沒有 2023-05-09 的 `SP3AVAL_2_`。所以目前資料庫無法對事件時段套用官方 validation 結果。
3. 本次查核也檢索 ESA Swarm Data Access、Swarm handbook/catalogue、ESA Swarm operations 公開頁，以日期、`Swarm-A`、`maneuver`、`orbit`、`POD`、`SP3` 為組合；沒有找到能直接指向 `2023-05-09 05:20–06:20 UTC` 的公開事件或品質紀錄。ESA 說明 Swarm 的飛控確實包含 flight dynamics 與 maneuver，但該概述並不是本事件的日誌。[ESA Swarm operations](https://www.esa.int/Enabling_Support/Operations/Swarm_operations)

因此目前正確的狀態是：`official_campaign_status: planned_orbit_raise_campaign`；
`official_event_status` 在 05:20–06:20 UTC 的精確 firing 層級仍為 `unknown`。不是
`no_maneuver`，也不是 `quality_passed`。campaign 的官方證據見
`research_2022_2023_orbit_raise_campaigns.md`。

## 對目前分析的限制與下一步

```text
SP3xCOM {IGS20-labelled Earth-fixed r, v}
  -> project GCRF conversion
  -> mean semi-major axis
  -> derivative
```

- 已知：事件日 source 本身沒有 gap、ZIP 邊界，或可讀取的每 epoch maneuver flag 證據。
- 未知：ESA `SP3xVAL_2_` 對此日的 validation 結果；是否有未公開或未被本次公開檢索索引的 mission-operation maneuver record。
- 不能做：因 HDR 的 `000` 或檔案連續性，就把 05:20–06:20 的半長軸結構宣告為物理 drag、無 maneuver，或品質正常。
- 可以做：把完整公告 campaign 日期窗列為 `planned_orbit_raise_campaign`，從自然衰減與 storm 統計排除；這不會刪除 raw POD，也不會宣稱每筆 state 都在 firing。
- 下一個可證偽步驟：取得能覆蓋該日的官方 `SP3AVAL_2_`，保存為獨立 raw source，先定義其時間對齊與欄位語意，再決定能否標記或排除 epoch。若取不到，保留此時段為 `official_event_status: unknown` 並在任何 decay-rate 交付物中列為未驗證區間。
