# Data Lineage 寫作規則

## 目的與優先序

這份文件規範 `data_lineage/` 的格式與資料契約，不取代根目錄的 `AGENTS.md`。
讀者是本專案的開發者：要一眼看出「哪個資料結構 -> 做什麼 -> 哪個資料結構」。
可讀性優先，其次才是精簡；不要解釋讀者已知道的專案背景。

Lineage 只保留不能從程式表面看出的研究選擇：資料座標、數學 estimator、必要邊界
與科學限制。不要寫函式控制流程、SQL、顯而易見欄位、繪圖樣式或逐行實作。

```text
AGENTS.md
  -> repository-wide rules
RULES.md
  -> data-lineage writing and data-contract rules
README.md
  -> project and lineage entry points
```

## 固定格式

每個步驟依序呈現：標題與狀態、動作、Input、Output。
三者各用獨立的 `text` code block；不增設固定的驗證／限制欄。
P1.5 沿用 Phase plan 的連續編號（目前為 P1.5.1--P1.5.6）；不用 P1.5a／b／c 或 P1.51／52／53。

沒有輸出時寫 `尚未執行`，不捏造 Output。實際排版如下（三個 code block，順序不可交換；數值僅示範格式，正式範例須核對來源）：

#### [P1.5.1] raw POD -> mean elements [done]

```text
prep_04_mean_orbit.py -> write_mean_orbit_elements()

P1.3 可用 state -> ITRF -> GCRF -> Brouwer-Lyddane -> mean elements
```

```text
swarm_a_states (raw; ITRF；欄位節錄)
[
  {
    time_us: 1688173252000000 (us),
    x_m: -6.225e6 (m),
    source_id: 3459
  },
  ...
]
```

```text
swarm_a_mean_orbit_elements_v1 (derived；欄位節錄)
[
  {
    time_us: 1688173252000000 (us),
    mean_semi_major_axis_m: 6.859e6 (m),
    mean_eccentricity: 8.822e-4,
    mean_inclination_rad: 1.527e0 (rad)
  },
  ...
]
```

此例 `time_us` 是 2023-07-01T01:00:52Z 的 POD epoch；輸出沿用同一 key。

一份文件的 SQLite 路徑在開頭寫一次，並交代 checkpoint 與 working copy 的關係。每節只寫來源 table 與輸出 table；不要重貼路徑。先給一步的動作，再給它的 Input，最後給 Output，讓讀者順著讀。

只寫實際參與該步的資料結構；不要把整個 database 塞進每個 Input。相同 row 後續可以用 table 名與 key 引用，不必整筆重貼。若重貼，數值與欄位必須一致。

### 動作

第一行列真正執行的檔案與函式。
資料轉換用 `來源 -> 處理 -> 結果`；`ITRF -> GCRF`、`GPS -> UTC` 直接這樣寫。
必要的篩選、缺口、chunk 與品質門檻用短句寫清楚。
不要把演算法條件藏在 Input／Output 的括號裡，也不要為了中文而中文。

若研究意義取決於數學選擇，只寫最小充分定義：座標與主要式子。不要逐項翻譯
程式變數或重述 loop。

### Input 與 Output

兩者使用同一格式：檔案或 table 名在 `{}` 外，`{}` 只代表一筆具名 record，`[]` 代表多筆同類 record。
每個 field 一行，後面直接放示例數值；不另設 `fields` 與 `example` 區塊。
若只列部分欄位，明寫「欄位節錄」，不可讓人誤認是完整結構。

上面的排版是格式示意，不是要每節複製同一筆資料。正式範例的數值必須能用 database path、table 與 key 查回；raw file 也須能核對。不要以推測值冒充實際 row。資料結構列出該步的主欄位，不用文字逐欄解釋，也不必標重要性。

單位寫在數值後的括號中，如 `density: 3.200e-12 (kg/m^3)`。無單位就不寫任何單位標示，也不要寫 `(無單位)`。浮點數用科學記號、尾數小數三位；不要加 `~` 或約等於。`time_us`、ID、計數保留原整數。這只是顯示精度，運算仍用資料庫原值。

`time_us` 必須有實際整數值。
它的 UTC 時間與語意（觀測時刻、bin 結束、orbit 結束、day start 等）在該步附近說明一次。
`raw`／`derived`、frame、time system、algorithm version 只在相關處標示。
Input 與 Output 要能看出 key 如何延續或改變。

輸出仍是 SQLite table 時，table 名與 `(derived)` 寫在大括號外。
`database`、`table`、`row`、`kind` 不是實際欄位，不得放進 row。
必要的 selection 與方法參數放在動作區塊，不假裝是 source table 的欄位。

## 程式函式的 Input / Output

修改 lineage writer、loader 或 calculation code 時，每個 function 都要有短 docstring：

```text
Input: {source_table, time_us, ...}
Output: {derived_table, row_count, ...}
```

Input / Output 要寫資料 shape、單位或 side effect (適用時)，不是重述函式名稱。
資料在 function 間傳遞時使用單一 state shape；不可把 time、position、velocity 拆成互不關聯的參數。

## `{}`、`[]`、`()` 的固定語意

Lineage 內的 bracket 不是裝飾。每個 data shape 必須依下列定義書寫。

```text
{
  field: value,
}
```

`{}` 表示一筆具名 record / mapping。

