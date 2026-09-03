# 设计：路由之后，harness 是地板不是天花板

- 日期：2026-08-21
- 状态：Draft **v1.2**。宪章仍有效。子单 C：PR **#288**（开场预取打 `[E<n>]`）**未合**；其上未提交一刀=问句精确名优先于缩短 subject。树 `/Users/a77/fwp-wt-harness-success-path`（`docs/harness-success-path-spec`，从 `gitea/main@dfc25221`）。**禁止**在主检出 `feat/reading-rules-baseline-batch1` 脏树上改。
- 进度：Gate 0 已过。Gate 1 第一发→子单 C（#288）。Gate 1 第二发分叉=**没投递精确名**（短 subject 抢长口径），扩 C 叠在 `fix/prefetch-evidence-id`，诊断在该树 `docs/verification/2026-08-21-gate1-pcb-exact-name.md`。预取已锚长名；公开稿下一分叉在写稿/判官（主线短名旁路 + 减句绑死问句日数字）。**下一刀只开子单 B 或关发酵题 live 主线，不要并行开 A。** 题面不进正文。
- 父稿：
  - `docs/superpowers/specs/2026-08-20-episode-public-answer-quality-design.md`（P0 传达室 + P1 护栏）
  - `docs/superpowers/specs/2026-08-20-market-cause-sector-routing-design.md`（板块「为什么涨」路由）
  - `docs/superpowers/specs/2026-08-20-asof-prefetch-dual-red-design.md`（问句日预取 + 双红戳）
- 交接（现状，先读再动手）：`docs/handoffs/2026-08-21-episode-answer-hygiene-p1.md`；生产切 + live 四跑读数在 `docs/handoffs/inflight/main.md` 2026-08-21 01:39 行（该行可能尚未合进你检出的 `gitea/main`，以 `/api/health` 为准）。
- 引擎：**A**（`continuous_episode`）。本单不换引擎、不调 T / `_REPAIR_SECONDS_CAP` / 档位 / `_AGENT_FINANCE_QUERY_MAX_ROWS`。
- 对照口径（用户 2026-08-20 纠偏，已落 correction）：质量归因是 **Cursor 分析师工具链 vs Workbench `events[].payload.arguments` / observation**，看第一次分叉。切后 canary、新旧店互比，只能证明洞修没修，不能代替这条对照。P1 live **不要**再开 Cursor 对打；新题型诊断才重新开。

## 0. 一句话

路由之后不要把学徒养成分析师。把分析师会重复做的确定性步骤收成 **harness 拥有的成功路径**（进场投递 + 槽位填数）；限制继续只挡失败路径。限制挡住了成功路径、又没有旁路，才叫 **副作用**，修法是挪层或投递，不是拆帽、不是加提示词、不是给 GLM `run_sql`。

人话：熟手进门前已经称好菜。店把同一盘摆上桌，学徒只炒。25 行帽防学徒端一锅；称菜那一刀不走 25 行。

**判别变量**（验收只锁这些，不锁文笔）：

1. 新题 Cursor 更好时，第一次分叉必须归成三态之一：**没投递 / 禁错了 / 禁对了**。禁止写成「GLM 弱」。
2. 判定为没投递 → 抽成预取或槽位，**限制集合不变**。
3. 判定为禁错了 → 成功路径旁路（预取不受 25；有收据的真话不准改口），帽仍在。
4. 判定为禁对了 → 限制保留，记「店必须继续比分析师严」（as-of、全称断言）。
5. 公开稿数字必须能从桌上的预取行或有收据的工具行读出，不得靠散文发明。

---

## 1. 不要重做（2026-08-21 已成立）

| 层 | 合入 | 生产 | 本单 |
|---|---|---|---|
| 判官投影 C1–C4 | 此前 | 随祖先 | 不做 |
| P0 传达室 T1/T2/T3 | `#282` 族 / `6a54f995` | 在 | 不做 |
| `market_cause` 路由 | `#283` | 在 | 不做 |
| 问句日预取 + 双红戳 | `#284` `48369a31` | 在 | 不做（本单是它的**下一刀收割**，不是重写） |
| P1 Q1/Q3 公开稿护栏 | `#285` `4a1abf79` | **8792=`dfc25221b07b`**（2026-08-21 01:39 切；回滚=`48369a313ff5`） | 不做 |
| P2 Q2 补枪 | 未实施 | — | **`R-20260820-11` 已 `deferred`**（锂矿 live 已含 07-23 +4.4%/628.5 亿）。号不撤 |
| 子单 C 预取行带 E 号 | **#288** `fix/prefetch-evidence-id` @ `33b4ca95` **open** | **未切**（8792 仍 `dfc25221`） | 本宪章第一刀执行结果；合入等用户。账本 `R-20260821-03` `pending` |

