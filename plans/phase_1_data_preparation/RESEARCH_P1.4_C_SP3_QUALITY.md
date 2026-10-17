# P1.4-C Q3：SP3 逐 epoch 品質欄位查核

決定：目前資料庫沒有可驗證可用的 ESA 逐 epoch 品質旗標或位置標準差；
P1.4 不建立「官方品質通過」欄位。

```text
SP3 {P/V state}
  -> quality_source: unavailable
  -> project checks {finite, bound, cadence, gap}
```

## 1. ESA 產品定義

ESA／TU Delft 的 `SP3xCOM_2_` catalogue 指定：

```text
SW_OPER_SP3ACOM_2_
  = {ITRF center-of-mass position, velocity}
  quality indicator
  = separate SP3xVAL_2_ validation report
```

- `SP3xCOM_2_` 是 position/velocity time series，格式為 SP3c。
  [ESA product catalogue](https://swarm-disc.github.io/product-catalogue-tools/SW_SP3xCOM_2_.html)
- 該 catalogue 將 quality indicator 明定為獨立的 `SP3xVAL_2_`
  validation report，不是 `SP3xCOM_2_` record 欄位。
  [ESA product catalogue](https://swarm-disc.github.io/product-catalogue-tools/SW_SP3xCOM_2_.html)

## 2. SP3 格式能力 != 此產品提供的資料

SP3c 格式本身可以有逐 epoch 品質資訊：

```text
P record
{
  cols 62..69: X/Y/Z position standard-deviation exponents,
  col 79: maneuver flag,
  col 80: orbit-predicted flag
}

EP record (optional)
{position standard deviations, correlations}

++ header
{one accuracy exponent / satellite / whole file}
```

- `P` record 的位置標準差在 cols 62..69；空白表示 unknown。
  `M` / `P` 軌道旗標分別在 cols 79 / 80；短 record 的缺欄視為空白。
  [IGS SP3 format specification, pp. 15--16](https://files.igs.org/pub/data/format/sp3d.pdf)
- `EP` 是 optional record，才可存更精確的逐 epoch position standard
  deviations 與 correlations。
  [IGS SP3 format specification, p. 16](https://files.igs.org/pub/data/format/sp3d.pdf)
- header `++` 是整個檔案中該衛星的 orbit accuracy exponent；`0` 是
  accuracy unknown，不是逐 epoch pass/fail。
  [IGS SP3 format specification, p. 14](https://files.igs.org/pub/data/format/sp3d.pdf)

## 3. 本機資料盤點

快速 inventory 讀取全部 `data/swarm_a_pod/*.ZIP` 的 header 與第一個 epoch：

```text
files: 1685
first P record: all < 80 chars
first P record cols 62..80: absent -> blank -> unknown
first epoch EP / EV record: none
++ header non-zero accuracy exponent: 0 files
```

另完整讀取 `SW_OPER_SP3ACOM_2__20211231T235942_20220101T235942_0201.ZIP`：
沒有 `EP` / `EV`，其 `P` / `V` record 均為 60 chars。依 SP3 規格，
short record 的 absent trailing fields 是 blank；因此不能把缺失欄位當作
「品質良好」或「observed」。

此 inventory 尚未逐行掃描其餘 1,684 個檔案的全部 epoch；因此結論是
「P1.4 沒有可用的已驗證 official quality」，不是聲稱每個檔的每個 epoch
都已逐欄完成查核。

## 4. P1.4 實作界線

```text
allowed
{finite state, bound orbit, 10-second cadence, gap interval}

not allowed
{ESA per-epoch quality flag, ESA per-epoch sigma threshold,
 "official quality passed"}
```

若研究需要官方軌道品質，下一步是取得 `SP3xVAL_2_`，再定義它和
`SP3xCOM_2_ {UTC, source_id}` 的對齊規則；未取得前保持
`quality_source: unavailable`。
