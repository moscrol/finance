# docs/capability-switchboard

## 这个分支做什么

两份设计稿 + 实现：

- `docs/superpowers/specs/2026-08-22-capability-switchboard-design.md` —— 工具/核验/提示词零件的并列开关板，独立 runner 做「默认盒 ± 一颗」消融。
- `docs/superpowers/specs/2026-08-22-domain-predicate-coupling-design.md` —— 领域谓词（双红/单红/开根加权…）的原件+复印件打成一个 id。

两族同一张表、不同 prefix。**开关板是消融夹具，不是运行期 feature flag**：拧动只发生在 runner 的 composition root，生产路径永远不读开关板。

## 当前状态

树 `/Users/a77/fwp-wt-capability-switchboard` @ `1289f110`，已 rebase 到 `gitea/main@b4689295`。未推、未合 main。

对照树：`/Users/a77/fwp-wt-code-map-land`（干净 `main@b4689295`）。不要和主仓 `feat/reading-rules-baseline-batch1` 并。

### 质量棘轮（2026-08-22）

验收口径：**默认空集合时，模型看见的层相对当前主链不能退步。** 「拧得动」是下一层；离线 43 绿只证明关得掉。

脚本：`scripts/align_default_box_quality.py`
题：`episode_seam_ladder_cases.json` 三道，`as_of=2026-08-07`
库：主仓 `db/market_feature_store.duckdb`（worktree 没有 `db/`，不设 `MARKET_FEATURE_STORE_DB` 预取会空，对打必须 `--db`）

**已跑：aligned=true，gaps=[]**

| 项 | 值 |
|---|---|
| 宪法 | 4420 字，sha `773fcf4cfcb57023` |
| 双红 SQL | `pct_chg > 0 AND diff_ratio > 10 AND amount > 500` |
| 双红个数 | 08-05=154 / 08-06=11 / 08-07=32 |
| next-session-index | `market_forecast`，预取「双红个数序列」`0ebfc4614e8f8d05` |
| current-mainline | `market_watch` + dated_market_review，prefetch=[] |
| weekly-market-cause | `market_cause`，prefetch=[] |

设计收紧（NULL 成交额、字符串/`True` 边界、开根 `GREATEST`）**没在这 3 题表面上露出来**，不要拿对照树去「修齐」它们。

Live 答案字符串：本会话环境无 LLM key，**fail-closed**。表面对齐 ≠ 答案对齐；同一模型连跑两次也会漂，不能当解耦验收。有 key 再双 sidecar（不同 port + `--repo-root`）。

### 审查回修（2026-08-22，对照 spec 验收后）

1. **三处 f 前缀贴反**：`evolution/strategy4.py` / `backfill_strategy3_touch_matrix.py` / `render_strategy4_dual_engine_matrix.py` 写成普通三引号 + `GROUP BY 1f`，DuckDB 吃到字面 `{DOUBLE_RED_SQL}`。已改成 `f"""… GROUP BY 1"""`。
2. **HEAD 锚改钉 `4e0c6bf5`**：门禁自检、路由 parity、noop 的 loop 文件守卫不再跟本分支 HEAD 走。提交后「改前 ≥4 hit」仍对着旧正文。
3. **没接到缝的算数面退出实验臂**：`single-red` / `volume-surge-10` / `mainup-consecutive-3` / `limit-approx-9p8` 不进 `arm_ids`、不进 `wired_predicate_ids`。`capacity-top3` / `sqrt-weighted` / `limit-heat-min2` 只保留说明书面（`has_arithmetic=False`）。
4. **开根正典接到日报和 agent**：`daily_review` 走 `weighted_strength_sql(别名)`，`adapters/market.py` 走 `WEIGHTED_STRENGTH_SQL`。列名只接受 ident，防以后把用户输入塞进片段。

**两份稿子的步骤全部执行完 ✅**（开关板 4/4，谓词 5/5 含第 2.5 步）