Live 四跑（sidecar `:8796`，必须 `POST /api/conversations/{id}/messages`，**禁止** `live_probe ask`）：锂矿 `run_20260821_012059_353272`、铝 `run_20260821_012508_762073`、电网复现 `run_20260821_013054_035436`。`unattempted_claim_count` 全 0，只证了「有收据不改口」。Q1 改口路径与 Q3 减句回退**一次没触发** → `R-20260820-09`/`-10` 保持 `pending`，不得 `confirmed`。

**不要切 8792**，除非用户另拍。不要动脏主检出。

---

## 2. 两套管线（禁止把 25 行当成 RAG 的 k）

Episode 是带工具的 agent，不是「topk + rerank 一条管」。

| 管线 | 工具 | 截断物理 | 典型题 |
|---|---|---|---|
| **非结构化 RAG** | `kb_search` / `evidence_search` | hybrid = BM25 + 向量 + RRF；可 rerank；`kb_search` 现役 **k=6** | 定义、研报、wiki |
| **结构化 SQL** | `finance_query` / `market_data` | DuckDB `WHERE` + `ORDER BY` + Agent 路径 **`LIMIT 25`**（`_AGENT_FINANCE_QUERY_MAX_ROWS`） | 锂矿涨幅、双红、板块归因 |
| **预取** | harness，模型第一轮 tool 之前 | **不受 25 行约束** | 分析师第一刀 |

`contains` 是 SQL 过滤器（`LIKE '%…%'`），不是 rerank。`sector_name contains 锂` 会灌进锂电池/锂电设备。分析师第一刀是 `sector_name='锂矿'`。25 行是上下文护栏，不是检索器。升序 + 25 会砍掉问句日——那是 T1，已修，不要再调大 25 当修复。

预算不够时 RAG 会降成纯 BM25（`select_mode_for_remaining`）。那与 25 无关。

---

## 3. 尺子：成功路径 vs 副作用

生产公式：`Agent = Model + Harness(上下文 + 工具 + 约束 + 验证 + 纠正)`。对齐质量发生在后三项落对层。

每次 Cursor 比店好，只问：**分析师那一招，店是禁止了，还是没投递？**

| 分叉 | 含义 | 动作 |
|---|---|---|
| **没投递** | 确定性 SQL / 派生列 / 时间轴，模型要点才有 | 进场前跑完（BUILD 模式 3：事实投递 > 提醒） |
| **禁错了** | 真话被删、预取了仍报缺能力、声明 1000 实际 25 | 挪层或旁路；帽留下 |
| **禁对了** | 偷看截止日、把截断袋写成全集 | 限制留着；这是店能超过分析师的地方 |

**副作用的定义（本单用语）**：成功路径被 harness 拦住，且没有旁路；失败路径没拦住。拆限制不是默认修复。

已登记的副作用（已修，作反例，勿回归）：

- `freshness` 写死 `current` → 历史题端上今天（#284）
- `ORDER BY trade_date ASC + LIMIT 25` 静默丢掉问句日（P0-T1）
- 资讯 `future_of_cutoff` 静默滤成 0 条（P0-T2）
- 单位标签不一致 → 判官删唯一硬事实（P0-T3 / 铝 43 字）
- 有 capability 收据却改口「未返回」（P1-Q1）
- 语义 repair 塌成残句仍交给用户（P1-Q3）
- schema 广告 `limit.maximum=1000`、执行压 25（已把 schema 生成到 25）

BUILD 对照：事实投递 > 提醒；砍了必须下单前声明；认不出 fail closed；E 号单一发放。

---

## 4. 路由之后五段：限制留在失败路径

路由只决定合同（`market_cause` / `theme_analysis` / `market_forecast` …）。其后：

| 段 | 限制（留） | 成功路径（harness 拥有） | 禁止的「对齐分析师」 |
|---|---|---|---|
| 进场桌 | 上下文预算 | 问句日、精确名、双红戳、（本单要收的）发酵轴 | 提示词「请查双红」 |
| 跟进工具 | 参数化 `finance_query`、无 Shell、25 行 | 只补预取没覆盖的窄问；已知长窗走预取 | `run_sql` / 技能桥挂 tracer |
| 写稿 | 必填格、E 号来自桌上的行 | 槽里的数 = 预取行；模型只写格间句子 | 「写得像研报」无红绿尺 |
| 判官 | as-of、没查过不准写没查到 | 只删已确认坏句；有收据留真话 | 拆判官、调 T |
| 预算 | T、判官 50s | leftover 不够就不派半截 | 配额只写 telemetry |

