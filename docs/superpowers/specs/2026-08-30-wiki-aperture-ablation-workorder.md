# 2026-08-30 Wiki 闭环三铲对照评测工单

> 可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
> 形态已定：**评测 + 评测专用旋钮**，默认行为与现网逐字节一致。否定结论（三铲不优于一铲）也算合格交付。

## 背景与动机

生产 W 源不是「搜一轮 hybrid 就结束」。`collect_wiki_rag` 外套 `retrieve_closed_loop`：预算够时按 **narrow → broad → counter** 各铲再调一次 hybrid（一铲内第一句有货即停，最多换 3 句）。词面闸和语义闸是分桶之后的过滤器，**不是这三铲**。

截至 2026-08-30：

- 三铲对照**没有**质量评测。单测只钉接线、空结果换句、预算跳过。
- 线上常见后两铲被跳过：`broad/counter skipped: remaining budget below observed query cost`（例：`intelligence/eval/runs/20260826T101858Z-quality-ablation.json` 基线臂）。那种 run **不能**拿来回答「三铲好不好」——后两铲没跑。
- 语义闸（`evidence_judge`）另有消融：`20260826T101858Z-quality-ablation.json`，关 `ASK_EVIDENCE_JUDGE` 边际贡献 **+2.8/20**。本单**不重复**那道闸，闸跨臂必须钉死同一状态。

本单只回答：**在预热完成、三铲都实际跑完的前提下，多铲是否比只收窄更好。** 预算不够的样本整题作废，不编进「三铲更差/更好」。

## 目标

1. 评测专用旋钮 `ASK_WIKI_APERTURES=narrow|narrow_broad|all`（未设 = `all` = 现状）。生产默认路径零行为变化。
2. 两层读数，分开写、禁止混成一个分数：
   - **L0 激活**：预热后，`all` 臂三铲均 `executed=True` 且无 `budget_exhausted`。
   - **L1 检索**：结论桶页集合、反方桶是否非空、后铲是否贡献了收窄没有的页。
   - **L2 答案**：复用质量消融盲评（五维 0–4，总分 /20），只评 L0 通过的题。
3. 报告预注册结论（上线 / 不上线 / 仅检索有增益答案无增益），附原始 JSON。台账取号登记。

## 非目标（写死认领）

- ❌ 不评 knowledge-base CLI 默认 agentic vs ask 的 hybrid（另一条默认，已有 40 题页排行评测）。
- ❌ 不重评 rerank、入度加权、PRF（已有否决表）。
- ❌ 不重评语义闸开关（已有 +2.8；本单闸状态跨臂固定）。
- ❌ 不改 ask 默认、不切生产、不合 `main`。
- ❌ 不用 2026-07-22 冻结 as_of 复现那次「W 全空 + 后铲被跳」当本单主证据——那是新鲜度/预算事故，不是三铲消融。
- ❌ 不把 G/R/L、盘面 D 块差记成 W 三铲差。L2 若做，须在报告里拆「W 页变了」vs「答案分变了」。
- ❌ 不把词面闸/语义闸改成代码规则闸。

## 先分清：三铲 ≠ 闸

| 名字 | 是什么 | 谁判 |
|---|---|---|
| 三铲（本单变量） | 换问法再 hybrid：收窄 / 放宽 / 反方 | 代码调度；每铲内部仍是 hybrid |
| 词面闸 | 标题+摘录是否含问句/锚词（含中文二字） | **纯代码** `_hit_overlaps_terms` |
| 语义闸 | 字叠了但说的是不是这题 | **LLM** `evidence_judge.judge_relevance`，失败 fail-open |

语义闸怎么判（执行方勿改口径）：

- 输入：用户原问 + 结论桶与反方桶的 `(title, excerpt)`，最多 16 条，编号 0..n。
- 模型只输出 `{"keep": [编号], "reason": "一句"}`，不改写正文。提示写明：主体/主题须一致；「支撑位」vs「基本面支撑」不算相关；**拿不准就留**。
- 温度 0。可走独立 `LLM_JUDGE_*`。
- **fail-open**（`verdict is None` 或未开闸）：桶原样不动。触发：`ASK_EVIDENCE_JUDGE=off`、`auto` 且无钥匙、超时、空响应、JSON 不合法、deadline 已过。
- 成功才把未 keep 的挪进 `discarded` 并记 warning。不是结构门（那种只核哈希/格/白名单）。