### 谓词第 3 步：声明的每一面共一 id

`intelligence/services/predicate_faces.py` —— 一个谓词 id 统辖它声明的面（三面是上限不是定额）：

| 面 | 关掉后 | 谁有 |
|---|---|---|
| 算数 | `counts_double_red()` → False，预取不报个数 | double-red 等有算数的 |
| 说明书 | 宪法里它名下的行不注入 | double-red / capacity-top3 / sqrt-weighted / limit-heat-min2 |
| 路由 | 词表摘掉它名下的专有词，**其余词一个不少** | double-red（「双红」）；dated-market-topic（整张词表） |

正控是**声明的每一面都要变**，不是「三面都要变」。说明书用真宪法正文验，不造样例。

接线：`ContextVar` + `using()`。runner 在 composition root 包住 `adapter.handle`；prefetch / dated-topic / `load_methodology` 读 `faces()`。生产不写 → 空集合 → 与本模块不存在时一致。loop 不加产品 if。

**§7.2 漂移测试已加**：`foresight_methodology.md` 里手抄的那条 SQL 必须等于 `DOUBLE_RED_SQL` 当前字面。第一期允许宪法仍是人维护的复印件，但改了正典忘了改宪法 → 这条红（模型读的是宪法不是 signals，两者不一致模型背的就是过期口径）。

`OWNERSHIP` 已登记本底全部可拧谓词（含 dated-market-topic 的路由面）。没登记的 id runner 仍报 `not_implemented`，不是空过。

### 谓词第 2 步：单红 / 开根正典（NULL 口径已定）

**用户 2026-08-22 定：成交额缺失既不算单红也不算双红。** 另两种写法各自隐含一个没依据的假设（「没抓到≈量不大」/「没抓到≈量大」）。

| 收口前 | 收口后 |
|---|---|
| 日报 SQL：`(amount <= 500 OR amount IS NULL)` → NULL 算单红 | `SINGLE_RED_SQL`（`NULL <= 500` 求值为 NULL，天然不成立） |
| `ask_blocks:677`：`(amt is None or amt > 500)` → NULL 算双红，贴「真正双红」 | 调正典；NULL 单独一支「量价状态待确认（成交额缺失）」 |
| `adapters-design.md:429`：漏了 `pct_chg > 0` | 补上 + 指向正典 |

⚠ `ask_blocks` 那处不能只改成正典就完事：改完它会**滑到下一支「弱放量修复」**，那句话隐含「量不大」，同样是把不确定说成确定。所以加了显式的待确认分支。

**开根加权**：`WEIGHTED_STRENGTH_SQL` + `weighted_strength()`，amount 单位=**亿元**。缺值返 `None` 不返 `0`（返 0 会把「不知道」排成「中性」，同一条纪律）。

⚠ **稿子 §3.5「D 是亿元再开根、A 与 D 量纲不可比」是错的，已更正**：`daily_review:616` 那个 `amount_yi` 只是 `max(amount) AS amount_yi` 的别名，同一列同一单位；四个变体读的都是 `fact_sector_stock_daily.amount`（样例 3.9 / 1.81，本来就是亿）。真正差别只在空值/负值怎么挡。

**影响面实测**：库里 84 行 `amount` 为空，但同时满足「涨>0 且 边际量>10 且 amount 空」的是 **0 行**。单红计数 60 个交易日 **2631 → 2631**。**代码分歧是真的，数据分歧是空的**——所以它不会自己暴露，哪天数据源改口径才会炸，且没有测试会红。

## ⚠ 第 2.5 步偏离了稿子的字面，理由写在这

附录 E 写「单一真本源 `MARKET_TOPIC_TERMS` **生成**六处」。**照字面做会改掉路由**——那几处的外延是故意不同的，且差异在源码注释里写明是有意为之：

