# 從 Phase1 到 Phase4 的遺漏物理：可做性研究

日期：2026-10-30

狀態：[done]。這是研究選項，不改寫 Phase1--3 的凍結結果，也不把 Trial4 的
`R_fit`、`tau_hours` 或共同 `G` 解釋成物理常數。

## 決定

目前最缺的不是另一個密度回歸公式，而是把「密度」轉成「非保守加速度」所需的
衛星與大氣速度資料。現在不應直接把 atmospheric drag 接到 RK4。

可以立刻做的最小工作是新 phase 的資料可用性稽核：確認 DNSAACC、衛星質量／姿態／
投影面積、`C_D`、maneuver 與大氣 wind 的來源、時間範圍及品質旗標。稽核通過前，只可
產生明確標為 proxy 的量，不可產生 `drag_acceleration_m_s2` 或校準 orbital decay。

```text
目前可用
POD {r, v} + D-model density + Earth rotation
  -> relative-speed / density proxy [descriptive]

尚缺受控資料
{C_D, projected_area, mass, attitude, atmospheric_wind}
  -> aerodynamic acceleration
  -> Gauss / energy equation
  -> physical da/dt comparison
```

## 現有鏈條已做與未做的事

| 層次 | 現有結果 | 不能補上的物理量 |
| --- | --- | --- |
| Phase1／1R | POD state -> B-L J2--J5 mean element -> candidate `da/dt` | B-L `M2=0` 不是完整 conservative-force accounting，也不是 drag acceleration。 |
| Phase2／2R | storm phase、SME、DNSAPOD 與 NRLMSIS 配對 | DNSAPOD 是 density product，不提供衛星的可識別 ballistic coefficient。 |
| Phase4 | 每場 $R_{\mathrm{fit},k}$、\(\tau_k\)，共同正 \(G\) 的 retrospective D-model | 三個 fit parameter 都用了同場 L2；不是 mass、area、drag coefficient、heating time constant 或 forecast input。 |
| Phase4 | 多組 residual GPR 無 held-out 改善 | 負結果不代表遺漏的力項為零；只表示已試特徵無可轉移殘差修正。 |

## 候選 1：自由分子／連續過渡區的 aerodynamic drag

若衛星的有效 drag coefficient、投影面積與質量都已受控，常用向量形式可寫為

$$
\mathbf a_D=-\frac{1}{2}\rho\frac{C_D A_\perp}{m}
\lVert\mathbf v_{\mathrm{rel}}\rVert\mathbf v_{\mathrm{rel}},
\qquad
\mathbf v_{\mathrm{rel}}=\mathbf v_{\mathrm{sat}}-\mathbf v_{\mathrm{atm}}.
$$

其中 \(\rho\) 是中性質量密度，\(A_\perp\) 是隨姿態改變的迎風投影面積，\(m\) 是
瞬時質量，\(\mathbf v_{\mathrm{atm}}\) 含 Earth co-rotation 與 thermospheric wind。也可令
ballistic coefficient \(\beta=m/(C_DA_\perp)\)，但它不可由目前 Trial4 的 `R_fit` 代替。