本单跨臂钉：`ASK_EVIDENCE_JUDGE` 同一值（建议 `off`，把变量只留给三铲；若开闸须三臂都开，并在报告声明「闸与三铲纠缠」）。

## 证据路径（先读，勿臆测）

| 文件 | 看什么 |
|---|---|
| `intelligence/services/closed_loop_retrieval.py` | `retrieve_closed_loop`、`_run_aperture`、`_narrow_queries` / `_broad_queries` / `_counter_queries`、`_bucket_hits`、`_hit_overlaps_terms`、预算跳过 |
| `intelligence/services/evidence_providers.py` `collect_wiki_rag` / `_apply_semantic_judge` | W 入口；语义闸 fail-open |
| `intelligence/services/evidence_judge.py` | 闸提示词与 `None` 返回 |
| `intelligence/services/kb_rag.py` `prewarm` / `_RESULT_CACHE` | 启动预热；缓存 key 含问句，三铲问句不同不串 |
| `intelligence/api/app.py` lifespan `kb_rag.prewarm` | 工作台启动预热 |
| `scripts/run_quality_ablation.py` | L2 盲评/聚合数学，**复用勿重造** |
| `intelligence/eval/runs/20260826T101858Z-quality-ablation.json` | 语义闸边际 +2.8；亦见后铲 skipped（反面教材） |
| `intelligence/tests/test_closed_loop_retrieval.py` | 接线夹具，旋钮单测往这里加 |

## 预注册：臂、激活、指标、否决

### 臂（单变量 = 跑哪几铲）

| 臂 | `ASK_WIKI_APERTURES` | 含义 |
|---|---|---|
| A0 | `narrow` | 只收窄 |
| A1 | `narrow_broad` | 收窄 + 放宽 |
| A2 | `all`（或未设） | 收窄 + 放宽 + 反方 = 现网 |

其余钉死：`wiki_rag_mode=hybrid`、结构版索引、同一 `as_of`（**当日最新导出/交易日**，禁止再用 2026-07-22）、同一 `ASK_EVIDENCE_JUDGE`、预热后再跑、关 wiki 结果缓存或每臂独立 `cache_scope`（禁止 A0 命中污染 A2）。

### L0 激活（过不了不准谈 L2）

对每道题的 A2：

- `attempts` 里 narrow / broad / counter 各至少一次 `executed=True`
- 无 `status=budget_exhausted`
- 预热已跑：`kb_rag.prewarm(...)` 成功，或工作台已 ready 且本进程复用热 worker

任一题 A2 未激活 → 该题 `usable=false`，不进 L1 增益均值、不进 L2。  
**可用题 < 4 → 整单停在 L0，结论写成「现网预算撑不满三铲，质量对照无资格」，不要发明「三铲无用」。**

建议墙钟：单题 wiki 阶段 ≥ 90s（模块 `MAX_TOTAL_SECONDS`），总回合再留合成余量。CLI 须把 timeout 传到 `retrieve_closed_loop` 的 `total_seconds`，勿只加进程墙钟。

### L1 检索（主指标，不看作文）

每题、每臂从 `ClosedLoopRetrievalResult` 取：

- `C` = 结论桶 `page_id` 去重集合
- `K` = 反方桶 `page_id` 去重集合
- `discarded` 只记账，不当命中

预注册：

1. **后铲增量**（A2 vs A0）：`|C_A2 − C_A0|` 与 `|K_A2 − K_A0|`。报均值。不设「必须更大才合格」——增量 0 也是合法结论。
2. **反方是否出现**：A2 的 `\|K\|≥1` 的题数 / 可用题数。A0 允许为 0（收窄不问反方词）。
3. **污染**：A2 结论桶相对 A0 **少掉**的页（后铲把户主挤出窗）。若平均 `|C_A0 − C_A2| > |C_A2 − C_A0|`，报告必须写「后铲挤窗」，不得只报增量。

可选：给 4～6 题手写 `expected_pages`（wiki `page_id`，如 `concepts/液冷`、`entities/申菱环境`）。有标注的题加 hit@6（结论桶 ∪ 进证据链的 W 页）。**无标注不得用标题模糊匹配冒充 recall。**

### L2 答案（次指标，仅 L0 可用题）

