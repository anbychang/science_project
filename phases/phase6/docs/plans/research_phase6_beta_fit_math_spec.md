# Phase 6 density -> semi-major-axis decay 的 `beta_eff` 擬合規格

## 決定與狀態

狀態：[done: read-only specification]。本文件固定數學、資料切分與驗收規則；新的 SQLite derived output 仍是 [not created]。文中的 Phase 5 pooled GPR 檔是**需要上一圈 L2 的歷史 Trial9 輸出**，只可作回溯接法研究，不是[Phase 5 無同場 L2 終版](../../../phase5/reports/phase_5_report.md)的密度產品。

主方法沿用現有 Phase 6 quiet closure 的兩日窗 estimator：前 6 圈與後 6 圈各作端點 OLS，得到觀測半長軸損失；同一窗逐圈累加
`rho*sqrt(mu*a)*delta_t`，再以 zero-intercept regression 估計單一 `beta_eff`。2024 的三個窗只作 calibration；2026 的兩個窗只作一次性 validation。

`beta_eff` 只能稱為特定資料產品、window mapping 與 estimator 下的有效比例。它不是 Swarm-A 的物理 ballistic coefficient，也不是已驗證的 `C_D*A/m`。
本文件的方向約定是 `beta_eff ~= C_D*A/m`，不是有些文獻稱為 ballistic coefficient 的倒數 `m/(C_D*A)`；schema 必須把單位寫入名稱。

```text
2024 quiet windows
  -> endpoint 6-orbit OLS observed loss L_i
  -> density-orbit integral K_i
  -> zero-intercept beta_eff fit
  -> freeze every choice
  -> 2026 quiet windows validation
  -> Phase 5 storm density integration (retrospective application)
```

## 1. 輸入與符號

目前可重現 pilot 直接讀：

```text
phases/phase6/data/sqlite/swarm_a_phase6_quiet_audit_v1.sqlite
  phase6_quiet_orbit_pair_v1

phases/phase6/data/sqlite/swarm_a_phase6_quiet_endpoint_sensitivity_v1.sqlite
  phase6_quiet_endpoint_sensitivity_v1

phases/phase5/data/sqlite/swarm_a_phase5_pooled_orbit_gpr_v1.sqlite
  phase5_orbit_anchor
  phase5_orbit_prediction
```

令 window \(i\) 內依 UTC 排序的 paired orbit 為 \(k=0,\ldots,m_i-1\)：

| 符號 | 定義 | 單位 |
| --- | --- | --- |
| \(t_{ik}\) | orbit anchor UTC | s |
| \(a_{ik}\) | 與 density 同 orbit window 的 mean semi-major axis | m |
| \(\rho_{ik}\) | orbit-mean density | kg/m³ |
| \(\mu\) | \(3.986004418\times10^{14}\) | m³/s² |
| \(x_{ik}\) | \(\rho_{ik}\sqrt{\mu a_{ik}}\) | kg/(m s) |
| \(K_i\) | window-integrated predictor | kg/m |
| \(L_i\) | 正的 observed semi-major-axis loss | m |
| \(\beta_{\mathrm{eff}}\) | fitted effective density-to-decay scale | m²/kg |

近圓、\(v_{rel}\simeq v=\sqrt{\mu/a}\) 且一圈內 scale 固定時，能量式給出

\[
\dot a=-\beta\rho\sqrt{\mu a}.
\]

