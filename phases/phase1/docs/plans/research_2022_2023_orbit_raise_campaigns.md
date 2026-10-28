# 2022–2023 Swarm-A 半長軸異常為何集中在 4–6 月

## 結論

「多數候選異常在五月」不是目前可支持的季節性 `beta-angle` 或 GPS geometry 結論。現有證據更直接：專案掃出的 2022 年 5–6 月與 2023 年 4–5 月候選日期，分別完整落在 ESA 已公開的 Swarm-A/C 軌道抬升 campaign 期間。

```text
2022-05-03 .. 2022-07-08  Swarm-A/C orbit raise campaign
2023-04-26 .. 2023-06-07  Swarm-A/C orbit raise campaign, phase II
```

因此這些日期的 `a` 結構不能納入自然軌道衰減或 geomagnetic-storm response 的統計。應先當成 `planned_orbit_raise_campaign` 候選區間排除或分層處理。

這**不能**推出每一個 10 分鐘 bin、每一個 400 m 跳變，或 2023-05-09 05:20–06:20 UTC，恰好就是一次 thrust firing。公開來源確認的是 campaign window，不是逐次 maneuver 的 UTC log。

## 與本專案候選日期的對齊

本專案先前以 `abs(10-min mean a - 12h smooth a) >= 500 m` 找到的主要日期，和公開 campaign window 的關係如下。左欄是本機資料分析結果，不是官方 maneuver log。

| 本機候選日期 | 已確認的官方 campaign window | 判定 |
|---|---|---|
| 2022-05-10、05-24、05-31、06-15、06-22 | 2022-05-03 至 2022-07-08 | 在 campaign 內 |
| 2023-04-26、05-04、05-09、05-11、05-17、05-24、05-26 | 2023-04-26 至 2023-06-07 | 在 campaign 內 |

這解釋了為何異常看起來集中在五月：資料涵蓋的兩個主要異常群，剛好是兩次春末開始、跨越數週的軌道抬升工作，不是已證實的每年五月自然週期。

## 官方已證實的事實

| 事實 | 證據 | 直接來源 |
|---|---|---|
| Swarm-A/C 在 2022-05-03 至 2022-07-08 進行抬升 orbit 的 campaign，目標為 `45 km`。 | NASA 的 ILRS mission-news 對日期與目標高度作出明確記錄。 | [NASA ILRS Mission News](https://ilrs.gsfc.nasa.gov/missions/satellite_missions/Mission_News.html) |
| 2022-07-14 的 ESA 報導確認 A/C 為進入較低大氣密度區而爬升；兩星原訂在 10 週內各執行 25 次 maneuver。 | ESA 同時說明其中一次 Alpha maneuver 因緊急避碰被取消並重排。 | [ESA: Swarm dodges collision during climb to escape Sun's wrath](https://www.esa.int/Space_Safety/Swarm_dodges_collision_during_climb_to_escape_Sun_s_wrath) |
| 2023-04-26 至 2023-06-07 是 A/C orbit campaign 的 Phase II。 | NASA ILRS 條目直接指向 ESA 的原始公告。 | [NASA ILRS Mission News](https://ilrs.cddis.eosdis.nasa.gov/missions/satellite_missions/Mission_News.html)；[ESA 原公告](https://earth.esa.int/eogateway/news/swarm-alpha-and-charlie-orbit-raise-campaign-starting-on-26-april-2023-potential-impact-on-data-quality) |
| 2022 campaign 的 ESA 原公告起日為 2022-05-03，並明示可能影響 data quality。 | 該頁目前對自動讀取回傳 `403`，但 URL、標題與日期由 ESA 發布且被 NASA ILRS 索引；保留原始 URL 供人工瀏覽。 | [ESA 原公告](https://earth.esa.int/eogateway/news/swarm-alpha-and-charlie-orbit-raise-campaign-starting-on-3-may-2022-potential-impact-on-data-quality) |
| `SP3ACOM` 是 reduced-dynamic position/velocity product；品質結果應由獨立 `SP3xVAL` report 提供。 | 單一 SP3 檔不應被當作逐 epoch maneuver log 或 validation 結果。 | [ESA/TU Delft SP3xCOM product catalogue](https://swarm-disc.github.io/product-catalogue-tools/SW_SP3xCOM_2_.html) |

## 不應成立的推論

- **不是「五月一定有自然半長軸跳變」。** 目前只看到兩個受任務操作主導的年份區間；這不足以建立年週期。
- **不是「所有候選點已證實為 maneuver」。** campaign 內可能包含 thrust、maneuver 後的精密軌道解重估、正常軌道演化，以及本流程的 mean-element 處理結構。沒有逐次 firing UTC 或 `SP3AVAL` 前，不能再細分。
- **不是 `beta-angle` 已被排除。** 本次只查到 campaign 的直接文件；沒有找到 ESA 官方資料把這些日期的 `SP3ACOM` 半長軸偏移歸因於 beta angle、eclipse geometry 或 GPS tracking geometry。
- **不是 UTC、km/m 或 velocity unit 的問題。** 這些已由本機 state/derivative 恆等式檢查排除；本備忘錄只新增任務操作脈絡。

## 對資料處理的決定

目前最小且可追溯的處理是保留原始資料，新增或在分析時套用 campaign exclusion interval：

```text
Swarm-A planned orbit raise
  2022-05-03T00:00:00Z .. 2022-07-08T23:59:59Z
  2023-04-26T00:00:00Z .. 2023-06-07T23:59:59Z
```

- 這是 campaign-level flag，不是假裝已知的逐 epoch maneuver flag。
- 所有跨越該 interval 的 `delta_a`、forward 12 h rate、smooth derivative 都應標為 contaminated，不能用於 storm-response 主統計。
- 若研究問題需要保留 campaign 內資料，必須先取得 ESA 的逐次 maneuver history 或對應 `SP3AVAL`，再以實際 firing times 做更窄的排除。

## 尚待證據

1. ESA 的 Swarm spacecraft anomalies and manoeuvres history 是否有 2022–2023 的延伸版與逐次 UTC。
2. `SP3AVAL_2_` 是否覆蓋每個候選日，以及該 report 能否標示軌道解品質變化。
3. campaign 外的候選日期是否仍呈現同等級半長軸結構；若有，才另查 beta angle、GPS geometry、frame 或 mean-element algorithm。