- 题集最低 6 道，必须是 **W 能说话的题**，禁止再拿「只谈大盘、W 全空」当主干。建议：
  - 液冷服务器现在处于什么阶段
  - 申菱环境液冷订单落地了没有
  - 英维克和液冷管路的关系
  - 玻璃基板和陶瓷基板的区别（多面，放宽可能有用）
  - 科创50支撑位在哪（语义闸经典脏页；本单若关闸，只作检索污染观察）
  - 再加 1 道实体+概念（如中际旭创 / 1.6T）
- 跑法抄 `run_quality_ablation.py`：真模型写稿、盲评、洗牌、解析失败 = unscored。
- 主比较：A2 − A0 的 `marginal_contribution_total`（与现脚本同一符号：`−mean(ablated−baseline)` 时以 A2 为 baseline、A0 为减铲臂，或写清公式勿反号）。
- **不上线门（预注册）**：可用题 ≥4 且 A2 相对 A0 的盲评总分均值 **低 ≥1.0/20**，且 L1 挤窗成立 → 结论「默认勿吹三铲，考虑默认 narrow 或加预算」。反向：A2 高 ≥1.0 且挤窗不成立 → 「预算够时三铲值得保留」。介于中间 → 「检索有/无增量，答案无显著差，保持现状」。
- 回退题数：逐题 A2 总分低于 A0 超过 **2** 题且可用仅 6 题 → 否决「全面更好」，即使均值略正。

### 延迟（记账，不作上线门）

报 A0/A1/A2 的 wiki 墙钟 p50。三铲更慢是预期。不设「必须 <Xs」。

## 步骤

1. 开工三连：`git status --short && git branch --show-current && git worktree list`。`main` 拉齐后开 `eval/wiki-aperture-ablation`。
2. 取号：`python3 scripts/claim_ledger_id.py claim --branch eval/wiki-aperture-ablation`，写入本单头部与台账行（`EVAL_ONLY`）。
3. 旋钮：`closed_loop_retrieval.retrieve_closed_loop` 读 `ASK_WIKI_APERTURES`，跳过的铲不调用 `retrieve`，`attempts` 记 `executed=False` / `status=disabled`（勿伪装成 `budget_exhausted`）。未设或 `all` 与现网一致。
4. 单测加在 `test_closed_loop_retrieval.py`：`narrow` 只出现 narrow 的 retrieve；默认不设 env 时三铲都调用（对 fake retrieve 计数）。
5. 脚本：`scripts/run_wiki_aperture_ablation.py`（L0+L1 可先独立跑、零合成；L2 复用消融盲评零件）。`--dry-run` 只打印计划。
6. 先 L0：预热 + A2 扫题。可用 <4 则停，写报告「无资格」，不要硬跑 L2 充数。
7. L0 过了再 L1、L2。原始 JSON 落 `intelligence/eval/runs/<utc>-wiki-aperture-ablation.json`（默认不提交大答案正文；报告 md 只留表）。
8. 报告：`docs/verification/2026-08-30-wiki-aperture-ablation.md`（或 eval/ 下短文）：激活率、L1 三张表、L2 均值与逐题、预注册结论四选一。

## 验收

- [ ] 未设 `ASK_WIKI_APERTURES` 时，既有 `test_closed_loop_retrieval` 全绿（默认三铲仍跑）。
- [ ] `narrow` 臂 fake retrieve 次数 = 仅 narrow 查询，无 broad/counter 问句。
- [ ] L0 激活率与每题 `attempts` 写入 JSON；可用 <4 时报告明确「无资格」，无「三铲无用」措辞。
- [ ] L1 含增量、反方出现率、挤窗三项，公式与原始集合可对账。
- [ ] L2 仅含 `usable=true` 题；盲评无臂标签；公式不反号。
- [ ] 结论落在预注册四档之一，并引用本单门限。
- [ ] 台账号已登记；分支推远程；**不合 main**。
- [ ] pathspec 提交；不提交 `.env` / duckdb / 密钥。

## 红线

- 禁 `git add -A`；不合 `main`；不强推。
- 解释器：`.venv-workbench/bin/python`（或仓内规定的 workbench venv）。
- 台账禁手工取号。
- 默认 `all` 必须与旋钮落地前逐字节一致（单测钉调用次数，不要在默认路径加日志噪音）。
- 无 LLM key 不得用模板答案冒充 L2；可只交 L0+L1。
- 禁止把本单改成「顺便把默认改成 agentic / 打开 rerank」。