- field 名稱是 key，不靠位置解讀。
- 未列出的 required field 不應被假定存在。
- optional 條件在 shape 前後說明；不要把 `?` 當成實際欄位名稱。
- 一個 orbit state 固定使用一個 `{}` record。

```text
[
  item_1,
  item_2,
  ...,
]
```

`[]` 表示零筆或多筆同類 item 的 collection。

- table output 的 `[]` 是多列 record；不自動表示 row order，排序、key 與 time semantics 必須另寫。
- orbit series 的 `[]` 是 time-ordered state sequence。
- 欄位清單若使用 `[]`，只列 schema field，不表示 runtime data value；Output 應直接用具名欄位及值。

```text
(supplementary scope, exception, or provenance)
```

`()` 在 prose 中只放補充資訊；在數值後專門表示單位。

- 主結論不放進 `()`。
- 會改變 acceptance、資料選擇、物理意義或科學主張的條件，必須寫在正文或品質門檻。
- math 中的 `()` 只做運算分組。
- data shape 不使用 positional tuple；若資料必須依位置解讀，改成 `{named_field: value}`。

## Markdown 與 data shape

- 主句先寫決定、狀態、限制或結果。
- 補充資訊放在 `(小括號)`；會改變結論的限制留在正文。
- 一個句子若同時含兩個獨立條件、結果或決定，拆成兩句或 list。
- `{}`、`[]`、`()` 的 data shape 必須多行縮排。
- 每個 section 的 Input / Output shape 要遵守本文件的 bracket semantics。
- 一個 field 一行；不可把 schema 壓成一行長句。
- 只在 section、段落、list、code block 或語意轉折時換行。
- 同一個短段落維持連續文字；不要把每一句或一句中的片語各拆一行。
- 空白行只分隔獨立段落或 block；不要用連續空白行製造層次。
- 句子過長才在自然語意處換行；不要留下難以掃讀的超長行。
- 不使用 emoji、裝飾性圖示或重複解釋圖表的散文。
- 文件使用 Traditional Chinese；技術名、table、field、file、unit 與 code 保持 English。

## 資料與 table contract

```text
raw files
  -> raw SQLite tables (immutable)
  -> derived tables (separate, reproducible)
  -> analysis / audit outputs
```

- Raw SQLite tables 是 source record；不可 `UPDATE` 或 `DELETE` raw observation。
- 計算只可寫自己的 derived table；以原始 `time_us` 或明確記錄的 derived key 追溯來源。
- 不可覆寫 legacy table；新算法建立 versioned table。
- 每個 derived table 要保留 `algorithm_version`。
- 有上游資料缺口時，不可補值、內插或跨越缺口，除非該步驟的 contract 明確允許且記錄方法。
- `chunk_id` 的語意必須在每個 estimator 個別說明；不可假設它永遠是分組鍵或永遠可跨越。
- 所有 internal physics unit 使用 SI：m、m/s、m/s^2、s、rad、kg、m^2、kg/m^3。
- 時間使用 UTC；SQLite key 使用 `time_us`。

## Phase 1 目前 contract

- P1.5.2 的 10-minute bin 與 P1.5.3 的 3h / 6h / 12h backward rate 不可跨 `chunk_id`。
- orbit-average estimator 必須自行記錄 `chunk_id` 的語意與實際 time-gap rule。
- Weather source time 不可晚於 orbit time。
- SYM-H 非 exact observation 時，僅允許左右觀測總間距 <= 120 seconds 的內插。
- Density 不進 Phase 1 core analysis。

## 版本、證據與狀態

每個結果都標示其中一種狀態：

```text
[done]       verified output exists and has recorded validation
[working]    derived output exists but remains under active analysis
[paused]     intentionally not progressing
[not created] no output exists
[deferred]   outside the current phase
[retained]   historical or recovery artifact; not current input
```

單筆範例須可用 database path、table name 與 key 查回原 row；不必在每段重貼驗證 query。
Row count、UTC coverage 等整體統計要能追溯至 audit metadata。
只有真的呈現整體統計時，才在附近交代資料範圍。沒有查過的數值不能當成實際範例。

## 科學主張界線

- 「可追溯」不等於「已校準」或「可做因果宣稱」。
- 候選 decay、storm window、density comparison 必須標示為 descriptive，直到 maneuver、source 與 method anomaly 校準完成。
- 不可把去除週期項、smooth、fit 或 filter 寫成「真實衰減」的證據。
- 資料源、frame、force model 或 product version 改變時，必須記錄其影響範圍。
- 外部論文方法要區分：原文直接使用的步驟、本專案的實作選擇、尚未驗證的推論。

## 更新 lineage 時的完成條件

更新前：

```text
read current lineage
  -> inspect actual database schema and metadata
  -> verify row count and UTC coverage
  -> identify raw / derived write boundary
```

更新後：

```text
標題與狀態 -> 動作 block -> Input block -> Output block
  -> table/file 在 {} 外；每筆 row 是一個 {}
  -> 數值後才標單位；無單位不標；浮點範例三位小數科學記號
  -> time_us、來源 key、UTC 語意可追溯
  -> 研究界線與狀態明確；README 連結有效
```

對照實際檔案、table 與 writer 再修改；不可只修一個被指出的句子，必須掃過同類步驟。若改變算法、selection filter、schema 或主張界線，也要更新相鄰的 lineage section。
