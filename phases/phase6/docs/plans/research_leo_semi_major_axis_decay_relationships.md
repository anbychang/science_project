# LEO 半長軸遞減的物理關係與實測文獻

## 決定

Phase 6 可用比「兩個文獻 rate 對時間線性內插」更合理、仍然很簡單的背景
proxy。對同一顆 Swarm-A，定義正的下降速率

\[
r(t)=-\dot a(t)>0.
\]

若姿態、質量與 drag coefficient 在比較區間內近似不變，且軌道近圓，則

\[
\boxed{
\frac{r(t)}{r_{\mathrm{ref}}}
\simeq
\frac{\bar\rho_q(t)}{\bar\rho_q(t_{\mathrm{ref}})}
\sqrt{\frac{a(t)}{a(t_{\mathrm{ref}})}}
}
\]

其中 \(\bar\rho_q\) 是沿實際 Swarm-A 軌道取一圈平均、但使用 quiet
geomagnetic forcing 的 model density。這個 ratio 應先用專案已有的
NRLMSIS 2.0 實作；DTM2013/2020 與 JB2008 只作 model sensitivity。不要為此先
新增依賴。這個方法保留 altitude、solar flux、season、latitude 與 local time
的影響，直接修正純時間線不具物理意義的正背景 rate。

這仍是 empirical proxy，不是已校準 drag model。它不能吸收 maneuver、姿態改變、
\(C_D\) 改變、POD estimator bias，亦不能把 Phase 4 D-model 的 in-sample density
參數變成 forecast input。

```text
一個可接受的 quiet-rate reference
  -> quiet model 的 orbit-mean density ratio
  -> sqrt(a/a_ref) 小修正
  -> 每場背景 rate
  -> 與同一 estimator 的實測六日下降比較
```

## 物理式與假設

### 1. 從 drag acceleration 到 `da/dt`

令

\[
\beta=\frac{C_D A}{m}\quad (\mathrm{m^2/kg})
\]

為 area-to-mass drag factor。部分文獻把它叫 ballistic coefficient；另一些文獻把
其倒數 \(m/(C_DA)\) 才叫 ballistic coefficient。引用數值前必須先核對定義。

drag acceleration 為

\[
\mathbf a_D=-\frac12\beta\rho |\mathbf v_{\mathrm{rel}}|
\mathbf v_{\mathrm{rel}}.
\]

由比軌道能量 \(\epsilon=-\mu/(2a)\) 與
\(\dot\epsilon=\mathbf v\cdot\mathbf a_D\)，得到

\[
\dot a
=-\beta\rho\frac{a^2}{\mu}
|\mathbf v_{\mathrm{rel}}|
(\mathbf v\cdot\mathbf v_{\mathrm{rel}}).
\]

