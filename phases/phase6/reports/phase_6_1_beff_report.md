# P6.1：逐分鐘 L2 density 擬合 `B_eff`

## 結果

P6.1 已完成。唯一主結果是：

\[
\boxed{B_{eff}=0.0092292068\ \mathrm{m^2/kg}}
\]

這個值由三年逐分鐘 L2 density 積分線與 POD mean semi-major axis 線共同擬合。沒有按年份、磁暴、quiet period 或 continuous block 分別調整。

## 實際資料

| 項目 | 數值 |
| --- | ---: |
| UTC 範圍 | 2023-07-01 -- 2026-06-30 |
| DNSAPOD daily ZIP | 1,096 |
| complete paired minutes | 1,575,708 |
| integral points | 1,575,671 |
| continuous blocks | 37 |
| `B_eff` | 0.0092292068 m²/kg |

每分鐘使用 2 筆 DNSAPOD instantaneous density 與 6 筆可用 POD mean semi-major axis。積分使用 60 秒梯形法；缺分鐘或 `chunk_id` 改變就重開 block。

## 與逐圈 sensitivity 比較

| Resolution | `B_eff` |
| --- | ---: |
| 逐分鐘 P6.1 | 0.0092292068 m²/kg |
| 逐圈 retained sensitivity | 0.0092140060 m²/kg |
| 相對差 | +0.165% |

兩種時間解析度得到相近的有效比例。P6.1 採逐分鐘結果；逐圈結果只保留作 sensitivity。

## 不做的解讀

- P6.1 不判斷 magnetic storm 是否增加 decay。
- P6.1 不驗證 Phase 5 density model。
- P6.1 不提供逐分鐘 orbit forecast。
- `B_eff` 不是已校準的 `C_D A/m`；它吸收未建模效應與共同 POD lineage。
- MAE `68.47 m`、RMSE `85.11 m` 只記錄 in-sample closure。逐分鐘 POD 短週期抖動使它們不是本步的研究結論。

方法定義見[P6.1 plan](../docs/plans/phase_6_1_beff_plan.md)，資料 key 與實際 row 見[資料血緣](../docs/lineage/phase6_1_beff.md)。
