# 官方 Swarm 軌道下降產品查核

## 結論

查核截至 2026-10-31。**沒有找到可直接取代本專案估計 Swarm-A
磁暴額外下降量或背景下降率的 ESA 官方產品，也沒有找到可下載的
Swarm-A 多事件數表。**

ESA 公開產品停在三種上游量：精密位置與速度、非保守加速度、熱層密度。
它們都沒有 `semi-major-axis decay rate`、quiet-time background decay 或
event-level excess decay 欄位。正式論文公開少數事件結果，但仍由作者從
ESA 軌道產品自行計算，且出版社頁面沒有提供逐事件 CSV、XLS 或其他數值表。

```text
ESA position / velocity 或 acceleration / density
  -> 自行定義軌道下降 estimator
  -> 自行定義 quiet background 與 storm window
  -> 自行積分 rate difference
  -> event-level excess decay
```

## 官方產品逐項核對

| 產品 | 官方實際內容 | 能否直接給下降率或事件額外下降量 |
|---|---|---|
| `SW_SP3xCOM_2_` | 10 s、GPS time、ITRF 的衛星質心 position 與 velocity；日檔、SP3-c | 否 |
| `SW_DNSxPOD_2_` | 30 s 的 POD-derived density、orbit-mean density、位置輔助量與品質旗標 | 否 |
| `SW_DNSxACC_2_` | accelerometer-derived thermospheric density 與位置輔助量 | 否 |
| `ACCxPOD_2_` | 30 s 的三分量 POD-derived non-gravitational acceleration 與品質旗標 | 否 |

### `SW_SP3xCOM_2_`: precise reduced-dynamic orbit