Orekit 的 `DragForce` 明確以 density、atmosphere velocity、spacecraft mass 與
`DragSensitive` 幾何／係數來計算 acceleration；其文件也明示 relative velocity 由 atmosphere
velocity 與 satellite velocity 相減得到。[Orekit DragForce](https://www.orekit.org/site-orekit-latest/apidocs/org/orekit/forces/drag/DragForce.html)

### 現在能做的安全子項

可在新的 derived table 計算、不含未知 \(1/\beta\) 的

$$
q_D=\frac12\rho\lVert\mathbf v-\boldsymbol\omega_\oplus\times\mathbf r\rVert^2,
\qquad
p_D^*=\frac12\rho\lVert\mathbf v-\boldsymbol\omega_\oplus\times\mathbf r\rVert^3.
$$

`q_D` 是 dynamic-pressure proxy；`p_D^*` 是每單位 \(C_DA/m\) 的 power-like proxy。
兩者的用途只能是把 D-model / observed density、軌道速度與 candidate `da/dt` 對齊，檢查
storm-time scaling 是否合理。它們不是 force、acceleration、實際功率或 decay rate。

### 目前不能做的部分

- 不能把 \(\mathbf v_{\mathrm{atm}}\) 簡化為 Earth co-rotation 後就宣稱為實際 drag；wind 在
  storm-time 可改變相對速度。
- 不能假設固定 `C_D`、固定面積或固定質量。Swarm 的姿態、surface model、maneuver 和
  質量歷史都要有版本化來源。
- 不能用 DNSAPOD／DNSAACC density 的反算結果再「校準」同一筆 orbit rate，然後稱為獨立驗證。

## 候選 2：Gauss semi-major-axis equation

若已經有可信的 RTN non-conservative acceleration
\(\{a_R,a_T,a_N\}\)，可以用

$$
\dot a=\frac{2a^2}{h}
\left(e\sin f\,a_R+\frac{p}{r}a_T\right),
\quad h=\lVert\mathbf r\times\mathbf v\rVert,
\quad p=a(1-e^2).
$$

這是把已知 acceleration 投影成 osculating semi-major-axis change 的關係；拖曳多半由
沿軌 \(a_T\) 主導，但不能先假設 radial 或 normal component 為零。

**判定：現在不可做 physical \(\dot a\)。** 目前只有 candidate mean-element slope 與
density／D-model，沒有可校準的 RTN acceleration。先做候選 1 的資料稽核後，才可把此式
列為新 phase 的 closure check；不得拿它回寫 Phase1 candidate rate。

## 候選 3：機械能與完整 conservative-force work

可用比機械能

$$
\varepsilon=\frac12\lVert\mathbf v\rVert^2+U(\mathbf r,t),
\qquad
\dot\varepsilon=\mathbf v\cdot\mathbf a_{\mathrm{nonconservative}}
+\frac{\partial U}{\partial t}
$$

分離 non-conservative work。實作時 \(U\) 必須包括所宣稱精度下的非球形 Earth gravity、
Sun/Moon、solid/pole/ocean tides 等 time-varying potential；solar radiation pressure 也必須
以姿態、eclipse、optical coefficient 與面積建模，不能被默默當成 drag。

Li & Lei 的 Swarm research route 正是以高階 gravity、lunar/solar ephemeris、IERS tide 與
沿軌 work integration 來處理這件事；論文警告低階或近似 potential 可能使 rate 有很大誤差，
甚至符號錯誤。[Li & Lei 2021](https://doi.org/10.1029/2020SW002664)

**判定：目前不做。** 這是獨立 validation project，不是給 B-L H2/H3 或 Trial4 residual
加一項公式就會正確的修正。現有 B-L J2--J5 定義仍可保留為 candidate estimator，但不能冒充
完整 energy accounting。

## 候選 4：官方 accelerometer-derived density 作獨立密度資料層

這不是新 force equation，卻是目前最有價值的物理資料改進。ESA/VirES 將
`SW_OPER_DNSAACC_2_` 定義為結合 precise orbit determination 與 accelerometer 的 Swarm-A
thermospheric-density observation；目前專案主要使用的是 POD-only `SW_OPER_DNSAPOD_2_`。
[ESA/VirES HAPI product catalogue](https://vires.services/hapi/)

NRLMSIS 2.0 是以位置、時間、solar activity 與 geomagnetic activity 為輸入的經驗大氣模型，
不是 storm-time ground truth；因此可用 ACC density 與 NRLMSIS／D-model 分別比較，但不可把
模型密度當成加速度測量。[NRLMSIS 2.0 原始論文](https://repository.library.noaa.gov/view/noaa/53074/noaa_53074_DS1.pdf)

**判定：可現在開始做資料稽核，尚不能直接做 drag propagation。** 最小輸出應是新的 raw
manifest 與 read-only quality audit：CDF variable、quality flag、uncertainty、cadence、產品
baseline、與 DNSAPOD 的 epoch pairing / coverage。它必須寫入新的 phase，不能更新凍結
Phase2／3 表。

## 候選 5：thermospheric wind、local solar time 與 onset

| 項目 | 為何重要 | 現在判定 |
| --- | --- | --- |
| thermospheric wind | 決定 \(\mathbf v_{\mathrm{rel}}\)，是 drag equation 的必要項。 | 缺有資料契約的 wind product；不可以零 wind 宣稱 physical acceleration。 |
| local solar time | NRLMSIS 與 density 有顯著 local-time dependence；Phase1 support code 已能從位置算出。 | 可做新 phase 的 stratified residual diagnostic，但不能拿已曝光的 25 場再做任意 GPR 選模。 |
| reproducible onset | 區分驅動開始、density response 與 orbit response；現有 `t0` 是 SYM-H minimum。 | 值得先定義，但需要預先固定輸入、threshold、gap rule 與 held-out protocol。 |

## 建議順序

1. **P5.0 data audit**：不寫 propagator。只盤點並核對 ACC density、attitude／area／mass、
   maneuver、wind 來源與品質，列出可追溯的缺口。
2. **P5.1 descriptive drag proxy**：若 P5.0 證明 density 與 GCRF state 的 key 能安全對齊，
   寫 `q_D`、`p_D^*` 到新 derived table，並按 maneuver／source boundary 分層。它不含未知
   ballistic coefficient。
3. **Go / no-go gate**：只有找到受控 \(C_D,A_\perp,m\)、姿態與 wind 定義，才實作候選 1 的
   \(\mathbf a_D\) 與候選 2 的 Gauss closure；否則停在 proxy。
4. **獨立 future validation**：完整 energy/work integration 必須另立計畫、force-model test 與
   independent product comparison；不與 P5.1 混為一個小修正。

## 來源與推論界線

- Orekit 文件提供 drag model 的輸入契約與 relative velocity 定義；它不提供 Swarm-specific
  \(C_DA/m\)。
- ESA/VirES product catalogue 證實 ACC/POD density products的資料來源差異；它不等於可直接取得
  calibrated drag acceleration。
- NRLMSIS 2.0 論文定義的是經驗 density model 的適用範圍；D-model 對其作的 residual fit
  仍是專案內 retrospective operation。
- 「先做 P5.0/P5.1」是依上述輸入契約與本專案既有缺口做的工程推論，不是外部論文已證實的
  Swarm drag release。
