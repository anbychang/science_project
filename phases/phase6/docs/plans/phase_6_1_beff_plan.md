# P6.1：逐分鐘 L2 density 擬合單一 `B_eff`

## 決定

P6.1 只做一件事：用 2023-07-01 至 2026-06-30 的逐分鐘 L2 density 與 POD mean semi-major axis，擬合一個全域 `B_eff`。

P6.1 不分 magnetic storm 與 quiet period，不比較 density model，不做 orbit forecast，也不把 `B_eff` 解讀成衛星的已校準物理常數。

```text
DNSAPOD instantaneous density (30 s)
  + Phase 1 POD mean semi-major axis (10 s)
  -> complete 1-minute pairs
  -> density integral
  -> one global B_eff
```

## 定義

每個完整分鐘 `k` 有：

- `rho_k`：該分鐘兩筆 DNSAPOD instantaneous density 的平均，單位 `kg/m^3`。
- `a_k`：該分鐘六筆可用 POD mean semi-major axis 的平均，單位 `m`。
- `mu`：Earth gravitational parameter，單位 `m^3/s^2`。
- `Delta t = 60 s`。

以梯形法累積 density kernel：

\[
K_n=\sum_{k=1}^{n}
\frac{\rho_{k-1}\sqrt{\mu a_{k-1}}+\rho_k\sqrt{\mu a_k}}{2}\Delta t.
\]

每個連續 block 從第一分鐘重新設零：

\[
\Delta a_{POD,n}=a_n-a_{block,start}.
\]

全三年只擬合一個通過原點的比例：

\[
B_{eff}=
-\frac{\sum_n K_n\Delta a_{POD,n}}
{\sum_n K_n^2}.
\]

最後只取：

\[
\Delta a_{fit,n}=-B_{eff}K_n.
\]

## 資料門檻

- 一分鐘必須有 2 筆有效 DNSAPOD density。
- 一分鐘必須有 6 筆 `is_usable=1` 的 POD mean semi-major axis。
- 同一分鐘只能屬於一個 `chunk_id`。
- 缺一分鐘或 `chunk_id` 改變就切新 block；不補值、不跨缺口積分。

## 唯一主結果

\[
\boxed{B_{eff}=0.0092292068\ \mathrm{m^2/kg}}
\]

逐分鐘 fit 有 1,575,708 個 paired minutes、1,575,671 個 integral points 與 37 個 continuous blocks。

逐圈 sensitivity 的 `B_eff=0.0092140060 m²/kg`，逐分鐘結果高 `0.165%`。兩種時間解析度得到相近尺度；P6.1 仍只採逐分鐘值作主結果。

## 主張界線

`B_eff` 是 L2 積分線對 POD 半長軸線的全三年 in-sample 有效比例。L2 DNSAPOD 與半長軸都依賴 POD，因此這不是獨立驗證，也不是 `C_D A/m` 的直接測量。

逐分鐘 POD 有明顯短週期抖動。MAE 與 RMSE 只作 closure audit，不是 P6.1 的研究目標，也不代表逐分鐘 forecast skill。
