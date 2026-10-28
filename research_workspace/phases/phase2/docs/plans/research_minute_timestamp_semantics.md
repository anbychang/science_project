# SME／SYM-H 一分鐘時間戳查證

## 結論

- 京都 HAPI `min_asysym` 的 `05:38:00Z` 是一分鐘資料的**區間中心**，不是 `[05:38:00, 05:39:00)` 的起點，也不是單一瞬間的原始磁力計讀數。官方 metadata 同時給出 `cadence = PT1M` 和 `timeStampLocation = center`，並明說時間戳位於 UT 整分。[京都 `min_asysym` metadata](https://wdc.kugi.kyoto-u.ac.jp/hapi/info?dataset=min_asysym)
- 因此，若以一分鐘寬的時間箱解讀京都值，標為 `05:38:00Z` 的箱約在 `05:37:30–05:38:30Z`；這是由官方「一分鐘、中心戳」推得的名義區間，端點包含規則不影響此處結論。[京都 `min_asysym` metadata](https://wdc.kugi.kyoto-u.ac.jp/hapi/info?dataset=min_asysym)
- SuperMAG 方法論證實：各站原始磁場先用置中 boxcar average 重採樣成一分鐘資料，再進入後續處理；SME 因而不是單一瞬間的原始磁力計讀數。但該論文**沒有定義** `indices.php` 回傳的 `tval` 是最終 SME 所代表分鐘的起點、中心或終點。[Gjerloev（2012），SuperMAG 資料處理方法](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2012JA017683)
- 本機 SME 原始 CSV 只有 `{tval, SME, SMEnum}`，每 60 秒一列，沒有時間戳位置或觀測區間欄位；不能由等間距 `tval` 推出中心／起點語意。[本機 SME 範例](../../../phase0/data/raw/sme/SME_20230803.csv)、[下載程式](../../../phase0/code/data/geomagnetic/down_supermag_sme.py)

## 本機資料與 P2.3 的差異

- 同一組來源標籤 `2023-08-03T05:38:00Z`：京都 CSV 的 `symHValue = -2 nT`，SME CSV 的 `SME = 153.613083 nT`。京都 CSV 首行 metadata 原本就帶 `timeStampLocation = center`；SME CSV 沒有等價 metadata。[京都原始檔](../../../phase0/data/raw/geomagnetic/sym_h_2023-05-14_2023-11-09.csv)、[SME 原始檔](../../../phase0/data/raw/sme/SME_20230803.csv)
- P2.1 把兩個來源的整分時間戳存成同一個 `time_us` key；這是資料對齊 key，不是兩者有相同物理觀測區間的證據。[P2.1 實作](../../code/prep_21_geomag_1min.py)
- 舊 P2.3 v1 曾把該 key 命名為 `minute_start_time_us`，自行建立 `[05:38, 05:39)` 分組格，並在 `05:38:30` 取 Phase 1 軌道量。這不是來源宣告的觀測區間。現行 P2.3 v5 在原始 `05:38:00` 標籤對齊 Phase 1，另記名義區間 `05:37:30–05:38:30`；事件選取端點則以 `t0` 同相位決定。[P2.3 實作](../../code/prep_23_t0_phase_window.py)
- P2.1 的 `kyoto_not_before_time_us = stamp + 30 s` 與 `sme_not_before_time_us = tval + 60 s` 是專案使用的保守觀測完成界線，不是來源實際發布時間。京都的前者可對應名義半分鐘寬的右端；SuperMAG 的後者在 `tval` 位置未明前只是政策假設。[P2.1 實作](../../code/prep_21_geomag_1min.py)

## 決策與未解事項

- P2.3 v5 區分 `source_time_us`、`assumed_support_start_time_us`、`assumed_support_end_time_us` 與來源的 `*_not_before_time_us`。Phase 1 對齊時間是 `source_time_us`。京都軌道對齊採官方中心戳；SME 比照採中心戳是 Anby 同意的工作假設，不是 SuperMAG 已證實的定義。
- 尚未查得 SuperMAG `indices.php` 的 `tval` 時間戳位置、SME 合成後的精確時間支持區間，也未查得兩來源的逐筆發布時間。不可把「一分鐘頻率」「置中 boxcar」「API 時間戳」混成同一主張。
