# Swarm-A Orbit Project - Time Log

最後更新：2026-09-16

這份檔案是本專案的共同外部記憶。它記錄已確認的決策、已做過的事情、刻意不做的事情，避免之後重複討論或把測試資料誤當研究資料。

## 1. 合作方式與程式規則

- 用繁體中文，先講結論，再講原因。
- 解釋要非常白話；一次只處理一個觀念。
- 程式碼不是只要能跑，還要讓人一眼看懂。
- 不用壓縮寫法：不用 list comprehension、generator expression、巢狀函式、過度抽象的 class 或工具層。
- 函式名稱要說清楚物理意義與單位，例如 `position_km`、`velocity_km_s`、`a_dot_km_s`。
- 程式註解盡量使用簡單英文；真的無法說清楚時才使用中文。
- 英文使用常見單字與短句，重點是容易理解，不追求複雜文法。
- docstring 用短格式與括號表示資料，例如：

  ```python
  """Input: {orbital_response, weather_points}
  Output: [{time, a_mean_km, a_dot_km_s, sym_h_nT, ...}, ...]"""
  ```

- 不把「檢查用、驗證用、一次性實驗用」程式混進主程式。真的需要時再另外寫。
- 不要靠很多層資料夾假裝整理。應刪掉不必要的東西；保留的檔名要能直接說用途。
- 檔名前綴統一為四個字母：`calc_` 是計算、`down_` 是下載、`load_` 是讀取本機檔案。

## 2. 目前研究目標

研究主題：盡量準確預測 Swarm-A 在指定時間的 XYZ 座標。

目前衛星：Swarm-A。

通訊系統不是本專案範圍。本專案只提供有座標系與時間標記的衛星位置；其他系統自行使用該位置指向衛星。

長期研究流程：

1. 取得公開 Swarm-A 精密軌道資料。
2. 讀取官方位置、速度與品質資訊。
3. 以官方精密軌道作為答案，檢查我們的傳播結果誤差。
4. 逐步加入 J2、大氣阻力與太空天氣資料，改善較長時間預測。

現在已有一日 Swarm-A 官方 POD、POD 讀取程式、GCRF／ITRF 轉換、二體重力、J2 公式與 RK4。J2 尚未接進 RK4，因為 RK4 還沒有傳入絕對 UTC。大氣阻力與 POD 誤差比較也尚未完成。

## 3. 資料來源：已確認的事實

### TLE、OEM、POD 的差別

- `TLE`：兩行平均軌道元素，給 SGP4 用。它是擬合過的簡化描述，不能當精密觀測真值。
- `OEM`：一種軌道檔案格式，不等於精密資料；裡面可能是預報、操作用軌跡或 POD。
- `POD`：由實際量測資料重建的高品質位置與速度序列，才適合當本研究的「觀測軌道」。
- 更原始的 GNSS／測距量測也可以用，但必須自己做軌道決定；目前不走這條路。

### Swarm-A 的正式資料

- 主資料：ESA `SP3ACOM_2_` reduced-dynamic POD。
- 每 10 秒一筆位置與速度，官方另有品質報告。
- 原始座標系是 ITRF，原始時間是 GPS time。
- Kinematic 軌道只做後續比較；主資料不用它，因為主資料已直接提供速度。
- Swarm-A 有可協助理解非重力加速度與大氣阻力的公開科學資料；這是選它的主要優勢。

## 4. 座標、時間與單位：已定案

- 主要座標系：`GCRF`。
- 主要時間：`UTC`。
- 位置：`km`。
- 速度：`km/s`。
- 軌道狀態與 RK4 傳播使用 GCRF。
- Swarm-A 原始 POD 讀入時，必須先處理 GPS time 與 ITRF；不要假裝它原本就是 UTC／GCRF。
- J2、大氣阻力、POD 比較或地面位置需要時，暫時轉到 ITRF；算完加速度後再轉回 GCRF。
- 大氣模型需要經緯度高度時，由 ITRF 再轉成地理座標。
- `RTN` 只用來拆解位置誤差，不作為 RK4 主座標。
- GCRF／ITRF 狀態與向量轉換使用 Astropy，不自行簡化地球旋轉公式。
- Astropy 使用 IERS 資料處理歲差、章動、地球自轉與極移。
- 未來阻力公式中的 `v_rel` 是相對大氣速度，必須扣掉地球自轉造成的大氣速度；不能直接拿 `vx, vy, vz`。