| 处 | 收「板块」 | 为什么 |
|---|---|---|
| `query_understanding._DATED_MARKET_TOPIC_RE` | **不收** | 注释原文：收了会把 theme-research 的问题抢走，over-routing 比 under-routing 更难发现 |
| `evidence_capabilities._MARKET_SUBJECT_MARKERS` | **收** | 主体词，命中后 `mainline_context` 才有意义 |

并成一张单子就是**削齐**，正是谓词稿 §9-C 拒绝的失败形状的镜像（那条讲不该各写各的，这条讲不该强行合并本来就该不同的判据）。

真正的漂移风险在**词汇层**不在列表层：「主线」在四处各写一遍字面，改一处写法时没人知道另外三处也要改。

所以实际做法是 **`intelligence/services/market_topic_terms.py` 共享词汇表 + 各处自己组合外延**。收口四处：`query_understanding` / `answer_orchestrator` / `evidence_capabilities` / `task_frame`。`route_table.JUDGMENT_REQUEST_PATTERN`（展望/研判词）与 `turn_controller._FINANCE_PATTERN`（泛金融分道，含题材/财报/公司）是**第三、第四个不同判据**，未并入。

parity 断言的是「每一处仍等于它改前那一份」（AST 从 `git show HEAD:` 取字面比对），外加一条**不许削齐**的守卫：`板块` 必须在 `_MARKET_SUBJECT_MARKERS` 里、且必须不在 `DATED_MARKET_TOPIC` 里。

**新增（5）**

| 文件 | 是什么 |
|---|---|
| `intelligence/eval/fixtures/capability_switchboard.json` | 种子表 27 行（12 capability + 1 composer + 2 verifier + 12 predicate） |
| `intelligence/services/capability_switchboard.py` | 读表 / 按 id 解析（fail closed）/ 实验臂资格 |
| `scripts/check_double_red_copies.py` | 双红复印件门禁，三形状，CLI 退出码 0/1 |
| `scripts/diff_predicate_impls.py` | 两份实现的差分（真实数据 + 类型空间两趟） |
| `scripts/run_capability_switchboard.py` | **开关板 runner**：默认盒 ± 一颗，正控/负控/底盘三判据 |
| `scripts/verify_double_red_parity.py` | §10-8 行为对照（旧模块从 `git show HEAD:` 取，不重打） |
| `scripts/generate_default_switch_box.py` | `default-v1` 生成器 + `--check` 再生一致 |
| `intelligence/eval/fixtures/switch_box_default_v1.json` | 冻结默认盒 |
| `intelligence/tests/test_capability_switchboard.py` | 27 条 |

**改了三个生产模块（第 1 步收口）**

| 文件 | 改动 |
|---|---|
| `market_feature_store/signals.py` | 提出 `DOUBLE_RED_PCT_MIN/DIFF_MIN/AMOUNT_MIN`；`DOUBLE_RED_SQL` 与 `DOUBLE_RED_DESCRIPTION` **由常量生成**；新增行形状入口 `is_double_red_row(row)` |
| `intelligence/services/theme_lifecycle_timeline.py` | 删掉自己那三个 float；`is_double_red(row)` 改成薄包装委托正典；两处展示串改引正典常量 |
| `intelligence/services/asof_prefetch.py` | 常量与判定改从 `signals` 引（不再从 timeline）；模块 docstring 更正 |

`switch_set="seed"`，**不是 `default-v1`**——那是开关板第 2 步的生成物。

## 已验证

`4e0c6bf5`（工作区脏）：

- **513 passed** —— 全部引用 signals/timeline/asof_prefetch/双红的测试（19 个文件）
- `test_capability_switchboard.py` **21 passed**
- `scripts/layer_audit.py` **ERROR 0 条**（新模块落 services/；timeline→market_feature_store 是允许方向）
- `test_episode_seam_ladder.py` **49 passed**（梯子无回归）
- 复印件门禁基线 **16 处 / 11 文件**，收口前后不变（timeline/asof_prefetch 用的是具名常量，本来就不在字面基线里）

