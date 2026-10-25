# Phase 2 原始資料來源查核

## 結果與界線

查核日期：2026-10-22。下列是來源文件能支持的事實；本機現行實作與輸出以[Phase 2 計畫](PLAN.md)為準。

- SuperMAG `SME` 是 1-minute 地磁指數；`indices.php` 回傳的 `tval` 究竟標示該分鐘觀測區間的起點或中心，尚未查到直接規格。SuperMAG 方法論只確認各站磁場先以 *centered boxcar average* 重採樣為 1-minute，不能據此替最終 SME API 時間戳下結論。[SuperMAG 方法論](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2012JA017683)、[SuperMAG 資料描述](https://spase-metadata.org/CNES/NumericalData/CDPP-AMDA/Indices/Ground_Based/ground-based-sme.html)
- GFZ 官方 API 的 Kp／ap 時間代表 3-hour **區間起點**；Kyoto HAPI 提供的 Kp／ap 時間代表**區間中心**。同一物理區間在兩個介面有不同標記方式，不可直接以時間戳相等合併。[GFZ 下載與 API 說明](https://kp.gfz.de/en/data)、[Kyoto HAPI 說明](https://wdc.kugi.kyoto-u.ac.jp/hapi/)
- `pymsis` 官方 `get_f107_ap()` 回傳前一日 F10.7、以目標日期為中心的 81-day F10.7A，以及 7 欄 ap history。早期 pilot 曾自算 trailing 81-day F10.7A；現行 P2.3–P2.6 已改用 CelesTrak 來源欄 `F10.7_OBS_CENTER81`，不再沿用該替代選擇。[pymsis 輸入文件](https://swxtrec.github.io/pymsis/reference/generated/pymsis.utils.get_f107_ap.html)、[NASA NRLMSIS 2.0 輸入說明](https://ccmc.gsfc.nasa.gov/models/NRLMSIS~2.0/)
- Kyoto HAPI 的 `min_ae`、`min_asysym` 都提供每列 `versionCode` 與來源 `modificationDate`；`versionCode` 的十位數表示 real-time、provisional、final，個位數表示重新轉換代數。AE 可混用不同處理等級，故須逐列保存版本；SYM-H 當前 HAPI metadata 描述 best-available 目前僅有 provisional。[Kyoto AE metadata](https://wdc.kugi.kyoto-u.ac.jp/hapi/info?dataset=min_ae)、[Kyoto SYM metadata](https://wdc.kugi.kyoto-u.ac.jp/hapi/info?dataset=min_asysym)

## SuperMAG SME

- 原始論文指出 SME 使用比傳統 AE 更多的測站；它與 nightside auroral power 高度相關，但不是直接量測 Joule heating。[Newell 與 Gjerloev 2011](https://agupubs.onlinelibrary.wiley.com/doi/abs/10.1029/2011JA016779)
- 本地 `data/sme/manifest_p2_0_sme.json` 登錄 1,096 個日檔；原始 CSV 自 2026-05-07 02:35 UTC 起到 2026-06-30 結束共 79,045 分鐘為 `SME = 999999`、`SMEnum = 0`，這是**本地檔案稽核觀察**，不是已查得的官方通用填充值規格。[本地稽核](../../data/sqlite/2023/phase2_p2_0_source_audit.json)
- CDPP/AMDA 的 SuperMAG SME 資源描述目前列出 1-minute cadence，時間範圍終點為 2026-05-07 23:59 UTC；它與本地末段缺值相容，但不能證明此後官方永遠沒有資料，亦不能取代逐筆稽核。[CDPP/AMDA 目錄](https://amda.irap.omp.eu/help/auto/ground-based-sme)
- 本機下載請求包含 `sme,num`，回傳欄名是 `tval,SME,SMEnum`。尚未找到 SuperMAG 一手文件直接定義 `SMEnum` 欄位的涵蓋站點集合或品質門檻；暫把它當來源提供的數量欄並保存原值，不自行賦予「全球可靠度」的物理意義。

## GFZ ap 與時間可用性

- GFZ 提供 3-hour `ap` 與 daily `Ap`；可由官方 HTTPS 歷史檔或 `/app/json/` API 取得。API 支援 `index=ap` 與 `status=def`；API `time` 是該指數**區間起點**。下載檔需保存來源、下載時間與 definitive／nowcast 狀態。[GFZ 下載頁](https://kp.gfz.de/en/data)
- `ap` 是由 Kp 轉換的 three-hour equivalent planetary amplitude，**不是三小時變化率**。[GFZ 原始研究](https://gfzpublic.gfz-potsdam.de/rest/items/item_5004610_3/component/file_5007000/content)
- GFZ nowcast 可能在 3-hour 區間結束前先發布初估，之後更新；因此「等區間結束才把最終 `ap` 用於特徵」是本專案的保守可用性規則，不是宣稱官方只在區間結束後發布。[GFZ nowcast 方法論](https://gfzpublic.gfz-potsdam.de/rest/items/item_5004610_3/component/file_5007000/content)
- Kyoto HAPI 把同一類 3-hour Kp／ap 標為區間中心 `01:30, 04:30, ...`；若用京都介面，須先還原區間 `[start,end)`，不能把中心戳當 GFZ API 的起點。[Kyoto HAPI 說明](https://wdc.kugi.kyoto-u.ac.jp/hapi/)

## NRLMSIS 2.0 與 `pymsis`

- NASA 列出的 NRLMSIS 2.0 輸入包括位置、當地時、前一日 daily F10.7、81-day F10.7 平均和地磁指數；NASA 該頁沒有指定 81-day 平均的中心或尾隨定義。[NASA CCMC](https://ccmc.gsfc.nasa.gov/models/NRLMSIS~2.0/)
- `pymsis` 的自動驅動明定 F10.7A 為 **centered** 81-day average。若要求模型輸入只用目標時間以前的觀測，自算 trailing 81-day 可以滿足因果政策，但其輸出不可與標準 `pymsis` 自動輸入結果混作同一設定。此句後半是本專案方法推論。[pymsis `get_f107_ap`](https://swxtrec.github.io/pymsis/reference/generated/pymsis.utils.get_f107_ap.html)
- `pymsis` 的 ap history 有 7 欄：daily Ap、當前及往前 3／6／9 小時的 3-hour ap、過去 12–33 小時與 36–57 小時各 8 個 3-hour ap 的平均。`geomagnetic_activity=-1` 才使用詳細的 storm-time history；呼叫時必須指定 `version=2.0`，因公開 API 文件所列預設版本為 2.1。[pymsis 計算介面](https://swxtrec.github.io/pymsis/reference/generated/pymsis.msis.calculate.html)
- `pymsis` 自動下載的底層資料是 CelesTrak `SW-All.csv`；來源可能包含內插或預報，套件只發警告，研究者仍須檢查實際使用的 Ap／F10.7 類別。不能把它寫成「原始 GFZ 觀測」。[pymsis 下載文件](https://swxtrec.github.io/pymsis/reference/generated/pymsis.utils.download_f107_ap.html)

## 尚未證實與下游限制

- SuperMAG `indices.php` 的 `tval` 觀測區間位置、官方完整 fill-code 表，以及 `SMEnum` 精確定義未查得。不可把「每 60 秒一個時間戳」直接推成「戳記為區間起點」。採保守可用時刻前，應聯絡來源或取得明確 metadata。
- SME 末段長缺口不能用重試、短缺口內插或權重重新歸一化產生觀測值；後續事件應記錄來源覆蓋並排除不合格區間。此為根據本地稽核與缺值處理契約的實作推論。[本地 lineage](../../data_lineage/README.md)
- GFZ definitive、GFZ nowcast、CelesTrak 衍生資料與京都 HAPI 的來源／版本／時間戳語意不同。要跨來源比對，先轉成明確 `{interval_start_utc, interval_end_utc, available_at_utc, status}`，不要直接以原時間戳 join。此為由各來源規格推出的本專案資料契約。[GFZ](https://kp.gfz.de/en/data)、[Kyoto](https://wdc.kugi.kyoto-u.ac.jp/hapi/)、[pymsis](https://swxtrec.github.io/pymsis/reference/generated/pymsis.utils.download_f107_ap.html)