## 5. 軌道反應訊號：已定案

每個原始狀態仍是六維：`[x, y, z, vx, vy, vz]`。

每個時間點先從狀態計算瞬時半長軸：

```text
distance_km = sqrt(x*x + y*y + z*z)
speed_km_s = sqrt(vx*vx + vy*vy + vz*vz)
a_km = 1 / (2 / distance_km - speed_km_s*speed_km_s / MU)
```

不使用近日點、遠日點或「第幾圈」切分。Swarm-A 軌道接近圓形，這些切點不穩定。

正式做法是「往回看一整圈」的滑動平均：

- `instantaneous_a_km[t]`：當下六維狀態算出的半長軸。
- `a_mean_km[t]`：從 `t - 約 90 分鐘` 到 `t` 的半長軸平均。
- `a_dot_km_s[t]`：`a_mean_km` 隨時間的變化率。

選擇往回平均而不是前後各半圈，因為置中平均會用到未來資料，會讓後續延遲分析看起來比真實反應更早。

最前面不足一整圈的點沒有平均值與導數，應保留為 `None`，不要硬補數字。

`a_dot_km_s < 0` 代表軌道正在縮小。軌道能量變化率可作為數學一致性檢查，但目前不是主分析量，暫不保存。

目前程式假設資料固定間隔；真實 POD 若不規則，之後要改成按時間權重平均，不能直接照目前的「點數平均」。

## 6. 地磁與太陽資料：已定案

- `SYM-H(t)`：主要地磁暴強度訊號。
- `d(SYM-H)/dt`：由原始 SYM-H 直接算出，不另外下載一欄。
- `AE(t)`：補充極區活動。
- `F10.7(t)`：太陽背景活動。
- `F10.7A(t)`：F10.7 的 81 日平均；不是 `F81`。
- Dst 可作為較長時間尺度的輔助資料，非主訊號。

軌道反應和太空天氣資料需要對到相同 UTC 時間點；目前假資料剛好都是四分鐘一筆，所以用精確時間對齊。

## 7. 大氣阻力與 GPR：概念已確認，尚未實作

阻力加速度：

```text
a_drag = -0.5 * Cd * A / m * rho * |v_rel| * v_rel
```

- NRLMSIS 2.0 的密度是基準：`rho_MSIS`。
- 真正要使用的密度：`rho_corr = rho_MSIS * C_rho`。
- 為了保證倍率是正的，GPR 預測 `y = log(C_rho)`，再取 `C_rho = exp(y)`。

關鍵限制：POD 只告訴我們軌道如何掉，不會直接告訴我們真正密度。因此 `C_rho` 必須先透過「以物理傳播結果配對 POD」反推，之後才是 GPR 的訓練標籤。

## 8. 高頻資料與平滑窗口的討論

- 114 小時平滑窗口遠大於想找的 1 到 6 小時延遲，會抹掉訊號，也可能製造假的時間偏移；不可用。
- 本專案目前採用約 90 分鐘的一圈 trailing 平均，不是 114 小時。
- Swarm-A 的主資料採用 Reduced-dynamic 解；它同時有位置與速度，較適合用來算半長軸。
- 高頻取樣不代表導數一定較準；必須比較平滑窗口，例如 30、60、90、150 分鐘，看結果是否穩定。
- 2.5 小時雖比 114 小時合理，仍可能削弱一小時尺度的訊號。

## 9. 資料保存與目前資料狀態

原則：

