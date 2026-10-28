# Phase 4 計畫：M1 基線的 GPR 殘差修正

## 狀態與研究界線

狀態：[working]。本文件保存 2026-10-28 提出的 GPR 殘差修正設定，並對齊 [Phase 3 結案報告](../../../phase3/reports/phase_3_final_report.md)。使用者看過一圈／兩圈 L2 對照圖後，選回一圈窗口作正式資料單位。25 折 GPR 留一場驗證與逐場 M1/GPR 比較圖已交付，詳見[Phase 4 結果報告](../../reports/phase_4_gpr_loso_report.md)與[資料血緣](../lineage/phase_4_gpr_loso.md)；模型好壞待使用者目視判斷。Phase 5 的題目另定；原提案其餘特徵留待 Phase 6 討論。

Phase 4 讀取既有結果，寫入獨立的 Phase 4 輸出；Phase 2、Phase 2R、Phase 3 的檢查點與報告不回寫。研究仍是磁暴與 Swarm-A 密度響應；本步不接大氣阻力或軌道傳播。

## 1. 物理基線與 GPR 目標

Phase 3 的 M1 基線為

$$
\rho_{\mathrm{phys},k,i}
=\rho_{\mathrm{MSIS,q,phase},k,i}R_k
\exp\!\left(GH_{\tau,\mathrm{phase},k,i}\right).
$$

其中 $k$ 是磁暴、$i$ 是該場的密度資料列；$H_\tau$ 是以 `SME - 65 nT` 作輸入的一階記憶濾波，單位仍為 nT，不能稱為實測加熱功率。Phase 4 直接讀取 Phase 3 最終預測 SQLite 的逐場 $R_k$，令 $c_k=\ln R_k$；此值只由該場的低活動窗口取得，不跨場估計。每折只用訓練場重新選 $\tau^*$ 與 $G^*$，以 $\rho_{\mathrm{phys}}^{(4)}=\rho_{\mathrm{MSIS,q}}\exp(c_k+G^*H_{\tau^*})$ 作該折基線。密度與響應均先作 $u\pm\pi$ 相位平均，再形成密度比。

GPR 只學基線尚未解釋的對數殘差：