這只是 regression 的低階物理母式。完整 POD orbital-decay 路徑需處理非球形重力、time-varying potential 與其他 conservative force；Li and Lei 的原始方法不能用現有 B-L mean element 簡化取代（[Li and Lei 2021](https://doi.org/10.1029/2020SW002664)）。

## 2. 主 observed decay estimator

每個預先選定的兩日窗都保留全部合格 paired orbit。不得因 \(L_i\le0\)、個別 scale 不好看或 validation error 大而事後刪窗。

1. 對最前 6 圈的 \((t,a)\) 作含 intercept 的 OLS，將 fitted line 評估在 \(t_{i0}\)，得到 \(\widehat a_{i,start}\)。
2. 對最後 6 圈作相同 OLS，將 fitted line 評估在 \(t_{i,m_i-1}\)，得到 \(\widehat a_{i,end}\)。
3. 定義正的觀測損失：

\[
L_i=\widehat a_{i,start}-\widehat a_{i,end}
=-\Delta a_{obs,i}.
\]

`L_i > 0` 表示下降。端點 OLS 只降低單點殘留變異，不把 candidate mean element 變成已校準 drag truth。實作定義來自 [`calc_phase6_quiet_closure.py`](../../code/calc_phase6_quiet_closure.py)；端點 4／6／8 圈差異與 6 圈 OLS sigma 來自 [`calc_phase6_quiet_endpoint_sensitivity.py`](../../code/calc_phase6_quiet_endpoint_sensitivity.py)。

### 次要 daily OLS 檢查

Daily OLS 只回答 `beta_eff` 是否隨日明顯漂移，不取代上述兩日窗主 estimator。一天至少 10 個完整 phase orbit，對 orbit-mean \(a\) 作線性 OLS，令 \(y_d=-\widehat{da/dt}_d\)，並用同日 orbit-weighted predictor \(x_d\) 比較。Ram et al. 也以 orbit-mean semi-major axis 的 daily least-squares slope 與 slope 1-sigma 表示 Swarm-A daily decay（[Ram et al. 2026](https://doi.org/10.1029/2026GL125768)）；本專案的 phase boundary 是自己的實作選擇，不可反稱為該論文指定。

## 3. Predictor 與 window integral

逐圈 predictor 固定為

\[
x_{ik}=\rho_{ik}\sqrt{\mu a_{ik}}.
\]

主方法為了重現既有 quiet closure，使用左端 rule：

\[
K_i=\sum_{k=0}^{m_i-2}x_{ik}\Delta t_{ik},
\qquad
\Delta t_{ik}=t_{i,k+1}-t_{ik}.
\]

每段必須滿足 \(0<\Delta t_{ik}\le6000\) s；不跨 gap、不補 density。Trapezoid rule 只作預先聲明的 quadrature sensitivity；不得看 validation 後才改成主方法。

Phase 5 storm application 對每場 event/window 使用同式：

\[
\widehat{\Delta a}_{event}
=-\widehat\beta_{\mathrm{eff}}
\sum_k \widehat\rho_{5,k}\sqrt{\mu a_k}\Delta t_k.
\]

負號表示半長軸下降。缺一圈時結束目前連續 block；不可跨缺圈積分。每個 block 另存其起訖 anchor、orbit count、\(K\) 與 `algorithm_version`，最後只加總明確屬於同一 event evaluation window 的 blocks。

## 4. Mean anomaly 與共同 orbit-window mapping

時間接近不等於 orbit window 相同。正式 Phase 5 application 必須用 Phase 1 mean element 建立

\[
u(t)=\operatorname{unwrap}(\omega(t)+M(t)),
\]

其中 \(\omega\) 是 `mean_argument_of_perigee_rad`，\(M\) 是 `mean_anomaly_rad`。Unwrap 只能在同一 `chunk_id` 內進行。

Phase 5 anchor \(k\) 位於 `u_rel_rad ~= 2*pi*k`；其 density 是 centered

\[
W_k=[u_k-\pi,u_k+\pi]
\]

的一圈平均。共同 window 的 mapping 固定如下：

1. 以線性 phase interpolation 找 \(u_k-\pi\) 與 \(u_k+\pi\) 的 UTC boundary。
2. 保留 boundary 之間的 Phase 1 usable mean-element samples；boundary 落在兩筆間時只插入 boundary 的 \(t\) 與 \(a\)。
3. 以 `delta-u` trapezoid weight 計算同一 \(W_k\) 的 \(a_k\)。
4. 要求 phase coverage `>= 2*pi - 0.05 rad`、至少 500 個 10-second samples、最大 POD gap `<= 10 s`，且不可跨 `chunk_id`、source 或 maneuver boundary。
5. 相鄰 Phase 5 anchor 只接受 integer phase grid 連續；目前的 `0.02*pi` anchor tolerance 與 `phase_is_valid_80pct=1` 都保留。

Phase 5 已有 density window contract 見 [`phase5_pooled_orbit_gpr.md`](../../../phase5/docs/lineage/phase5_pooled_orbit_gpr.md)；Phase 1 的 phase-orbit 實作見 [`prep_10_phase_orbit_mean.py`](../../../phase1/code/prep_10_phase_orbit_mean.py)。`swarm_a_phase_orbit_mean_v2.time_us` 是 absolute-\(u\) orbit 的右端點，Phase 5 `time_us` 是 event-relative centered window anchor；兩者不可 exact join，也不可只因都叫 orbit mean 就視為同一 estimator。

目前 quiet-closure pilot 是「Phase 1 orbit end 與最近 DNSAPOD orbit-mean sample 相差不超過 60 s」的 legacy-compatible pairing，不證明兩個產品使用完全相同的 centered boundary。下列 preliminary 數值保留此定義以便重現。正式 Phase 5 storm application 必須完成上述共同 \(W_k\) mapping；新 mapping 若改變 2024 fit，必須建立新 version，不能覆寫 pilot。

## 5. Zero-intercept `beta_eff` estimator

主 regression 是

\[
L_i=\beta_{\mathrm{eff}}K_i+\epsilon_i,
\]

不加 intercept。\(K=0\) 時物理簡式要求 drag loss 為 0；若 residual 顯示明顯非零 offset，判定簡式不閉合，不以自由 intercept 掩蓋缺失物理。

### OLS

\[
\widehat\beta_{OLS}
=\frac{\sum_iK_iL_i}{\sum_iK_i^2}.
\]

主 pilot 使用 OLS，因為目前只有 3 個 2024 calibration windows，端點 formal sigma 並不包含 density、window selection、maneuver 與 estimator systematics。

### WLS sensitivity

若每窗 6-orbit endpoint uncertainty \(s_{L,i}>0\) 已固定，令 \(w_i=1/s_{L,i}^2\)：

\[
\widehat\beta_{WLS}
=\frac{\sum_iw_iK_iL_i}{\sum_iw_iK_i^2}.
\]

WLS 只作 sensitivity。不得把較小的 formal SE 解讀為密度與軌道的完整 measurement uncertainty。NIST 的 WLS 說明同樣要求 weights 對應 error variance；未知 variance 時先作 unweighted fit 再檢查 residual 是較安全的起點（[NIST WLS](https://www.nist.gov/system/files/documents/2017/05/09/sec2-1.pdf)）。

## 6. 標準誤、prediction uncertainty 與 resampling

令 \(n\) 是 calibration windows 數、\(e_i=L_i-\widehat\beta K_i\)。Zero-intercept OLS 只有一個 fitted parameter：

\[
\widehat\sigma^2=\frac{\sum_i e_i^2}{n-1},
\qquad
SE(\widehat\beta)=
\sqrt{\frac{\widehat\sigma^2}{\sum_iK_i^2}}.
\]

Scaled WLS 使用

\[
\widehat\sigma_w^2=\frac{\sum_iw_i e_i^2}{n-1},
\qquad
SE_w(\widehat\beta)=
\sqrt{\frac{\widehat\sigma_w^2}{\sum_iw_iK_i^2}}.
\]

對固定 validation kernel \(K_*\)，只含 coefficient uncertainty 的 mean prediction SE 是

\[
SE_{mean}(\widehat L_*)=|K_*|SE(\widehat\beta).
\]

若要預測一個新的 observed window，而非 fitted mean，classical diagnostic 才加 residual variance：

\[
SE_{pred}(L_*)=
\sqrt{K_*^2\operatorname{Var}(\widehat\beta)+\widehat\sigma^2}.
\]

這仍未包含 density uncertainty、端點 systematics 與相鄰 orbit correlation，報告必須分欄標示，不能只給一條看似完整的 95% 帶。

### 最小合理 resampling

- Regression unit 是不重疊兩日 window，不是 orbit row。相鄰 orbit 高度與 density 強烈相關；不得逐圈 iid bootstrap。
- 若 windows 重疊，先把所有時間相交的 windows 合成一個 cluster。Phase 5 storm application 則以整個 `storm_id` 為 cluster。
- 擴充後至少有 10 個獨立 calibration clusters，才執行 10,000 次 cluster bootstrap；每次抽整個 cluster、重算 endpoint \(L\)、\(K\) 與 `beta_eff`，以 bootstrap SD 與 2.5/97.5 percentile 報告 uncertainty。
- 目前 2024 只有 3 個獨立 windows。三群 bootstrap 或 cluster-robust covariance 不能支持可靠 coverage；只報 analytic SE、leave-one-window-out coefficient、4／6／8 endpoint sensitivity，並明寫 small-\(n\) limitation。Statsmodels 的官方 covariance contract 也把 `cluster` 視為 group-level covariance，而不是 row-level iid 修正（[official API](https://www.statsmodels.org/dev/generated/statsmodels.regression.linear_model.OLSResults.get_robustcov_results.html)）。
- Phase 5 的 `pooled_gpr_log_std` 是 density-model uncertainty，不等於 window-level decay residual。相鄰圈 correlation 未估出前，只能另報「完全相關」與「獨立」兩個 propagation bounds；不可把獨立圈平方和當成正式 prediction interval。

## 7. 2024 calibration／2026 validation：禁止洩漏

Calibration set 固定為：

```text
Q20240202
Q20240316
Q20240424
```

Validation set 固定為：

```text
Q20260318
Q20260428
```

在第一次讀取 2026 observed \(L\) 前，必須凍結：window selection、quiet thresholds、maneuver/source exclusions、common-window mapping、endpoint orbit count、gap rule、quadrature、OLS/WLS role、outlier policy、uncertainty method 與 acceptance criteria。2026 不得參與 scale、weight、threshold、hyperparameter、feature scaler 或 model selection。

歷史 Trial9 的 `phase5_orbit_prediction` 用 GroupKFold 混合 2023--2026 events，且 Phase 4 event parameters 使用同場完整 L2。它可作 retrospective storm application，不能直接形成「2024 訓練、2026 獨立 forecast validation」。若要做真正 chronological 2026 test，必須從 Phase 4／5 上游重新建立只用截至 2024 可用資料的 frozen density model；2026 只能套用並評分，不能 refit。這條歷史 GPR 另需上一圈 observed L2，因此即使完成 year split，也只能稱 conditional hindcast，除非該依賴被明確替換。

2023 與 2025 可保留為方法 development 或額外外部檢查，但不得在看過 2026 後拿來調規則，再聲稱原 2026 是 untouched validation。

## 8. Preliminary 可重現結果

下表直接讀現有 quiet closure v4；\(L=-\Delta a_{obs}\)。

| Window | Role | \(L\) (m) | \(K\) (kg/m) | \(\widehat L\) (m) | Error \(\widehat L-L\) (m) |
| --- | --- | ---: | ---: | ---: | ---: |
| `Q20240202` | calibration | 82.5350 | 8405.2082 | 82.3106 | -0.2244 |
| `Q20240316` | calibration | 72.8043 | 8172.5227 | 80.0319 | 7.2277 |
| `Q20240424` | calibration | 139.8959 | 13864.4090 | 135.7715 | -4.1244 |
| `Q20260318` | validation | 106.6242 | 9805.6520 | 96.0249 | -10.5994 |
| `Q20260428` | validation | 121.6935 | 14320.4420 | 140.2373 | 18.5439 |

2024 OLS pilot：

\[
\widehat\beta_{eff}=0.00979280767167571\ \mathrm{m^2/kg},
\qquad
SE=0.000324203999089046\ \mathrm{m^2/kg}.
\]

現有 4／6／8 endpoint sensitivity 對應的 OLS coefficient 分別為 `0.00980940`、`0.00979281`、`0.00958029 m^2/kg`；leave-one-window-out coefficient 範圍是 `0.00937675--0.01001751 m^2/kg`。Inverse-endpoint-variance WLS sensitivity 是 `0.00999818 m^2/kg`，但 3 個 windows 不足以把這個較集中的數字解讀成更準確。

2026 frozen validation metrics：

| Metric | Value |
| --- | ---: |
| MAE | 14.5716 m |
| RMSE | 15.1033 m |
| MAPE | 12.5895% |

這些數值只證明 formula 與 split 可重現。\(n_{cal}=3\)、\(n_{val}=2\) 太小，且 pilot pairing 尚未證明 centered orbit boundary 完全一致；trapezoid sensitivity 與完整 maneuver/source audit 也尚未完成。現在是 preliminary candidate，不得把小 SE 或 12.59% MAPE 寫成 calibrated release。

## 9. Acceptance／rejection criteria

### Data gate

每窗必須同時通過：

- 新 derived output 只寫 Phase 6 versioned SQLite table；不得建立 CSV intermediate，也不得改寫 Phase 1／5 source table。
- 預先指定年份角色，且沒有 validation-derived choice。
- 同一 `chunk_id`；不跨 source、known maneuver、POD rejection 或 gap。
- 至少 12 個 paired orbits，前後各 6 圈 endpoint OLS 都可解。
- 所有 \(a>0\)、\(\rho>0\)、\(K>0\)，每段 \(0<\Delta t\le6000\) s。
- Density 與 \(a\) 使用同一 phase window；若只能使用 legacy nearest-time pairing，結果必須標 `candidate`。
- Preselected valid window 即使 \(L\le0\) 仍保留；不可只留下降窗抬高 coefficient。

任一項失敗，該窗以明確 `reject_reason` 寫入 audit output，不進 fit；不得靜默刪除。

### Pilot acceptance

目前只可接受為 `beta_eff` pilot，條件是：

- 2024 OLS 可由 source SQLite 重算到文件數值；
- `beta_eff` 有限且為正；
- 2026 只執行一次 frozen scoring；
- 4／6／8 endpoints、OLS／WLS 與 left／trapezoid sensitivity 不改變主要方向判定；
- 報告同時列出 window-level errors，不用 aggregate metric 隱藏單窗失敗。

### Confirmatory acceptance

只有下列條件全滿足，才可升級為跨時間 effective-scale release：

1. 至少 10 個非重疊 calibration clusters，cluster bootstrap 95% CI 完全大於 0。
2. 預先凍結的 validation windows 全部保留，predicted loss 方向正確。
3. 每個 validation observation 落在預先定義的完整 prediction interval；若 density correlation 尚未識別，必須同時報獨立與完全相關 bounds，不能挑較寬者宣稱通過。
4. Validation RMSE 低於 `beta=0` 與「2024 mean loss」兩個 naive baselines。
5. Endpoint 4／6／8、quadrature 與合理 WLS sensitivity 不改變 go/no-go 結論。
6. Maneuver/source audit 完成；Phase 5 chronological claim 另須通過上游 2024-only freeze。

任一 confirmatory 條件失敗，保留數值與 audit，但結論是 rejected／insufficient evidence；不得 refit 2026、改窗或把 `beta_eff` 改稱 physical `B`。

## 10. 為何只能叫 `beta_eff`

Fitted scale 同時吸收：

- 未知或時變的 \(C_D\)、迎風投影面積、質量與姿態；
- atmosphere co-rotation、thermospheric wind 與 \(v_{rel}\ne v\)；
- DNSAPOD／Phase 4／Phase 5 density scale 與 smoothing bias；
- B-L J2--J5、`M2=0` mean-element estimator 的 residual；
- endpoint OLS、phase-window mapping 與 left-rule quadrature error；
- 未標出的 maneuver、radiation pressure 與其他 non-drag force。

此外 DNSAPOD density 本身由 POD aerodynamic acceleration 反算，Phase 4/5 又是 retrospective／conditional data product。用它和 POD-derived semi-major axis fit 出的比例不是完全獨立的 spacecraft property。

因此欄位與報告只使用 `beta_eff_m2_kg` 或 `effective_density_to_decay_scale_m2_kg`。禁止使用 `ballistic_coefficient`、`physical_beta`、`measured_CdA_over_m` 或 `calibrated_B_eff`，除非未來有獨立 attitude、mass、surface／drag coefficient、wind 與 force-model validation。

## 來源界線

- Repo 直接證據：[`phase6_quiet_closure.md`](../lineage/phase6_quiet_closure.md)、[`phase6_quiet_audit.md`](../lineage/phase6_quiet_audit.md)、[`research_phase1_mean_anomaly_phase5_density_to_decay.md`](research_phase1_mean_anomaly_phase5_density_to_decay.md)。
- Ram et al. 支持 orbit-mean semi-major axis -> daily OLS 的 secondary check，不支持本專案的 mean-anomaly boundary、window-level `beta_eff` 或 acceptance threshold。
- Li and Lei 支持完整 POD energy／force accounting 的必要性，不把本文件的簡式升級成等價方法。
- OLS／WLS、bootstrap 與 acceptance rules 是本專案針對現有資料量的預先規格，不是上述 orbital-decay 論文直接給出的 Swarm calibration procedure。