- 真實來源資料只保存原始檔，不在 `data/` 覆寫或混入清理後結果。
- 清理、對齊、平均等衍生結果先在記憶體中算；正式要輸出時另行決定格式與位置。
- 假資料可保存，但檔名必須以 `synthetic_` 開頭，並永遠不可作為研究證據。

目前 `data/` 只有假資料：

- `synthetic_iss_orbit.csv`：舊的假軌道測試資料。檔名暫時不改，避免改動前期程式；它不是 Swarm-A 資料。
- `synthetic_space_weather.csv`：同一時間軸、每四分鐘一筆，共 2520 筆。第 24 小時起為假地磁暴，約第 30 到 36 小時最強；故意做成約六小時後才出現假的軌道反應。

這兩檔只驗證資料流程，不代表 Swarm-A 真實歷史，不可做科學結論。

## 10. 已刪除或刻意不保留的資料

舊的 ISS TLE 與暫時操作軌跡已移除；它們不屬於 Swarm-A 的正式 POD 資料。

也不保留主套件內的驗證腳本與 Python cache。

## 11. 現有程式結構

```text
satellite_orbit/
  down_swarm_pod.py                 下載 Swarm-A POD 原始檔
  load_swarm_pod.py                 讀取本機 Swarm-A POD ZIP
  calc_coordinates.py              GCRF／ITRF 狀態與向量轉換
  calc_forces.py                    二體重力、J2 公式與狀態導數
  calc_integrator.py                fourth-order Runge-Kutta（RK4）傳播
  calc_orbital_response.py          計算 a、滑動一圈平均、a_dot
data/
  synthetic_iss_orbit.csv
  synthetic_space_weather.csv
README.md
AGENTS.md
TIMELOG.md
```

目前最小流程已用假資料跑通：

```text
讀取 synthetic orbit
-> calculate_orbital_response
-> 讀取 synthetic space weather
-> align_orbit_and_weather
-> 2497 個具有 a_mean 的對齊資料列
```

RK4 是目前唯一保留的數值積分器。Euler step 原本只為比較 RK4 與 Euler 而存在，現在已移除。也已移除 `make_derivative` 這類函式內函式的寫法。

## 12. 目前需要注意的檔案

- 太空天氣 loader 尚未用到，已移除；加入大氣阻力模型時再重新設計。
- 舊的 CSV、ISS OEM 與 reboost 讀取程式已移除。

## 13. Git

- 2026-09-15：建立本機 Git repository。
- 第一個提交應包含目前可用的程式、假資料、研究決策與時間日誌。
- 2026-09-15：已建立私有 GitHub repository：`https://github.com/anbychang/science_project`。
- `master` 已連到 `origin/master`，目前提交已推送至 GitHub。

## 14. 下一步，尚未做

1. 將 Swarm-A 原始資料的 GPS time 轉成 UTC，再呼叫 ITRF／GCRF 轉換。
2. 讓 RK4 使用絕對 UTC，把 J2 加速度接進狀態導數。
3. 用官方 POD 當答案，測量目前傳播器的 XYZ 與 RTN 誤差。
4. 再加入大氣阻力與太空天氣資料。

官方 POD 只作為起始狀態與答案；不能把未來 POD 偷放進傳播器修正預測。

## 多 chat 協作規則

當同一件工作由多個 chat 同時處理時：

```text
主 chat：討論方向、做最後決策
工作 chat：執行一個明確的小任務
TIMELOG.md：共同的決策與目前事實
Git：每次完成後保存版本
```

- 只能有一個主 chat 負責最後決策。
- 不同 chat 不可同時修改同一個檔案。
- 重要決策只寫進 `TIMELOG.md`，不要只留在聊天裡。
- 完成一件事就 commit；下一個 chat 開始前先讀 `TIMELOG.md` 與最新 Git 狀態。
- 需要交接時，只傳「做了什麼、改了什麼、下一步是什麼」的短摘要，不轉貼整段聊天。