[ESA Swarm Product Handbook](https://swarmhandbook.earth.esa.int/catalogue/SW_SP3xCOM_2_)
將產品定義為每顆衛星質心相對 ITRF 的 dynamic position 與 velocity time
series。產品為 SP3-c，時間步長 10 s；position 單位為 km，velocity 單位為
dm/s。[ESA 產品 DOI 紀錄](https://doi.org/10.57780/esa-8579355)與
[ESA Swarm Data Access 的 POD/RD 入口](https://swarm-diss.eo.esa.int/#swarm/Level2daily/Latest_baselines/POD/RD)
指向相同產品。

產品不提供 semi-major axis、orbit-mean semi-major axis、`da/dt`、背景下降率或
磁暴額外下降量。SP3 是計算這些量的上游軌道解，不是軌道下降結果。

### `SW_DNSxPOD_2_`: POD-derived thermospheric density

[ESA handbook 產品頁](https://swarmhandbook.earth.esa.int/catalogue/SW_DNSxPOD_2_)
列出的 CDF 欄位為：

```text
time
density                  kg/m^3
density_orbitmean        kg/m^3
validity_flag
altitude                 m
latitude                 deg
longitude                deg
local_solar_time         h
```

`density_orbitmean` 是一個 orbital period 內的平均密度，不是 semi-major-axis
下降率。產品由 `ACCxPOD_2_` 的 GPS/POD-derived aerodynamic acceleration
轉成密度，名義時間步長為 30 s；檔案可由
[ESA DNS/POD 入口](https://swarm-diss.eo.esa.int/#swarm/Level2daily/Latest_baselines/DNS/POD)
取得。產品頁同時警告：高軌、低太陽活動時，radiation-pressure model 與
acceleration determination 的誤差可能使密度誤差很大，甚至出現負值。

### `SW_DNSxACC_2_`: accelerometer-derived density

`DNSxACC` 的 `ACC` 指密度來源包含 accelerometer，不代表產品輸出加速度。
[ESA handbook 產品頁](https://swarmhandbook.earth.esa.int/catalogue/SW_DNSxACC_2_)
及 [ESA VirES HAPI 的目前資料契約](https://vires.services/hapi/)列出 Swarm
collection 的欄位為：

```text
Timestamp
Latitude_GD
Longitude_GD
Height_GD
local_solar_time
density
```

其中沒有 semi-major axis 或 decay 欄位。檔案入口為
[ESA DNS/ACC](https://swarm-diss.eo.esa.int/#swarm/Level2daily/Latest_baselines/DNS/ACC)。
密度若要轉為某顆衛星的下降率，仍須衛星幾何、質量、drag coefficient、相對
流速及軌道平均等假設；不能把 density 直接當成下降量。

### `ACCxPOD_2_`: POD-derived non-gravitational acceleration

真正輸出非保守加速度的是 `ACCxPOD_2_`。ESA 的
[Swarm SPC-to-PDGS Interface Control Document，Appendix A](https://www.space.dtu.dk/english/-/media/institutter/space/behold-newdesign_2023/afdelinger/geomagnetism-and-geospace/swarm/invitation-to-tender/esa-eopg-mom-if-17-swarm-spc-to-pdgs-icd-v1-1-signed.pdf)
列出：

```text
time
acc_pod[3]               m/s^2; estimated non-gravitational acceleration X/Y/Z
validity_flag            0 nominal; 1 anomalous
```

這是 30 s acceleration time series，不是 `da/dt`。密度反演還需配合
attitude、radiation pressure 與 aerodynamic models；這些處理不在
`acc_pod[3]` 欄位內。[Siemes et al. (2016)](https://doi.org/10.1186/s40623-016-0474-5)

因此 `ACCxPOD_2_` 可以支援 energy-balance 或 Gauss variational equation
計算，但不能直接當成大氣拖曳造成的 semi-major-axis decay，更不能直接給
event excess。

## 正式論文與逐事件數表

### Li and Lei (2021): September 2017 單事件

[The Determination of Satellite Orbital Decay From POD Data During Geomagnetic Storms](https://doi.org/10.1029/2020SW002664)
明確使用 POD 軌道配合重力位能的 numerical integration，自行導出 orbital
decay 與 decay rate。Swarm-A 在 2017-09 事件的正文結果是 quiet 約 20 m/day、
storm 約 60 m/day；三日 total decay 約 80 m，storm-induced decay 約 20 m。

[出版社全文與 Data Availability Statement](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2020SW002664)
只連回 ESA Swarm、GFZ 與 OMNI 上游資料。頁面沒有 Supporting Information，
也沒有 CSV、XLS 或逐事件數值表；Swarm-A 數值在正文與 Figure 8。這些值可作
單事件 benchmark，不能取代本專案的逐事件資料庫。

### Tulasi Ram et al. (2026): May 2024 與 February 2026

[Quasi-Homologous Solar Flares and Impacts on Thermospheric Density and Satellite Orbital Drag](https://doi.org/10.1029/2026GL125768)
明寫從 `SW_SP3xCOM_2_` 計算每軌 mean semi-major axis，再對每日資料做 linear
least-squares slope。這表示論文中的 decay rate 不是 ESA 產品欄位。

正文報告 May 2024 quiet rate 為 -19.91 m/day，07--10 May 為 -33.53 至
-42.43 m/day，11 May 磁暴後接近 -170 m/day。該文
[Availability Statement](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2026GL125768)
只提供 ESA DNSxPOD、SP3 與外部指數入口；頁面沒有 Supporting Information 或
可下載數值表。逐日 slope 與不確定度放在正文及 Figures 2、4，仍只適合作為
少數事件的外部比對。

## 最少仍須自行計算的內容

若研究目標仍是「Swarm-A 每次磁暴相對背景多下降多少」，最小工作不能省掉：

1. 從 `SW_SP3xCOM_2_` 取得 Swarm-A position/velocity，正確處理 GPS time、ITRF
   到 inertial frame 的速度轉換、資料缺口與軌道機動。
2. 由 state 計算 semi-major axis，並明確定義 orbit mean 或其他去除軌道週期
   項的 estimator。若改走 energy-balance 或 `ACCxPOD_2_`，則須保留其 force
   model 與非大氣力修正。
3. 對每個事件獨立定義 storm window 與 quiet/background estimator。這些是研究
   選擇，不存在於 ESA 產品。
4. 計算同一 estimator 下的 storm rate 與 background rate，再積分差值：

   $$
   \Delta a_{\mathrm{excess}}
   = \int_{t_0}^{t_1}
   \left(\dot a_{\mathrm{storm}}(t)-\dot a_{\mathrm{background}}(t)\right)\,dt.
   $$

   此式保留 semi-major-axis change 的正負號；若要報告正值「額外下降量」，需再
   明寫採用 $-\Delta a_{\mathrm{excess}}$ 的符號慣例。

5. 把 Li and Lei (2021) 的 2017-09 結果與 Tulasi Ram et al. (2026) 的 2024-05
   結果只當外部 benchmark；不可把圖上讀值當成官方 release 或完整 ground truth。

若只研究上述兩個已發表事件，可以引用論文的摘要數值而不重算；但這無法回答
本專案的跨事件、統一方法問題，也不能產生可稽核的背景與額外下降資料鏈。

## 決策

- 不新增「下載官方 decay product」路線；該產品不存在。
- 為避免繼續投入平靜日 selection，Phase 6 目前採 Tulasi Ram et al. (2026) 的
  2024-05-04、2026-01-31 quiet-time rate 作時間錨點，按事件 `t0` 連續線性處理。
- 這是本專案的簡化 empirical proxy。中間 rate 不是論文測量值，也不控制高度、
  季節、local time 或 solar state。
- `SW_SP3xCOM_2_`、`DNSxPOD_2_`、`DNSxACC_2_` 與 `ACCxPOD_2_` 留待後續物理
  驗證，不冒充官方 event-level decay reference。