### 第 1 步的差分收据（切 import 之前跑的）

`scripts/diff_predicate_impls.py double-red --db …/market_feature_store.duckdb --limit 300000`

- **真实数据：扫 102,572 行，判定不同 0 行。** 列类型分布 `float/float/float` 100,345 ｜ `float/None/float` 2,223 ｜ `None/None/float` 4。**没有 Decimal、没有字符串**——所以 DB 路径切过去零风险。
- **类型空间：11 例，判定不同 4 例**（正典严格收窄）：

| 输入 | 收口前（复印件） | 收口后（正典） |
|---|---|---|
| 字符串数值 `"1.5"/"12"/"900"` | True | **False** |
| 字符串 amount 单列 `"501"` | True | **False** |
| `True` 当 1.0 | True | **False** |
| 空字符串 | **raise** | **False** |

四例都是「翻紧」，且真实库一条都碰不到。已在 `test_timeline_wrapper_delegates_and_keeps_no_thresholds` 钉住。

**这就是为什么「现有测试仍绿」不能当判据**：绿只说明测试没覆盖那四类输入，不说明没有输入会翻转。

### 开关板第 1 步：runner 读数（3 题 × 22 颗）

`python3 scripts/run_capability_switchboard.py --all-arms`

**通过 14 ｜ 设计不可满足 5 ｜ 本题不适用 20 ｜ 未接线 24 ｜ 失败 0**

结局分四种，别压成通过/失败两种——压了就会把三类完全不同的情况都读成「关不动」：

| 结局 | 含义 |
|---|---|
| ✅ passed | 正控（schema 差集恰好这一颗）+ 负控（硬调被拒）+ 底盘跑完，三条齐 |
| ⊘ designed_unsatisfiable | 该题证据计划把这颗列为 mandatory，关了合同不合法。**非失败，也非「关得动」的证据** |
| – inactive_on_case | 这颗不在本题**解算面**里，关它是空操作。授权面逐 frame 解算，A 题可测 B 题不可测是常态 |
| · not_implemented | runner 拧不动（`followup-composer` 在 conversation_orchestrator；谓词未接面时也走这条，不是空过） |

已证「关得住」的 6 颗（weekly-market-cause）：`mainline_context` / `finance_query` / `kb_search` / `evidence_search` / `web_search` / `semantic-verifier`。

### 谓词稿 §10-8 行为对照（第 2 步之前必须先有这个）

`python3 scripts/verify_double_red_parity.py --db …` → **✅ 五项零差异**

| 项 | 改前 | 改后 |
|---|---|---|
| 判定逐行（102,656 行） | — | 判定不同 **0** |
| 🔥 标记数 | 6651 | **6651** |
| 预取口径串 | — | 一致 |
| 预取双红个数（20 个交易日） | — | 不同 **0** |
| 时间线阶段段落（固态电池/信创/人形机器人） | 20/28/19 段 | **逐段相同** |

「改前」用 `git show HEAD:` 把旧模块原样加载，不重打旧逻辑——重打比的是「我记得的旧逻辑」。旧 `asof_prefetch` 要引旧 `timeline` 的三个常量，加载时临时影子化再还原。

⚠ 这个脚本第一版在自己文件里重打了 🔥 那句内联，被 `check_double_red_copies.py` 抓住——**抓得对，验证工具豁免自己就是给门禁开的第一个后门**。改成从 HEAD 原文按结构定位（`cell = f"🔥…"` 的前一行 `if`）取出来 eval，本文件里一个阈值都不出现。

### 开关板第 2 步：`default-v1`

`scripts/generate_default_switch_box.py` 生成，`--check` 比字节。**冻的是函数不是名单**：只冻 (1) 授权面派生函数符号 + (2) 非工具行取值；12 颗 capability 只记名字（`ambient_ids`），取值靠每次 run 的 `resolved_capabilities`。

