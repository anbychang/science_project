# Phase 2：各階段步驟與公式（GPR 版 v3）

## 狀態

討論中。尚未採納、尚未實作、尚未寫入 SQLite。

WARNING: 此草稿的部分假設與目前 Phase 1 working output 不一致；特別是 6 小時 POD、一天差分衰減率、固定衰減率篩選、ESA per-epoch quality flag。討論後才可成為正式規格。

## 記號

`t`：時間；`r`、`v`：衛星位置與速度向量；`mu`：地心引力常數；`R`：地球赤道半徑；`J2`：二階重力場係數；`a`：半長軸；`e`：離心率；`i`：傾角；`tau`：延遲；`rho`：大氣密度；`D(t)`：衰減速率。

## 第一階段：資料準備與平均衰減速率

### 步驟 1.1：讀取 POD 並檢查格式

輸入為 Swarm POD 的位置與速度，時間戳採 UTC，座標系統為地固座標（ECEF）。若產品為地心慣性座標（ECI），需先轉換，否則後續的能量與角動量計算會有系統性偏差。

檢查項目包括：時間戳是否單調遞增、是否有重複時間點、位置向量長度是否都在 6,700 到 6,900 公里範圍內（對應 Swarm 高度）。不符合的記錄直接標記。

### 步驟 1.2：計算比能量

```text
E = |v|^2 / 2 - mu / |r|
```

`E` 為負值，代表衛星處於束縛軌道。`E` 越負，軌道能量越低，衛星越靠近地球。

### 步驟 1.3：計算瞬時半長軸

```text
a_osc = -mu / (2E)
```

這是衛星在時刻 `t` 的瞬時橢圓軌道半長軸，包含所有短週期擾動。

### 步驟 1.4：計算角動量、離心率與傾角

```text
h = r x v
e = sqrt(1 + 2E|h|^2 / mu^2)
i = arccos(h_z / |h|)
```

離心率在 Swarm 軌道上接近 0.001，傾角接近 97 度。若計算出的值明顯偏離，代表位置或速度有誤。

### 步驟 1.5：Brouwer-Lyddane 解析變換

目標是把瞬時半長軸轉換為平均半長軸：

```text
a_mean(t) = a_osc(t) - delta_a_sp(t)
delta_a_sp ~= a * J2 * (R / a)^2 * g(e, i, M, omega)
```

`delta_a_sp` 為短週期擾動總和；`g` 是關於平近點角 `M`、近地點幅角 `omega`、離心率 `e` 與傾角 `i` 的三角函數組合。確切形式需從 Brouwer（1959）、Lyddane（1963）或 Vallado 取得完整係數，不能使用簡化版本。

實作順序：先計算 `M` 與 `omega`，再代入 `g`，得到 `delta_a_sp`，最後得到 `a_mean`。

### 步驟 1.6：衰減速率

```text
D(t) = (a_mean(t + 1 day) - a_mean(t)) / 1 day
```

`a` 以 m 計、時間以 day 計，`D` 的單位為 m/day。草稿主張使用一天間隔，避免相鄰短時間差分放大測量噪聲。

### 步驟 1.7：品質控制

依序套用並記錄各規則剔除數量：

```text
0.3 m/day <= D(t) <= 3 m/day
|d^2 a_mean / dt^2| <= threshold
ESA quality flag = good
```

草稿範例的二階變化 threshold 是 `0.5 m/day^2`。

### 步驟 1.8：多源資料整合

統一到 10 分鐘網格：

```text
SYM-H: linear interpolation
Ap, F10.7: forward fill
D(t): linear interpolation only within valid observations +/- 1 h
```

超出有效範圍標記為缺失。

### 步驟 1.9：降採樣至每小時

從 10 分鐘網格每小時取整點一筆。草稿預期磁暴總資料約為 3,000 到 5,000 點；理由是降低高度自相關並保留 1 到 8 小時延遲解析度。

## 第二階段：磁暴偵測、三階段劃分與延遲標籤

### 步驟 2.1：磁暴偵測

```text
start: SYM-H drops > 20 nT within 60 min
       and cumulative drop > 50 nT
intensity: minimum SYM-H < -100 nT
independence: adjacent storms separated by >= 48 h
```

另記錄 threshold 改為 `-80 nT` 或 `-120 nT` 時的事件數量，作敏感度分析。

### 步驟 2.2：能量輸入代理量

```text
S(t) = max(0, -SYM-H(t) - 50)
I_past(t) = integral from t-6h to t of S(t') dt'
I_rate(t) = dSYM-H(t) / dt
```

`S(t)` 單位為 nT，`I_past(t)` 單位為 nT h，`I_rate(t)` 單位為 nT/h。

### 步驟 2.3：三階段劃分

```text
initial phase: first SYM-H < -20 nT -> SYM-H minimum
main phase: SYM-H minimum -> recovery slope > 5 nT/h
recovery phase: main-phase end -> SYM-H > -50 nT
```

### 步驟 2.4：延遲標籤

對每個時刻 `t`：

```text
driver: I(s) = S(s), s in [t - 6 h, t]
response: D(s + tau), s in [t - 6 h, t]

rho_t(tau) = corr(S(s), D(s + tau))
tau_obs(t) = argmax over tau in [0 h, 12 h] of rho_t(tau)
```

候選 `tau` 以 0.5 h 為步長。最大相關係數小於 `0.3` 時，標記 label 不可靠且不納入訓練。

因果性：driver 只來自 `t` 前資料；response 的未來值僅用來建立 label，不可作為模型 input。預報使用的 feature 只能來自 `t` 前資訊。

## 討論前不得採用的項目

- 不得把此草稿的固定 `0.3..3 m/day` threshold、二階變化 threshold 或 ESA per-epoch quality flag 當成現有 Phase 1 規則。
- 不得把一天差分或每小時降採樣宣稱為已完成輸出。
- 不得把 future response 用於 feature；它只可在 label construction 出現。
- 不得把 density 自動加入 core analysis table。