$$
y_{k,i}=\ln\!\left(
\frac{\rho_{\mathrm{L2},k,i}}{\rho_{\mathrm{phys},k,i}}
\right),\qquad y\sim GP(0,k(x,x')).
$$

零均值使遠離訓練特徵的修正趨近 0，密度預測因而趨近物理基線；「訓練筆數少」本身不保證每個位置都退回基線。L2 是有觀測誤差的對照資料。

給定 GPR 的對數殘差均值 $\mu_{\mathrm{gp}}$ 與標準差 $\sigma_{\mathrm{gp}}$，密度中位數與條件式 95% 預測區間為

$$
\widehat\rho_{\mathrm{median}}=\rho_{\mathrm{phys}}e^{\mu_{\mathrm{gp}}},
\qquad
\left[\rho_{\mathrm{phys}}e^{\mu_{\mathrm{gp}}-1.96\sigma_{\mathrm{gp}}},
\rho_{\mathrm{phys}}e^{\mu_{\mathrm{gp}}+1.96\sigma_{\mathrm{gp}}}\right].
$$

此區間以已擬合的物理基線及 GPR 超參數為條件，沒有涵蓋 $\tau$、$G$、$c_k$ 與超參數估計的不確定性。

## 2. 中心相位錨點與四維設定

每列以 `{storm_id, time_us, u_rel_rad}` 標識一個中心相位錨點；沿用 Phase 2/3 以 $t_0$ 為原點的連續相位 $u$，保留 $t_0$ 前後事件範圍。正式窗口為 $u\pm\pi$，每筆涵蓋前後各半圈；每場以 $u=2\pi j$ 為中心格點，在完整且覆蓋率至少 80% 的錨點中選最近一列，距格點最多 $0.01$ 圈，得到 2,295 列。各列是 Phase 3 一圈相位平均的代表錨點。輸入固定為 `{h_tau_phase_nt, h_24h_phase_nt, sme_phase_nt, symh_phase_nt}` 四欄，均以同一一圈窗口及原生配對樣本數加權平均；缺值列不可進模型。逐折只用訓練場標準化。

| 特徵 | 要檢查的殘差規律 |
| --- | --- |
| $H_{\tau^*}$ | M1 已使用其線性對數響應；檢查較強／較弱響應時是否留下非線性殘差。每折的 $\tau^*$ 由訓練場決定。 |
| $H_{24h}$ | 檢查較長活動記憶是否影響預熱與恢復；須從連續 SME 另算，Phase 3 的 0–10 h 粗格點表不含此欄。 |
| `SME` | 檢查短期驅動變化是否提供 $H_{\tau^*}$ 之外的資訊。暫按同一 $u\pm\pi$ 窗口聚合；不是錨點當分鐘的瞬時值。 |
| `SYM-H` | 檢查磁暴狀態是否提供 SME 之外的資訊；不把相關性解讀成直接加熱因果。暫按同一相位窗口聚合。 |

Phase 3 的中心相位窗口會讀到錨點之後；置中 F10.7A 亦使用未來日期。因此本計畫先定位為**離線回溯密度驗證**。若日後要求即時預測，須另定只用截止時刻以前資料的取樣與特徵，重新驗證。相位平均、濾波與差分的可用時間也須逐欄檢查。

## 3. 核函數與擬合設定

候選核函數：`ConstantKernel × RBF(ARD) + WhiteKernel`。每個標準化特徵各有一個 RBF 長度尺度 $\ell$；初值 1.0、範圍 0.01–1000。`WhiteKernel` 初值 0.1、範圍 $10^{-5}$–1；`ConstantKernel` 的初值為 1.0，其界限在實作前明定並記錄。

使用 scikit-learn `GaussianProcessRegressor`：`normalize_y=False`、`n_restarts_optimizer=5`、`random_state=20261028`，採預設的 L-BFGS-B 核參數最佳化。`ConstantKernel` 界限為 $10^{-3}$ 至 $10^3$，`alpha=10^{-10}$ 為固定數值穩定項。逐折記錄 `ConvergenceWarning` 數量。零均值設定是退回物理基線的必要條件。`WhiteKernel` 表示觀測雜訊；`alpha` 不當成另一個待估雜訊變異。

ARD 的短 $\ell$ 表示模型對該標準化座標敏感，不能單獨證明物理因果重要性；SME、兩種時間尺度的響應與 SYM-H 可能相關。$\ell$ 達 1000 是特徵作用很弱的候選訊號；達 0.01 要檢查過擬合或資料問題。

## 4. 試跑與留一場磁暴驗證

先依本計畫選定一場測試磁暴，跑一折以核對來源鍵、相位窗口、特徵缺值、訓練／測試隔離、超參數與時間／記憶體成本。這是流程試跑，不拿單折結果宣稱模型有效。通過後再跑全部 25 折。

每折排除一場磁暴。其餘磁暴重新擬合 $\tau^*$、$G^*$ 與 GPR；各場 $c_k$ 固定取 Phase 3 的逐場 $R_k$，只由該場自己的低活動窗口估計，不跨場擬合。測試場的 $c_k$ 使用該場暴前 L2，成果稱為**取得暴前觀測後的條件式回放**。測試場的磁暴窗口 L2 不參與 $\tau$、$G$、標準化或 GPR 訓練。Phase 3 的選段相對真正 SME onset 尚未驗證，這是校準限制。

每一折執行：

1. 從 Phase 3 最終 SQLite 讀各場固定 $c_k$，再用訓練場的一圈資料選 $\tau^*$、$G^*$；算出同一一圈尺度的 $\rho_{\mathrm{phys}}$ 與 $y=\ln(\rho_{\mathrm{L2}}/\rho_{\mathrm{phys}})$。GPR 訓練列只取訓練場事件窗口內有效的一圈代表錨點。
2. 依第 2 節建立相同欄序的訓練與測試特徵矩陣，檢查時間窗口及事件鍵沒有交叉重複。
3. `StandardScaler` 只在訓練列 `fit`，再對測試列 `transform`；逐折保存均值、標準差、欄序於 `scaler_params.json`。
4. 依第 3 節設定零均值 GPR，`fit` 訓練殘差；對留出場用 `predict(return_std=True)` 取得 $\mu_{\mathrm{gp}}$、$\sigma_{\mathrm{gp}}$。
5. 由 `kernel_` 記錄各特徵 $\ell$、訊號與雜訊變異，連同對數邊際概似及折次寫入 `gpr_hyperparams.csv`。
6. 以留出場計算對數殘差 RMSE、MAE、95% 區間涵蓋率；另看密度峰附近與全窗口，最後以磁暴等權彙總，不讓長事件單獨主導總分。

含 `WhiteKernel` 的預測標準差用作 L2 觀測值的條件式預測區間；已核對所用 scikit-learn 版本的 `return_std` 行為。訓練組涵蓋率只作擬合診斷，留出場涵蓋率才是主要校準檢查。程式單元檢查遠離訓練特徵時 $\mu_{\mathrm{gp}}\to0$；實際事件外推仍待專門檢查。每場已出 M1、M1+GPR、L2 與預測區間圖；模型好壞由使用者看圖判斷，表格不自動貼成功標籤。

## 5. 已定設定與剩餘檢查

- **資料單位**：Phase 3 有 25 場、214,907 個有效一圈分鐘中心相位錨點；窗口高度重疊。Phase 4 採 $u=2\pi j$ 的最近有效錨點與 $u\pm\pi$ 一圈窗口，得到 2,295 列；每折 $\tau^*$ 的響應由連續 SME 重算。[一圈代表點圖](../../reports/phase_4_one_cycle_anchor_qc.md)記錄抽樣；[一圈／兩圈對照](../../reports/phase_4_two_cycle_window_qc.md)保留作視覺選擇紀錄，兩圈 1,131 列不進正式 GPR。
- **校準量**：直接讀 Phase 3 最終預測 SQLite `phase3_25storm_overview.r_candidate`；來源選段詳見 Phase 3 報告。此逐場固定值不隨留一折改變，並保留其暴前選段相對真正 onset 尚未驗證的限制。
- **校準截止**：Phase 4 不使用 `t_onset` 特徵；沿用 Phase 3 的 $R_k$ 選段。其截止是第一個強 SYM-H 低點之前，未證明早於 SME onset。`t_onset` 特徵留待 Phase 6；不得把 `t0` 換名當 onset。
- **可比性**：Phase 3 的 $\tau=4.65$ h 由全部 25 場選出，現有排除測試場的曲線只重估 $G$，不是本計畫的完整留一驗證。Phase 4 須各折重估 $\tau$ 與 $G$，並分開報告純 M1 與 M1+GPR 的留出場表現。
- **成本**：一圈 2,295 列、每折 5 次最佳化重啟。20 次迭代上限的首折試跑有 5／6 次提早停止，已排除。正式 25 折採 scikit-learn 預設最佳化，耗時 13,204 秒；折次存於 `folds_default_optimizer/`。25 折 `ConvergenceWarning` 總數為 0；逐場圖與主表已交付。