内置的元能力是 **确定性预取**，不是 **模型可以 exec**。预取是 harness 的 Shell：进程内跑 `is_double_red` / `load_theme_daily_rows`，观察值进 episode。和 Cursor 的差别从「谁拿着 Shell」变成「Shell 在进场前跑完」。

技能桥仍只开只读、无外呼的那一个。`theme-fermentation-tracer` 只读 DuckDB + 知识库，**可以**抽逻辑，**不要**注册成第 13 个工具（模型仍可能不调；与「技能桥刻意只开一个」冲突）。

`reading_baseline` / 视角叙事 **本单不 live**。那是显式开关产品线，不得替代预取或槽位。

---

## 5. 收割循环（本单的主流程，每个子 PR 都跑）

新题必须是设计时 **没用过** 的题面（反过拟合）。已用过、禁止再当设计样本：锂矿发酵到 07-23、08-19 次日研判、07-23 电网/铝为什么涨、低空经济到 07-10、08-12 次日研判、**创新药发酵到 08-07**（#288 夹具）。下一发 Gate 1 **不要写进本 spec 正文**（§8.2）。

```
1. Cursor 侧只写分析师会写的确定性 SQL / tracer（不要用 episode GLM）
2. 店侧同一题：POST /api/conversations/{id}/messages
   （skill_mode=auto；不要 live_probe ask → /api/runs 中立泳道无 continuous-episode）
3. 对 arguments / 预取观察值 / public_answer 三栏，标第一次分叉段
4. 三态归类 → 只开对应子单
5. 子单夹具锁「桌上的行 / 公开稿数字」，不锁文笔
```

对照停在 P1 验收；**新题型诊断必须重新开**。不要 Cursor 对打当 8792 回归。

---

## 6. 子单闸门（一次只开一条）

执行方读完 §1 后 **先做 §10 Gate 0 + Gate 1**。Gate 1 的分叉类型决定开哪条，不要并行开预取和槽位。

### 6.1 子单 A — 发酵轴预取（没投递）

**何时开**：新题第一次分叉在「分析师有消息→首板→双红→补涨时间轴，店用 `contains` + 25 行冒充」或「预取了日频涨幅但没有起涨/补涨分层」。

**做**：把 `skills/theme-fermentation-tracer/scripts/trace.py` 里 **只读、无外呼** 的对齐收进 `asof_prefetch.py` 观察值。盘面函数已在仓内：`theme_lifecycle_timeline.py` 的 `is_double_red` / `load_theme_daily_rows` / `resolve_theme_alias`。双红阈值只许引用这一份，禁止第三份字面量。

观察值至少含（窗口覆盖问句日，精确 `sector_name`，禁止 `contains` 近义名）：

- 逐日：`trade_date, pct_chg, amount, diff_ratio, 双红=是|否`
- 能廉价算则加：该窗内涨停热度（`fact_theme_limit_heat_daily`）或「起涨日 / 补涨日」各 ≤3 个代码+日期
- 消息面只投递 **日期 + 证据层标签**（L1 候选 vs L3），不把研报判断写成硬事实

解析不到板块名 → 观察值写明「未锚定，发酵轴未预取」，fail closed，让模型再走 `finance_query`。不要用模糊名灌满桌子。

**长度帽**：发酵轴预取本身不受 25，但观察值要声明截断（BUILD 模式 4）。建议硬帽：日频 ≤ 窗口交易日数（默认问句日起回 20～30 个交易日，与 #284 一致）；个股名单 ≤ 6。超了声明砍了什么。

**不做**：注册 skill 进 `skill_tools.py`；新 `question_type=fermentation`；调大 25；消息面外呼。

**账本**：建议新号 `R-20260821-01`（发酵轴预取）。`R-20260820-14` 是精确名+双红戳，已接线，不要重复实现；本刀是 **链路对齐**（起涨/补涨/消息日），叠在 14 上。

### 6.2 子单 B — 槽位填数（写稿分叉）

**何时开**：桌上已有问句日数字和双红戳，公开稿仍与 E 号打架，或判断槽数字对不上预取行。低空经济生产稿「连续下跌 vs E1」是已知形状，**不要**用那道熟题当合入闸夹具。

**做**：必填格（判断 / 因果 / 反证 / 边界，以当次 `question_type` 合同为准）的 **数字与日期** 从预取行或带收据的工具行填入；模型只写格间句子。门禁：判断槽出现的涨幅/成交额/双红个数，必须能在预取观察值或 traces 里精确对上。对不上 → 结构缺口，不准用散文圆过去。

仓内已有 grounded composer / `repair_grounded_composer_answer`。本刀是 **让槽消费预取行**，不是新写一套作文模型，不是换 GLM。