两条边界踩过坑，已钉进测试：
- **welded 要进盒子**（`structural-verifier` 关不掉但生产里开着——盒子描述「怎么拨的」，不是「哪些拧得动」）。按 `status=="active"` 过滤会把它漏掉。
- **`canonical != exists` 的不进**（`predicate.single-red` 之流没有正典，记成 `on` 等于放一个没有对应物的状态位）。排除项自述理由，否则「短了几行」和「本来就这么多」在下游长得一样。

派生链符号被改名 → 生成失败，而不是产出一个指向不存在符号的 `capability_source`。

### 开关板第 3 步：`noop-prompt` 零行为零件

挂在**已有的** `GLMAgentRuntime(client=...)` 注入缝外面（`NoopPromptClient` 装饰器），所以 `agent_episode` / `continuous_turn_adapter` / 梯子 / `Profile` / `episode_tools` **一行没改**——这条用 `git diff --name-only HEAD` 断言，不靠眼睛看（往 loop 里塞个 `if` 同样能让零件「生效」，但那证明的是反面：缝不存在，是现凿的）。

正控是「那段说明书**真的进了模型的消息流**」，且对照臂里没有，两边都看。不是「没崩」——零行为零件天然不会让底盘崩。

全臂回归（3 题 × 23 颗）：**通过 17 ｜ 设计不可满足 5 ｜ 本题不适用 20 ｜ 未接线 24 ｜ 失败 0**。

⚠ `--all-arms` 曾经无脑给每颗发 `off`，于是 `noop-prompt`（默认就是 off）两臂完全相同、正控必不过，报 3 个假失败。现在按**背离默认**的方向拧。**「把每颗都关一次」不等于「把每颗都拧一次」——默认 off 的那些，拧的方向是 on。**

**负控的观测点在 `traces` 不在 `trace_steps`**：拒绝记为 `ProviderTrace(provider="episode:tool_gate", capability=<工具名>, detail="unknown_or_unauthorized_tool")`（`agent_episode.py:395-411` → `continuous_turn_adapter.py:1083`）。第一版去翻 `trace_steps`，捞不到任何东西，于是负控整片报「未拒绝」——**观测点找错，读数长得和真失败一模一样**。

## 未验证 / 已知边界

- 默认盒**表面**已与当前主链对齐；**答案字符串未 live**（本会话无 LLM key，fail-closed）。A/B 零数据。离线 scripted 臂已跑过，不代替线上，也不代替表面棘轮。
- 门禁只覆盖**字面**三形状。具名常量的第二实现由 `test_double_red_thresholds_are_defined_in_exactly_one_module` 管。`daily_review` 🔥 图例已改引用 `DOUBLE_RED_DESCRIPTION`。
- `dual_blind` 弱口径只改名不改公式（历史 verdict 可复现）：`pct>0 AND diff>0`，不得再叫双红。
- 附录 E 刻意 4/6：`route_table` / `turn_controller` 不并入词表，不许削齐。

## 收尾批（四件全部完成）

**1. evolution / 矩阵第二批：门禁基线 10 处 → 0 处。** 生产代码里的双红字面复印件**全部清零**。
- 可执行 SQL 7 处改引 `DOUBLE_RED_SQL`（转 f-string 前先验过块内无其它花括号）
- `render_sw_l1` 内联三分类改调 `is_double_red` / `is_single_red`（它的单红原本就是 (c) 口径）
- 两处 **docstring 散文**改成指向正典而不是复述公式——散文也是复印件，只是门禁抓它的方式是「让它别再写公式」
- 测试基线改成**空集合**：不是「还没查」，是棘轮从此只减不增的起点

**2. `daily_review` 图例散文**：改为 `"…（" + DOUBLE_RED_DESCRIPTION + "）"`。这是三形状门禁抓不到的那一类，靠引用消除。