這個能量式比圓軌道簡式更一般。它保留 atmosphere rotation／wind 造成的
\(\mathbf v_{\mathrm{rel}}\) 差異。Li and Lei (2021) 也從 non-conservative
energy decay 導出 POD-based orbital decay，並指出必須先移除非球形重力等
conservative potential 對 instantaneous semi-major axis 的大幅週期變化
([DOI](https://doi.org/10.1029/2020SW002664))。

若再假設近圓軌道、\(\mathbf v_{\mathrm{rel}}\simeq\mathbf v\)、
\(v^2=\mu/a\)，則

\[
\boxed{\dot a=-\beta\rho\sqrt{\mu a}}.
\]

因此同一顆衛星的 rate ratio 會消去未知但固定的 \(\beta\)。Chen et al.
(2012) 對 CHAMP 的每圈 mean density 與每圈 mean semi-major-axis decay rate
得到三組線性相關係數 0.96、0.95、0.94，直接支持短期內「rate 主要隨 density
變化」的近似 ([DOI](https://doi.org/10.1029/2012JA017782))。

### 2. `a` 與 `e` 的角色

對非圓軌道，速度遵守

\[
v^2=\mu\left(\frac{2}{r}-\frac{1}{a}\right),
\qquad r=a(1-e\cos E).
\]

因此 \(e\) 不是可忽略地塞進一個常數修正：較低 perigee 同時有較大密度與速度，
使每圈能量損失被 perigee 強烈加權。完整 secular \(\Delta a\) 是沿 eccentric
anomaly 對 \(\rho(E)\)、\(C_D(E)\)、速度項積分。King-Hele 類方法正是這種
orbit-average；其準確度依賴 exponential atmosphere、scale height 與
drag-coefficient 假設 ([Ray and Scheeres 2021](https://doi.org/10.1093/mnras/staa3630)、
[Frey et al. 2019](https://doi.org/10.1016/j.asr.2019.03.016))。

Phase 6 的 Swarm-A proxy 只應在 near-circular regime 使用。每圈平均 density
必須沿實際 POD 軌道取樣；如此小 \(e\) 的主要作用已透過實際 altitude-dependent
density 進入積分。不要再另乘未驗證的 eccentricity correction。若未來處理
Starlink 的 210 x 350 km staging orbit，圓軌道 ratio 不成立。

### 3. 累積下降

在時間窗 \([t_0,t_1]\) 內，背景或 storm-induced change 都是 rate 的積分：

\[
\Delta a=\int_{t_0}^{t_1}\dot a(t)\,dt.
\]

磁暴 peak 強度不能代替積分。Chen et al. (2012) 的 CIR 案例 peak 較小但持續較久，
三場 CIR 累積下降 96.5、80.7、38.0 m；相配的四場 CME 為 32.6、26.5、70.5、
36.7 m。Chen et al. (2014) 的 135 場統計亦得到 CME median peak storm-induced
rate 39 m/day、CIR 27 m/day，但 median total decay 分別約 50 與 60 m
([2012 DOI](https://doi.org/10.1029/2012JA017782)、
[2014 DOI](https://doi.org/10.1002/2014JA019831))。

## Phase 6 最小 proxy

### 建議公式

選一個有可接受 quiet-rate 證據的 reference epoch：

\[
r_q(t)=r_{q,\mathrm{ref}}
\frac{\bar\rho_{q,M}(t)}{\bar\rho_{q,M}(t_{\mathrm{ref}})}
\sqrt{\frac{a(t)}{a(t_{\mathrm{ref}})}}.
\]

對六日窗的背景下降：

\[
\Delta a_q=-\int_{t_0}^{t_1}r_q(t)\,dt.
\]

`M` 是 density model。\(\bar\rho_{q,M}\) 應符合：

- 沿 Swarm-A 實際位置、altitude 與 local solar time 計算，再作 orbit mean。
- 保留該日 solar forcing；至少保留 daily `F10.7` 與 81-day mean `F10.7A`。
- 將 geomagnetic driver 固定為預先定義的 quiet state，不能把事件的 storm `Ap`
  或 `Dst` 混進背景。
- reference 與 target 使用相同 model version、相同 orbit-mean estimator。
- model density ratio 只調 rate；它不宣稱 model 絕對 density 正確。

### 為何優於純時間線

純時間線把下列不同物理來源都誤當成 calendar trend：

```text
altitude + F10.7/F10.7A + season + local time + latitude sampling
  -> thermospheric density
  -> quiet decay rate
```

model ratio 至少顯式控制這些量。ratio 也會消去同一 model 的固定 density scale
bias 與同一衛星固定 \(\beta\)。它不會消去 model bias 隨 solar state、altitude
或 local time 的變化。

### NRLMSIS、DTM、JB 的取捨

| Model | Phase 6 用法 | 優點 | 主要限制 |
|---|---|---|---|
| NRLMSIS 2.0 | 第一個 candidate proxy | 專案已有計算路線；不新增依賴；輸入可稽核 | storm peak 與 recovery 可有系統偏差；通過 backtest 前不是正式背景 |
| DTM2013/2020 | sensitivity | 在部分 CHAMP／GRACE 年段的平均 ratio 與 scatter 較好 | 優勢不是所有年份、altitude 都一致；增加另一套 model/data contract |
| JB2008 | sensitivity，或後續 storm hindcast | 針對 drag 與 geomagnetic response 設計 | Oliveira and Zesta 發現 storm recovery 常高估 decay；不能把 observed-storm JB density 當 quiet background |

ESA/NASA/NOAA 的 multi-model assessment 顯示 DTM2013、NRLMSISE-00、JB2008
對 CHAMP、GRACE 的 bias、scatter 與 correlation 會隨年份和任務改變，沒有單一
model 全域勝出 ([DOI](https://doi.org/10.1029/2018SW002027))。Oliveira and
Zesta (2019) 亦指出 JB2008 在強 storm recovery 的 total decay error 最大
([DOI](https://doi.org/10.1029/2019SW002287))。因此 Phase 6 的最小決策是：

較新的 NASA CCMC 151 場、五任務 storm-time assessment 顯示：DTM2020 的整體
scatter 與 correlation 最佳，JB2008、DTM2013 也表現良好；MSIS 在 main／recovery
phase 平均低估 density 約 20%--30%。這是 storm-time 模型評估，不代表 quiet
ratio 必然同幅偏差，但要求 NRLMSIS candidate 必須保留 model sensitivity，不可只因
專案已有程式就視為真值
([Wang et al. 2026](https://doi.org/10.1029/2025SW004782))。

1. 先跑 NRLMSIS 2.0 ratio。
2. 用現有 quiet windows 做不重新選窗的 backtest。
3. 只有 NRLMSIS ratio 明顯優於 pure-time baseline，才保留為現行 proxy。
4. DTM/JB 只在可用且不改資料鏈時作 sensitivity；model spread 是方法不確定度，
   不是 95% statistical interval。

### 接受條件

使用既有 Phase 6 quiet windows，不新增手挑事件：

- 與純時間線比較同一批窗的 signed error、MAE 與最差絕對誤差。
- 要求 2023 最早事件不再產生正的 physical background rate。
- 至少檢查 leave-one-window-out；reference rate 不可來自測試窗本身。
- 檢查 model-ratio 改善是否大於端點 4/6/8 圈敏感度。
- 分別報 NRLMSIS 2.0 ratio、純時間線與 constant-rate；不要只報勝者。
- 若姿態或 maneuver metadata 顯示 regime change，分段或排除，不能讓 density ratio
  吸收 satellite configuration change。

## 實測數值

下表的數字是各論文或官方報告在其特定 estimator、衛星與事件下的結果。它們可作
量級或方法 benchmark，不能直接當 Swarm-A 2023--2026 的 rate。

| 衛星／事件 | 實測或文獻導出結果 | 可用性與限制 | Primary source |
|---|---|---|---|
| Swarm-A，2017-09 storm，約 451 km | quiet 約 20 m/day，storm 約 60 m/day；3 日 total 約 80 m，storm-induced 約 20 m | 同一衛星直接 benchmark；POD energy method，非 ESA release 欄位 | [Li and Lei 2021](https://doi.org/10.1029/2020SW002664) |
| Swarm-B，同事件，約 515 km | 7.7 m/day 增至 >20 m/day；3 日 total 約 30 m，storm-induced 約 7 m | 顯示 altitude 作用；高軌低 density 時 POD uncertainty 較大 | [Li and Lei 2021](https://doi.org/10.1029/2020SW002664) |
| GRACE，同事件，約 338 km | 約 155 增至 400 m/day；3 日 total 約 600 m，storm-induced 152 m | 低 altitude 主導絕對 rate；不可把數值移植到 Swarm | [Li and Lei 2021](https://doi.org/10.1029/2020SW002664) |
| GRACE，2003-11 extreme storm | quiet 約 21 m/day，storm >150 m/day；4 日 total 162 m，storm-induced 約 75 m | solar maximum、低軌 drag-dominated；同文估計 storm-induced 約佔 4 日一半 | [Li and Lei 2021](https://doi.org/10.1029/2020SW002664) |
| CHAMP／GRACE，2003-11，storm onset 後約 60 h | 約 -160／-71 m；quiet background 約 -24.11／-6.86 m | 同 storm 不同 altitude、spacecraft；支持 altitude 與 \(A/m\) 不可忽略 | [Oliveira et al. 2020](https://doi.org/10.1029/2020SW002472) |
| CHAMP／GRACE，2005-08 storm | 約 364／482 km；peak 約 -250／-150 m/day；72 h 累積約 -86／-25 m | 同一 event 中較低 CHAMP 累積下降約為 GRACE 的 3.4 倍；各自 quiet background 約 12.0／2.9 m | [Oliveira and Zesta 2019](https://doi.org/10.1029/2019SW002287) |
| CHAMP／GRACE，近 200 個 ICME，2003--2015 | extreme events 常見約 90--120／40--50 m；GRACE 高約 150 km | 這些是 event decay，不是 daily rate；平均 onset lag 5 +/- 2 h | [Krauss et al. 2018](https://doi.org/10.1029/2018JA025778) |
| GRACE-FO，2023-05-01 | 7-day mean 19.8 m/day，mean altitude 484.9 km | 官方任務狀態快照；不是 storm excess | [GFZ SDS Newsletter No. 23](https://www.gfz.de/fileadmin/gfz/sec12/pdf/GRACE-FO/GRACE_FO_SDS_newsletter_No23.pdf) |
| Starlink Group 4-7，2022-02 | 49 顆進入 210 x 350 km staging orbit；38 顆約 4 日內 reentry；約 200--210 km density 比前 9 日高至少 20%--30% | 高 \(A/m\)、高 eccentricity、低 drag attitude 與未完成 orbit raising；沒有可移植的 Swarm `da/dt` | [Berger et al. 2023](https://doi.org/10.1029/2022SW003330) |
| TRISAT，2024-05 superstorm | baseline 約 0.4 km/day，peak >1 km/day；10--13 May 累積約 2.5 km | 3U CubeSat、低 altitude、高 drag susceptibility；TLE-derived | [Kosanic et al. 2026](https://doi.org/10.1029/2026SW005085) |
| SNIPE 6U constellation，2024-05 | 相近軌道的 SNIPE-B/D 有顯著不同 altitude loss；差異歸因不同 attitude 與 ram-facing area | 最直接證明相同平台也不能忽略 attitude；不應搬其數值到 Swarm | [Song et al. 2026](https://doi.org/10.1029/2026SW005089) |

Oliveira and Zesta (2019) 對 217 個 CME-driven storms、364 組 CHAMP/GRACE
observations 的統計顯示：storm-time decay 一般隨 storm intensity 增強；CHAMP
較低 altitude 的 total decay 大於 GRACE，且 response 先在高緯出現，再向中低緯
擴展 ([DOI](https://doi.org/10.1029/2019SW002287))。這比用單一 `Kp` 或
`Dst_min` 直接映射整場 decay 更接近實際時空結構。

## Density 與環境因子

### Altitude

altitude 是絕對 decay rate 最強的分層因子，因為 thermospheric density 隨高度近似
指數下降。2017-09 同場 storm 的 GRACE、Swarm-A、Swarm-B rate 隨約 338、451、
515 km 清楚分離。Krauss et al. (2018) 亦指出 GRACE 比 CHAMP 高約 150 km 時，
同類 event decay 明顯較小
([Li and Lei 2021](https://doi.org/10.1029/2020SW002664)、
[Krauss et al. 2018](https://doi.org/10.1029/2018JA025778))。

這也是 quiet model ratio 優於 calendar interpolation 的主要原因。\(\sqrt a\) 在
幾百公里高度變化中只小幅改變；真正的大變化來自 \(\rho(h)\)，不能只修
\(\sqrt a\)。

### Solar flux

solar EUV 加熱決定 thermosphere 的慢背景狀態；`F10.7` 是常用 proxy，不是 EUV
本身。CHAMP／GRACE 的季節研究指出不同 solar activity 會顯著調制 seasonal
amplitude 或 phase，因此 calendar month 不能單獨代表背景
([Lei et al. 2012](https://doi.org/10.1029/2011JA017324))。Phase 6 quiet model
必須保留實際 `F10.7` 與其長期平均，不能把它們也固定成 reference 值。

### Geomagnetic activity 與 lag

Joule heating 與 particle precipitation 先在高緯注入能量，造成 thermospheric
heating、expansion 與 density enhancement。Chen et al. (2012) 的 CHAMP
density／decay rate 與 auroral hemispheric power response 落後約 3--6 h；Krauss
et al. (2018) 的 event 統計得到 orbit-decay onset 平均落後 ICME/CIR arrival
\(5\pm2\) h
([Chen et al. 2012](https://doi.org/10.1029/2012JA017782)、
[Krauss et al. 2018](https://doi.org/10.1029/2018JA025778))。

因此 storm peak index 與 orbit decay 不應強迫同時。Phase 4 的 event-specific
\(\tau_k\) 能描述 retrospective density response，但不能被這些跨任務平均 lag
取代，也不能反過來把 \(\tau_k\) 寫成物理量。

### Local time、latitude 與 season

CHAMP 400 km density 顯示 10--20 magnetic local time、約 +/-20--25 deg
geomagnetic latitude 有雙峰，高緯亦有 localized enhancement；MSIS90 在部分區域
低估約 15%--30% ([Liu et al. 2005](https://doi.org/10.1029/2004JA010741))。
CHAMP／GRACE 觀測也有 annual 與 semiannual variation；歷史 climatology 常見約
April／October maxima，但 local-time precession 與 season 會混在一起，不能靠
日平均自動消除 ([Lei et al. 2012](https://doi.org/10.1029/2011JA017324))。

所以 Phase 6 應沿實際 orbit sampling 算 density ratio。只在單一固定 latitude、
local time、或每日中午算 model density，仍會留下 sampling bias。

## 可移植與不可移植

### 可移植的關係

- drag energy loss 對 \(\rho C_DA/m\) 一階成正比。
- near-circular orbit 的 \(-\dot a\propto\rho(C_DA/m)\sqrt{\mu a}\)。
- 同一衛星、同一 attitude regime 的 rate ratio 可消去固定的 \(C_DA/m\)。
- cumulative decay 必須積分整段 density enhancement；peak index 不夠。
- altitude、solar forcing、geomagnetic forcing、season 與 local time 都透過 density
  影響 decay。
- storm response 有數小時 lag，且有高緯到低緯傳播與 recovery。

### 衛星／事件專屬的數字

- 任一篇論文的 m/day、累積 m、lifetime loss。
- \(C_D\)、ram-facing area、mass、attitude mode 與 effective ballistic coefficient。
- Starlink staging orbit、low-drag configuration 與 reentry fraction。
- CubeSat 的高 \(A/m\)、tumbling、solar-panel geometry。
- 某個 storm 的 density enhancement factor、lag、recovery duration。
- TLE、POD、accelerometer、orbit-mean slope 各自的 estimator bias。

SNIPE 是最清楚的反例：幾何相同、altitude 相近的兩顆 CubeSat，只因 attitude
不同就有不同 altitude loss。Starlink、TRISAT、SNIPE 適合證明 high-\(A/m\)
風險，不適合替 Swarm-A 提供數值 calibration。

## 量測警告

不要把 instantaneous osculating semi-major axis 直接差分後稱為 drag decay。
Li and Lei (2021) 的 GRACE 案例中，conservative potentials 使 instantaneous
\(a\) 在 6843--6862 km 間變動，而同日 non-conservative decay 只有約 20 m。
該文以完整 gravitational work／energy integration 分離小訊號；累積 decay 對
accelerometer reference 的相對偏差通常低於 10%。在 high altitude、low density
時，簡化解析法甚至會產生不可靠的正 rate
([DOI](https://doi.org/10.1029/2020SW002664))。

Phase 6 必須繼續使用明確的 orbit-mean／endpoint estimator、同一時間鍵與 gap
規則。任何 model-ratio 改善都只能和同一套 observed decay estimator 比較。

## Phase 6 研究界線

- 目前可把 NRLMSIS quiet-density ratio 當成「背景 rate 的形狀」，再用一個獨立
  quiet reference 決定尺度。
- Phase 4 D-model 是 25 場 in-sample retrospective density model。它可在後續
  hindcast 積分中作 density input，但不能用來定義獨立 quiet reference，也不是
  forecast driver。
- 現有 Phase 6 quiet closure 的經驗尺度可作 feasibility evidence；在 maneuver、
  attitude 與 source quality 未校準前，不應改名為 physical \(C_DA/m\)。
- 若 model-ratio proxy 未穩定勝過 pure-time baseline，保留後者作 descriptive
  comparator，不能因物理式較漂亮就宣稱實證改善。
- 本筆記只提出 proxy 與驗證條件，不授權修改 frozen Phase 2、2R、3 或 Phase 4。

## Primary sources

- Chen et al. (2012), CHAMP density／decay case studies:
  [https://doi.org/10.1029/2012JA017782](https://doi.org/10.1029/2012JA017782)
- Chen et al. (2014), 135-storm CHAMP statistics:
  [https://doi.org/10.1002/2014JA019831](https://doi.org/10.1002/2014JA019831)
- Li and Lei (2021), POD energy decay for GRACE and Swarm:
  [https://doi.org/10.1029/2020SW002664](https://doi.org/10.1029/2020SW002664)
- Oliveira and Zesta (2019), 217 CME-driven storms with CHAMP／GRACE:
  [https://doi.org/10.1029/2019SW002287](https://doi.org/10.1029/2019SW002287)
- Oliveira et al. (2020), CHAMP／GRACE storm and quiet decay magnitudes:
  [https://doi.org/10.1029/2020SW002472](https://doi.org/10.1029/2020SW002472)
- Krauss et al. (2018), ICME／CIR, altitude and orbit decay:
  [https://doi.org/10.1029/2018JA025778](https://doi.org/10.1029/2018JA025778)
- Berger et al. (2023), Starlink 2022 event:
  [https://doi.org/10.1029/2022SW003330](https://doi.org/10.1029/2022SW003330)
- Kosanic et al. (2026), TRISAT May 2024:
  [https://doi.org/10.1029/2026SW005085](https://doi.org/10.1029/2026SW005085)
- Song et al. (2026), SNIPE attitude and decay:
  [https://doi.org/10.1029/2026SW005089](https://doi.org/10.1029/2026SW005089)
- Lei et al. (2012), annual／semiannual density variability:
  [https://doi.org/10.1029/2011JA017324](https://doi.org/10.1029/2011JA017324)
- Liu et al. (2005), CHAMP local-time／latitude density structure:
  [https://doi.org/10.1029/2004JA010741](https://doi.org/10.1029/2004JA010741)
- Picone et al. (2005), density retrieval from orbital elements and assumptions:
  [https://doi.org/10.1029/2004JA010585](https://doi.org/10.1029/2004JA010585)
- Emmert et al. (2021), NRLMSIS 2.0:
  [https://doi.org/10.1029/2020EA001321](https://doi.org/10.1029/2020EA001321)
- ESA/NASA/NOAA model capability assessment:
  [https://doi.org/10.1029/2018SW002027](https://doi.org/10.1029/2018SW002027)
- Wang et al. (2026), 151-storm multi-model assessment:
  [https://doi.org/10.1029/2025SW004782](https://doi.org/10.1029/2025SW004782)
- GFZ GRACE-FO SDS Newsletter No. 23:
  [https://www.gfz.de/fileadmin/gfz/sec12/pdf/GRACE-FO/GRACE_FO_SDS_newsletter_No23.pdf](https://www.gfz.de/fileadmin/gfz/sec12/pdf/GRACE-FO/GRACE_FO_SDS_newsletter_No23.pdf)
