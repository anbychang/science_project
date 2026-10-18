# Swarm-A 軌道提升與 maneuver catalog 稽核

## 結論

原本三段 `orbit-raise campaign` 不足以排除所有有官方證據、會污染
Swarm-A 半長軸差分的操作日期。資料涵蓋範圍 `2022-01-01` 至
`2026-08-13` 內，另外有兩個可精確到 UTC 日、但不是 broad campaign 的
Swarm-A maneuver：

| ID | 類別 | 最小可辯護 UTC interval | 官方事實 | 對本機資料的關係 |
| --- | --- | --- | --- | --- |
| `SWA_ORBIT_CONTROL_2022-01-13` | `orbit_control_manoeuvre` | `[2022-01-13T00:00:00Z, 2022-01-14T00:00:00Z)` | ESA 報告明列 Swarm-A 在 `13 January 2022` 進行 orbit-control manoeuvre。 | 這是目前 campaign 外最大的 12-hour 正 `delta_a`：終點 `2022-01-14T00:00:00Z` 為 `+273.788 m`，等價於 `-547.576 m/day` 的輸出衰減率。 |
| `SWA_CAM_2023-01-06` | `collision_avoidance_manoeuvre` | `[2023-01-06T00:00:00Z, 2023-01-07T00:00:00Z)` | ESA 報告明列 Swarm-A 與 C 各在 `06/01/2023` 執行一次 CAM。 | 本次掃描沒有同級的大上升；但它是已確認的 A maneuver，仍不能進入自然衰減樣本。 |

官方文件沒有提供兩個 maneuver 的 burn UTC、duration、direction 或 delta-v。因此上表是
**date-level** exclusion，不可被寫成逐 epoch firing label。半開區間能讓後續 12-hour
backward difference 在新 chunk 的 72 個 10-minute warm-up 後，自動排除跨 maneuver 比較。

## 完整 catalog：本資料涵蓋範圍內可確認的 Swarm-A 操作

| ID | 類別 | UTC interval | 是否已是 pipeline exclusion | 一手來源 |
| --- | --- | --- | --- | --- |
| `SWA_ORBIT_CONTROL_2022-01-13` | orbit-control maneuver | `[2022-01-13, 2022-01-14)` | 否 | [ESA-prepared CGMS report, PDF p. 18](https://www.cgms-info.org/Agendas/GetWpFile.ashx?aid=4fafae3c-cc18-435d-a9c9-d82d0d036fe5&wid=dfc681dd-16f6-41a0-a923-c854e330489c) |
| `SWA_C_ORBIT_RAISE_2022` | orbit-raise campaign | `[2022-05-03, 2022-07-09)` | 是 | [ESA report](https://www.esa.int/Space_Safety/Swarm_dodges_collision_during_climb_to_escape_Sun_s_wrath); [ESA campaign notice](https://earth.esa.int/eogateway/news/swarm-alpha-and-charlie-orbit-raise-campaign-starting-on-3-may-2022-potential-impact-on-data-quality) |
| `SWA_CAM_2023-01-06` | collision-avoidance maneuver | `[2023-01-06, 2023-01-07)` | 否 | [ESA-prepared CGMS report, PDF p. 14](https://www.cgms-info.org/Agendas/GetWpFile.ashx?aid=4d8a2caa-2bbf-44a8-8723-a5847e1b1ce5&wid=dfc681dd-16f6-41a0-a923-c854e330489c) |
| `SWA_C_ORBIT_RAISE_2023_PHASE_II` | orbit-raise campaign | `[2023-04-26, 2023-06-08)` | 是 | [ESA campaign notice](https://earth.esa.int/eogateway/news/swarm-alpha-and-charlie-orbit-raise-campaign-starting-on-26-april-2023-potential-impact-on-data-quality) |
| `SWA_C_ORBIT_RAISE_2026` | orbit-raise campaign | `[2026-07-21, 2026-08-01)` | 是 | [ESA QRAS Week 30 L1B report, p. 7](https://ftp-qras.earth.esa.int/swarm/swarm_instruments/weekly/2026/swarm--swarm_instruments--weekly--20260720--l1b.pdf) |

注意：2022 的 6/30 debris-avoidance 與被重排的 raise maneuver 都發生在既有
`SWA_C_ORBIT_RAISE_2022` interval 內；不需要再新增一段區間。ESA 對該事件的說明是
30 June 16:00 CEST 收到 Alpha 的 alert，四小時內完成 evasive action，並在 24 小時內
完成重排的 maneuver。[ESA report](https://www.esa.int/Space_Safety/Swarm_dodges_collision_during_climb_to_escape_Sun_s_wrath)

## 查核範圍與未發現事項

- 對 v1 的 10-minute mean-orbit table，以同 chunk、相隔 12 小時的 `a(t) - a(t-12h)`
  掃描；已排除原三段 campaign 後，最大的正差分是 `2022-01-14T00:00:00Z` 的
  `+273.788 m`。它與 1/13 官方 maneuver 的日界不足以將其歸因到其他自然過程。
- `2023-01-06` 是官方已確認操作日，但沒有造成同級上升；它仍須排除，這是規則完整性，
  不是由數值 threshold 推斷 maneuver。
- 2023-09-28、10-05、10-12、10-19 的 raise 是 Swarm-B；2023-11-17 的 CAM 是
  Swarm-C。它們不能成為 Swarm-A 資料的排除依據。來源：[ESA-prepared CGMS report,
  pp. 15–16](https://www.cgms-info.org/Agendas/GetWpFile.ashx?aid=6e1f8b19-7eb6-4356-bbe6-0673c950ba5e&wid=da80287c-7a8a-44bd-8c5f-3e2499564b22)。
- 以 ESA、EO Gateway、QRAS、ESOC/ESA-prepared CGMS 的公開一手文件檢索後，沒有找到
  2024–2025 或 `2026-08-13` 前另一段能精確指向 Swarm-A 的 raise/CAM 日期。這是
  「公開文件未找到」；不是「沒有 maneuver」的證明。

## 建議的程式與記憶模型

不要把所有操作硬塞進 `PLANNED_ORBIT_RAISE_INTERVALS`。那會把 confirmed CAM 或
orbit-control maneuver 錯稱為 campaign。應在同一份 canonical event table 儲存：

```text
{ id, start_time_us, stop_time_us, kind, spacecraft, evidence_url }

kind in {
  orbit_raise_campaign,
  orbit_control_manoeuvre,
  collision_avoidance_manoeuvre
}
```

P1.4 以共用 helper 判斷全部 Swarm-A event；`rejection_reason` 必須保留 event kind 或
stable event ID。只有 `orbit_raise_campaign` 才可以被文件稱為 `planned_orbit_raise_campaign`。
加入兩個新日期後，必須 rebuild P1.4 至 P1.7，並更新
`ORBIT_RAISE_CAMPAIGN_MEMORY.md` 成為包含 campaign 與 single-event maneuver 的唯一記憶。

## 證據邊界

- 這是 mission-operation exclusion，不是 `SP3ACOM` epoch-level quality failure 的判決。
- 沒有可公開驗證的 burn UTC 前，不把個別 10-minute jump 說成一次特定 firing。
- 不以 `m/day` 的大小自動拒絕 candidate；官方日期先進 exclusion，未確認 candidate 保持
  audit-only。