**3. 其余谓词接面 → 9 个全接上。** 但改了模型，理由见下。

**4. `boards-min` 改判为 `param.boards-min`（kind=parameter）。**

### ⚠ 「三面」是上限不是定额——正控改成「声明几面验几面」

稿子的口号是「算数 + 说明书 + 路由共一 id」。实测只有 `double-red` 三面俱全：

| 谓词 | 面 |
|---|---|
| `double-red` | 算数 + 说明书 + 路由 |
| `capacity-top3` / `sqrt-weighted` / `limit-heat-min2` | 算数 + 说明书（路由里没有它们的专属词） |
| `single-red` / `volume-surge-10` / `mainup-consecutive-3` / `limit-approx-9p8` | 只有算数 |
| `dated-market-topic` | **只有路由**——它就是那一面本身 |

硬要三面会把两面的判成失败，那是**判据错不是开关坏**。跟路由词表同形：外延本来不同，不许为了整齐划一削齐。

说明书那一面用**真的宪法正文**验（`foresight_methodology.md`），不自造样例——造样例只能证明过滤函数会过滤，证明不了它过滤得到真正注入模型的那几行。

### ⚠ `boards-min` 不是谓词，是参数

`scrape.py:61 min_boards = 3`（抓取侧默认，可 `--min-boards` 覆盖）vs `cli.py:1217/1224 --min-boards default=2`（入库侧默认）——**两个阶段各自的 argparse 默认值**，不是同一判据的两份复印件。「统一成一个数」是错的 move。

但**默认值不一致是真的**：抓取只抓 ≥3，入库却接受 ≥2，库里永远不会有 2 板行，入库那个默认是死的。这是配置一致性问题，已记进表的 notes，不进实验臂。

生成器也补了一条：`kind == "parameter"` 不进默认盒——CLI 参数默认值不是「开关位」，放进去会让人以为拨它就能改行为。

## 历史遗留（下面这些是执行过程中的记录，不是待办）

0. **runner 第一版有过两处空过，改法记下来免得重犯**：`predicate.*` 和 `followup-composer` 的正控被写成无条件 True，于是 7 颗没接线的开关顶着 ✅ 混进读数——正是稿子自己批评的「全绿却什么都没证明」。现在它们报 `not_implemented`。**给一颗开关记 ✅ 之前，先问它的关法有没有真的接在 composition root 上。**

1. **`ask_blocks` 的 NULL 已与单红同口径**：缺成交额两边都不算，单独一支「量价状态待确认」。不要再把不确定说成确定。
2. 开关板第 1 步 runner、第 2 步 `default-v1`、第 3 步 `noop-prompt` 已落地。
3. 谓词第 1–3 步（含跨生产缝的 contextvar 注入）已落地。说明书验真宪法，不造样例。
4. 第 2.5 步是共享原子不是削齐六处。别把 `route_table` / `turn_controller` 并进 `DATED_MARKET_TOPIC`。

## 踩过的坑

- **绝对计数会漂**：稿子里一版写过「不带 `-U` 41 文件、带 `-U` 47」，复测得 49→51（tracked-only 50）。对账一律用不变量——差集里有没有生产文件、文件集合等不等。
- **单行 `rg` 那条 SQL 在 `daily_review.py` 上命中 0 处**，而那文件有 4 处（3 跨行 + 1 内联）。`test_gate_self_check_on_daily_review` 钉的就是这个。
- **字面搜索按标识符名找，变量名改短就漏**：`ask_blocks.py` / `market_analogs.py` 两处生产复印件是人工 `rg diff_ratio` 那轮漏掉的，第 0 步跑门禁才抓到。
- **手维护的文件 allowlist 会变成下一份复印件**。门禁豁免一律用目录规则（`research/market-hypothesis/_scripts`、`intelligence/tests`）。
- 解释器用主树 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，本树没有自己的 venv。DuckDB 只读连接跑差分，不写。
