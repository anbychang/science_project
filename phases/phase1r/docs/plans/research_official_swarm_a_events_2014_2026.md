# Swarm-A 官方軌道操作證據：2014--2026-06

## 決定

只把 ESA 或 ESA-hosted 一手文件明確指向 Swarm-A 的操作日期加入 P1.4
排除表。沒有逐次 burn UTC 時，以 UTC 整日或官方 campaign 的半開區間排除；
不可把資料中的每個半長軸跳變說成官方已確認的 firing。

本查核沒有找到 `2014--2021`、`2024--2026-06-30` 可寫成新日期區間的
Swarm-A 官方 event。因此不應為了「看起來奇怪」額外刪除這些年的資料。

## 可執行 catalog

| ID | kind | UTC exclusion interval | 官方明示的事實 | 信心 | 來源 |
| --- | --- | --- | --- | --- | --- |
| `SWA_ORBIT_CONTROL_2022-01-13` | orbit-control manoeuvre | `[2022-01-13T00:00:00Z, 2022-01-14T00:00:00Z)` | ESA-prepared CGMS 報告列出 Swarm-A 在 `13 January 2022` 的 orbit-control manoeuvre。未公開 burn UTC。 | high | [CGMS report, p. 18](https://www.cgms-info.org/Agendas/GetWpFile.ashx?aid=4fafae3c-cc18-435d-a9c9-d82d0d036fe5&wid=dfc681dd-16f6-41a0-a923-c854e330489c) |
| `SWA_C_ORBIT_RAISE_2022` | orbit-raise campaign | `[2022-05-03T00:00:00Z, 2022-07-09T00:00:00Z)` | ESA 於 2022-07-14 說明 Alpha/Charlie 各需在 10 週內做 25 次 maneuver 以進入較高軌道；這是既有 ESA campaign notice 的完整 campaign window。 | high | [ESA campaign notice](https://earth.esa.int/eogateway/news/swarm-alpha-and-charlie-orbit-raise-campaign-starting-on-3-may-2022-potential-impact-on-data-quality)；[ESA 2022-07-14](https://www.esa.int/Space_Safety/Swarm_dodges_collision_during_climb_to_escape_Sun_s_wrath) |
| `SWA_CAM_2023-01-06` | collision-avoidance manoeuvre | `[2023-01-06T00:00:00Z, 2023-01-07T00:00:00Z)` | ESA-prepared CGMS 報告列出 A/C 各在 `06/01/2023` 執行一次 CAM。未公開 burn UTC。 | high | [CGMS report, p. 14](https://www.cgms-info.org/Agendas/GetWpFile.ashx?aid=4d8a2caa-2bbf-44a8-8723-a5847e1b1ce5&wid=dfc681dd-16f6-41a0-a923-c854e330489c) |
| `SWA_C_ORBIT_RAISE_2023_PHASE_II` | orbit-raise campaign | `[2023-04-26T00:00:00Z, 2023-06-08T00:00:00Z)` | ESA 的 A/C Phase II campaign notice。逐次 firing UTC 未公開。 | high | [ESA campaign notice](https://earth.esa.int/eogateway/news/swarm-alpha-and-charlie-orbit-raise-campaign-starting-on-26-april-2023-potential-impact-on-data-quality) |

`2026-07-21` 起的 A/C campaign 已在既有 catalog，但晚於本次查核上限
`2026-06-30`，不屬於本表。

## 2022-06-30 避碰：不要重複新增 event

ESA 在 2022-07-14 的公開報導說 Alpha 的 debris alert 發生在
`30 June 16:00 CEST`，預測接近在八小時後；團隊在四小時內完成避碰，並於
24 小時內重排同一個 orbit-raise maneuver。該報導的短句是
“25 manoeuvres over a period of 10 weeks”。

這是已執行的 Swarm-A CAM，但它位於 `SWA_C_ORBIT_RAISE_2022` 內，
不另建較窄區間：官方沒有公布 burn UTC、duration 或 delta-v。把它再標成
獨立的一日 exclusion 不會增加排除範圍，反而會製造兩個看似獨立的事實。

## 已知但不可自動排除的操作

| 時段 | 官方事實 | 為何不進 event table |
| --- | --- | --- |
| 2014 orbit acquisition | ESA 說 2014 年完成 orbit acquisition；ESA-hosted LPS poster 說 final constellation 在 2014-04 完成。 | 公開資料沒有可驗證的 Swarm-A 操作起訖 UTC 或逐日清單。不能自行把整段 early-2014 宣告為精確 maneuver interval。 |
| 截至 2016-04 的 routine manoeuvres | ESA-hosted LPS poster 說 Swarm-A 有 9 次 constellation-maintenance manoeuvres、一次 A 的 CAM；亦提及一次序列在計畫 delta-v 的 69% 中止。 | 全部缺日期；只能作研究背景，不能據此移除任意資料列。 |
| 2017-01 Swarm-B alert | ESA 詳細記錄了規劃的 Swarm-B CAM，但最後 abort。 | 非 Swarm-A，且 manoeuvre 未執行。 |
| 2023-09--10 Swarm-B raises、2023-11 Swarm-C CAM | ESA-prepared CGMS 報告有明確日期。 | 不得拿其他 spacecraft 的操作刪除 Swarm-A。 |

## 使用規則

```text
official Swarm-A date or campaign
  -> {id, kind, [start, stop)}
  -> P1.4 is_usable = 0
  -> new chunk_id after the interval
  -> P1.5 checkpoint -> P1.6 -> P1.7 rebuild

official statement without date or UTC interval
  -> research note only
  -> no automatic row deletion
```

詳列的單日操作、campaign 與 2026 後續資料品質上下文，見
[orbit_raise_campaign_memory.md](../../../phase1/docs/plans/orbit_raise_campaign_memory.md) 與
[research_swarm_a_orbit_raise_catalog_audit.md](../../../phase1/docs/plans/research_swarm_a_orbit_raise_catalog_audit.md)。