**不做**：few-shot 学分析师口吻当主修；改 prompt 抢判官层；锁「像研报」。

**账本**：建议 `R-20260821-02`。

### 6.3 子单 C — 挪约束（禁错了）

**何时开**：分叉证明限制打在成功路径上，且预取/槽位旁路还没有。形状必须可红可绿（有收据的句被改口、预取未计入 mandatory capability）。P1 已覆盖「未尝试声称 / 残稿减句」。不要把文笔差塞进这一单。

---

## 7. 禁止（硬）

- 给 episode 模型 Shell / `run_sql` / 任意 SQL。
- 把质量差写成 GLM 弱，或先换写手当修复。
- 调 `_AGENT_FINANCE_QUERY_MAX_ROWS`、T、`_REPAIR_SECONDS_CAP`、档位（`R-20260816-07`）。
- `git add -A`；在脏主检出改代码；未拍板切 8792；直推 `main`。
- `live_probe ask` 当 P1/本单 episode 验收（中立泳道无 `continuous-episode.json`）。
- 用设计样本题当新收割的合入闸。
- 技能桥扩注册表而不论证只读 + 无外呼。
- 本单范围写「超越分析师的文笔」。超过分析师的是：as-of、双红公式一份、不谎称未查、凌晨口径一致。

---

## 8. 验收

### 8.1 流程（每个子 PR）

1. 干净树从当时 `gitea/main` 长出。`merge-tree` vs `gitea/main` 为 0。
2. 定向 pytest 先红后绿；变异：拿掉投递或旁路必须转红。
3. 新题 live：同一题 Cursor SQL 摘要 vs 店 `arguments` + 预取观察值。第一次分叉不得落在「桌上没有分析师第一刀」。
4. 公开稿数字 ⊆ 桌上的行 ∪ 有收据的工具行。
5. 合入等用户确认。不切 8792 除非用户说切。

### 8.2 反过拟合

合入闸至少 1 道 **未进入本 spec 正文的** 发酵或次日研判题。库里要有真实行。

### 8.3 账本

单测绿 ≠ `confirmed`。无 sidecar / 未走 conversation 入口记 `not_run`。n=1 过不了方差门，保持 `pending` 并写清证了哪半边（P1 四跑的写法照抄）。

---

## 9. 实施顺序

0. **Gate 0 对齐（只读，无 PR）**：`git fetch`；`/api/health` 确认 8792 rev；读 §1 表。已切已 live 的不要重做。解释器：`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。**已完成（2026-08-21）。**
1. **Gate 1 新题第一次分叉（诊断）**：选一道未见过的发酵或次日研判题。分析师侧跑确定性取数；店走 conversation 入口。产出：分叉段 + 三态。**未完成 Gate 1 不得开代码 PR。** 第一发完成（创新药→#288）。第二发完成（精确名被短 subject 挤掉→扩 C，未提交）。**不要复用这两题当下一刀合入闸。**
2. 按三态开 **恰好一个** 子单 A/B/C。先写该子单的失败测试再接线（TDD）。子单 C 已有 #288 + 精确名扩刀。下一刀：**B**（公开稿问句日数字锁 E1）或发酵题 live `mainline_context` 隔离，一次一条。A 仍等 #288 合入。
3. 定向测试 + 该新题 live。账本新号。
4. 用户确认后合。生产切另拍。 **#287（切生产读数）与 #288 都未合**；同改 `docs/prediction-ledger.md`，后合方 rebase。

反向执行的代价：先做槽位再投递发酵轴，槽里填的是 `contains` 杂牌行，门禁会绿在脏数上。先拆 25 再预取，成功路径继续靠学徒点菜，帽失去意义。

---

## 10. 回写

- 子 PR 合入后：日期快照 `docs/handoffs/YYYY-MM-DD-harness-success-path-<slice>.md`；inflight 只留卡点。
- 项目笔记一行：收割了哪一刀、限制集合未改。不要把 live 问句全文抄进 vault。
- 可迁移：成功路径旁路 + 失败路径留帽；SQL 管线不是 RAG topk。写入 `BUILD.md` 仅当换项目仍会犯（收割循环本身会）。

## 11. 给执行 agent 的开场（可原样贴）

读 `docs/superpowers/specs/2026-08-21-harness-success-path-design.md`。P0/路由/预取/P1 已合；8792 已在 `dfc25221`（以 health 为准）；Q2 deferred。不要切 8792、不要动脏主检出、不要 `run_sql`、不要调 25。先 Gate 1 新题分叉，再只开一条子单。Live 走 `POST /api/conversations/{id}/messages`。
