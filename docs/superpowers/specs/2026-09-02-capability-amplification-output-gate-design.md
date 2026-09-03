# 设计：能力放大与输出硬层——放开输入侧、守住来源与出处、把弃权率纳入读数

日期：2026-09-02
状态：**P0a / P0b / §3.6 两项（守门 + `web_fetch`）/ §4 两个诊断字段 已实施于本分支（2026-09-03），P1–P4 与全部 live 读数未做。** 分支 `spec/capability-amplification-output-gate`，树 `/Users/a77/fwp-wt-capability-amplification`，基线 `gitea/main@daea04a0`。**未提交、未推、未开 PR、8792 未切。**
收据：`docs/verification/2026-09-02-capability-amplification.md`（同分支，与代码一起未提交）
修订：2026-09-03——§3.5 对照源重核（pi / dsh 均有子代理与沙箱，但都是挂在钩子上的插件；09-02 版「两家都没有」的负面断言撤回）、P4 主臂改 `sdk_glm`、§1.3 补工具窗口一层、新增 P0b 与 §3.6。同日实施后回写：§1.3 第二层升 [实测]（F10 live 探针）、§1.3 第一层的授权集有产物实证、§3.6 第 8 条首跑读数 3 个裸契约（见 §8）。

父稿：

- `docs/superpowers/specs/2026-09-02-research-harness-loop-decouple-design.md`（§4 表第 11 行：`admit_finish` 是终局准入，pi / dsh 两家都没有；本稿把它确立为**唯一**硬层）
- 2026-08-27 四臂对照读数（组件臂 vs react vs 8792 vs 8796，噪声底与门槛）
- 2026-08-28 react round2（F1 / F2 / F3 三个失败家族）

用户裁决（2026-09-02 口述，本稿的立稿前提）：

> 「输入层的契约其实不是硬性指标。最硬的一层是输出要带证据索引、置信度要高。其他要放大能力——如果一些题目都回答不了，只能回答最简单最基础的，根本没有产品竞争力，也没有使用价值。」

---

## 0. 一句话

**把硬层从输入侧移到输出侧**：入口放开（谁都可以供数），出口收紧（每一句话要能指到出处）。

五刀，按性价比排：P0 补一条被漏掉的授权（P0a）并给 `financial_data` 开报告期参数（P0b）、P1 把弃权率提成一等读数、P2 判官判据从「来源白名单」改成「出处可追溯」、P3 沙箱按 `derived_calculation` 落地、P4 跑 `sdk_glm` 底座 A/B（`sdk_gpt` 为可选第三臂）。外加 §3.6：把 knevo 用得上的工具**形状**抄过来，契约自己写。

**P0a 是一行改动 + 一个已知真值的回归用例；P0b 是一个参数 + 一条能到 2024 年报的测试；P4 主臂是一个环境变量 + 一次对照跑；P2 是唯一有风险的一刀，必须先量后改。**

**本稿不含任何 loop 移植。** 「换底座才有元能力」不成立——pi / dsh 的子代理与沙箱都是挂在钩子上的插件，不在循环里（§3.5.1）；knevo 的工具多半没用上，是契约没做，不是底座差（§1.4、§3.6）。要抄的是工具形状，契约与账本是我们的。

---

## 1. 为什么现在做

### 1.1 最严的输入契约在分布外归零 [实测 2026-08-27]

四臂 38 题，未见题（D 组 10 道，避开 `run_component_arm.py:classify_handler` 的字面 token）均通过率：

| 臂 | 未见题均通过率 | 弃权 |
|---|---|---|
| react | 85.7 | — |
| 8796 | 59.5 | — |
| 8792 | 56.7 | — |
| **组件臂** | **11.1** | **10/10 全弃权** |

组件臂在**见过的 28 题上 0 弃权**、未见的 10 题**全弃权**，完全分离。当时的结论是「它不是天花板，是小抄」。

**可迁移的读法**：输入侧契约越硬，分布内越准、分布外越接近零。产品价值分布在分布外。

### 1.2 `produces` 声明自带「不可复验」警告 [实测]

`intelligence/services/research_tool_registry.py` 的 `finance_query` 条目注释原文：

> ⚠️ 可复现性：证据来自 `~/tmp` 和 `~/agent-memory/.foresight` 下的 `continuous-episode.json`（gitignored、随清理消失）。观测时（2026-08-06）全部 45 份存在且可读，但**这不可在 CI 里复验**。

`ToolSpec.produces` 是观察归纳出的软约定，不是可门禁的契约。本稿不删它（它给检索规划提供先验），但**不把它当硬指标**。

### 1.3 茅台题的根因：一行授权，加一层工具窗口 [实测，本轮定位]

2026-09-02 P2''-live 两臂同题「2024年贵州茅台营业总收入是多少亿元？」，真值 **1741.44 亿元**。

两臂完整工具序列（`finance-base-ab/out/reference-loop-0902b/`）：

```
Episode 臂：   kb_search✗ → financial_data✓ → l3_lookup✗ → evidence_lookup✗   （4 次）
参考 loop 臂： financial_data✓ → l3_lookup✓ → kb_search✗ → evidence_search✗ → kb_search✗   （5 次）
```

**两臂 9 次调用，零次 `web_search`。**

链路：

| 层 | 值 | 位置 |
|---|---|---|
| question_type | `financial_analysis` | `episode.json` `diagnostics.question_type` |
| → 证据策略 | `company_financial_evidence` | `intelligence/services/task_frame.py:43` |
| → 能力下限 | `market_data / financial_data / kb_search / evidence_lookup / l3_lookup` | `intelligence/services/evidence_capabilities.py:146-152` |

**`company_financial_evidence` 是 `_RUNTIME_CAPABILITY_FLOOR`（`evidence_capabilities.py:95`）20 条策略里唯一被排除 `web_search` 的公司类证据策略。**

20 条里不含 `web_search` 的共 5 条，另外 4 条都是本地盘面/技术面策略，排除 web 是对的：

| 策略 | 含 web_search | 性质 |
|---|---|---|
| `current_a_share_market` | ✗ | 本地盘面 |
| `dated_a_share_market` | ✗ | 本地盘面 |
| `current_market_scenarios` | ✗ | 本地盘面 |
| `structured_market_technical` | ✗ | 本地技术面 |
| **`company_financial_evidence`** | **✗** | **公司研究——异类** |
| `company_multi_layer_evidence` | ✓ | 公司研究 |
| `company_valuation_evidence` | ✓ | 公司研究 |
| `event_and_official_evidence` | ✓ | 公司研究 |
| `current_fact_evidence` | ✓ | 公司研究 |
| `comparable_multi_source_evidence` | ✓ | 公司研究 |
| `claim_verification_evidence` | ✓ | 公司研究 |

它的五个同类兄弟全都有 `web_search`。这一条没有，而它恰好管「某公司某期财报数字」。

**注意不是全局缺失**：`evidence_capabilities.py:552` 有 `floor = ("kb_search", "web_search") if frame_requires_retrieval else ()`，web 在别处是默认授权。所以这是**单条策略的遗漏**，不是设计取向。但也要看清合成规则（`:550-565`）：策略在表里时授权集 = 策略 floor ∪ 计划需求，**不会**回落到 `:552` 那条通用默认——所以这一行漏了就是真漏，不是别处兜着。

**根因的第二层：工具面，不止授权** [实测 2026-09-03：F10 `600519.SH` `pageSize=8` 第 7 行 `2024年报 REPORT_DATE=2024-12-31 NOTICE_DATE=2025-04-03 TOTALOPERATEREVE=1741.44 亿`，第 3 行 2025年报 1720.54 / -1.20 与 E7 逐字一致]

授权那一行解释的是「为什么没走 web」，不是「为什么拿不到 1741.44」。第二个问题的答案在 `financial_data` 自己身上：

- `episode_tools.py:1056-1079` 的 `financial_data_runner` **不读模型传的 `_query`**（形参名就叫 `_query`），固定按 `subject_query` 取 `DEFAULT_PERIODS = 6`（`market_financials.py:36`）个报告期。
- 2026-09-02 往前数 6 期是 2026 中报 → 2025 一季报；**2024 年报是第 7 期，刚好在窗外。** 模型拿到的是 2025 年报 1720.54 与同比 -1.2%（E7），倒推出 1741——`episode.json` 里那个答案就是这么来的。
- 而 D7 链（东财 F10 → 新浪利润表 → AKShare）含的正是 knevo 去 fetch 的那个新浪源。**数在我们的一手链里，工具没把它递给模型。**

所以茅台题有两个修法，性质不同：走 web（P0a）拿到的是二手材料，`web_search` 的工具契约（`research_tool_registry.py:975`）自己就写着「不能直接当作公司级硬事实……写成待验证线索」；给 `financial_data` 开报告期参数（P0b）拿到的是一手证据、带披露日 as_of，直接过 §2 和判官。**P0b 才是这一类题（某公司某期财报数字）的通解，P0a 是补授权。**

### 1.4 对照组：knevo 赢在走了 web，不在数据源 [实测 2026-09-02]

同题，knevo 派 `finance-researcher` 子代理跑了 22 次工具，给出 1741.44 亿元。其调用底账里：

- `finance_statement` → **不可用（无 provider 支持）**
- `finance_graph_context`（贵州茅台/白酒/飞天茅台，hops=2）→ **entity_not_found**
- `finance_shareholders`（600519）→ **失败**
- `finance_search_data` ×7 → **每次 `providers=["web"]`**
- 最终数字来自 `web_fetch` 新浪财经财务指标页 + 中新网报道 + 多轮 web 收窄

其 `finance_provider_status` 原始返回的 `ready` 仅 `datasvc / polymarket / web`——**研报/纪要线（gangtise）不在其中**。

**结论：他的数据面不比我们深。他赢在这道题上走了 web，而我们的两条 loop 因 §1.3 那一行拿不到 web 授权。**

再拆一层，他赢的机制是三件，都不是「工具名多」：

| 机制 | knevo | 我们 |
|---|---|---|
| 取页 | `web_fetch` 拉新浪指标页全文 | **无 `web_fetch`**；`web_search` 只回 5 条 × 160 字符 snippet（`agent_research.py:609-619`），无取页 |
| 调用预算 | 22 次 | 4 次，其中 `l3_lookup` / `evidence_lookup` 两次 `zero_grant: true`（`episode.json` `dispatch_grants`，`timeout_configured: 75.0`） |
| 隔离 | `finance-researcher` 子代理把失败的调用圈在外面 | 无子代理 |

反过来，他那些**没用上**的工具——`finance_statement` 无 provider、`finance_graph_context` 对「贵州茅台」`entity_not_found`、`finance_shareholders` 失败——不是能力差，是**工具调用契约没做**：工具挂在菜单上，底下没源或没实体解析，模型试了才知道。这正是我们做得比他好的那一层（`_TOOL_CONTRACTS` 把「查不到 ≠ 不存在」写进每个工具；`ProviderTrace` 分 success / empty / error；注册表只挂 `authorized_specs`）。**所以他的工具形状可以抄，契约由我们写——见 §3.6。**（用户裁决 2026-09-03。）

同时记下口径差：他把新浪财经 + 中新网当证据发了 1741.44；我们的参考 loop **点名了 1741.44 并拒绝断言**（原文：「因此精确到小数位的数字（如1741.44亿）不能作为已核实事实引用」）。真值确为 1741.44。**正确但无用。**

---

## 2. 分层原则：形状契约软，来源契约硬

这两类东西长得像，本稿把它们明确分开。**放开的是前者，绝不放开后者。**

| | 形状契约 | 来源契约 |
|---|---|---|
| 管什么 | 这个工具产出什么证据类型、参数长什么样、覆盖面怎么声明 | 每条进入答案的事实的 `hash` / `as_of` / `source` |
| 例子 | `ToolSpec.produces`、`query_parameters()`、`_RUNTIME_CAPABILITY_FLOOR` 的策略划分 | `EvidenceLedger` 的哈希铸造、`admit_finish` 的绑定校验 |
| 谁消费 | 检索规划（先验，帮模型选工具） | **输出门**（`ResearchHarness.admit_finish`，`research_harness.py:479`） |
| 本稿态度 | **软**。可以放宽、可以缺、缺了不阻塞 | **硬**。任何新入口都必须铸出这三样，否则不许进证据体系 |
| 违反的后果 | 模型多走一跳弯路 | **输出门没东西可绑 → 「输出带证据索引」直接落空** |

**判据一句话**：放开的是「我不管你从哪来、长什么样」，守住的是「你得能说清你是谁、什么时候的」。

这条分界决定了 P3（沙箱）的形状：沙箱的**输入侧不设形状契约**（爱写什么代码写什么代码），但**产物必须携带输入证据的哈希列表 + 脚本本身**，否则它算出来的数进不了答案。

---

## 3. 五刀

### 3.1 P0：`web_search` 进 `company_financial_evidence`（P0a）+ `financial_data` 开报告期（P0b）

#### 3.1.1 P0a：补授权

**改动**：`intelligence/services/evidence_capabilities.py:146-152` 的元组加一项 `"web_search"`。

**为什么是安全的**：floor 只是**授权**，不是强制调用——`web_search` 作为 overlay 需求时 `mandatory=False`（`_OVERLAY_REQUIREMENT_TEMPLATE`，`:244-247`，`"web_search": ("WEB", False, "current")`；`:209` 的 `_PLAN_CAPABILITY_TO_RUNTIME` 只是名字映射，不带该标志）。同类五条策略已全部含它，没有一条因此劣化。

**静态断言要走合成函数，不要断言字面量**：`runtime_capabilities_for_frame()`（`:539-565`）的授权集 = 策略 floor ∪ 计划需求。测试应构造茅台题的 `TaskFrame`（`question_type=financial_analysis`）调这个函数，断言改前 `web_search` 不在、改后在。这同时把 §1.3「授权集里没有 web」从静态推断钉成实测（现有产物无法区分，见 §4）。

**必须同时钉的负向断言**：加了授权不等于必然调用。验收要分开两个读数——**授权集含 `web_search`**（静态断言）与**该题实际调用了 `web_search`**（live 读数）。只钉前者是假门禁。

**预期结果要老实**：`web_search` 的工具契约（`research_tool_registry.py:975`）写死「网页是二手材料……只有网页来源时写成待验证线索」，判官按 tier 处理 `public_web`。所以 P0a 单独落地，最可能的 live 结果是**第三种**：web 拿到 1741.44，但正文只能写「待验证线索」——「正确但无用」原样复现。这不算 P0a 失败（授权目标达成），但说明「把 1741.44 当事实写出来」这一步依赖 P0b（一手证据）或 P2（判据改）。验收按三分法记（§5 第 4 条）。

#### 3.1.2 P0b：`financial_data` 读报告期

**改动**：`episode_tools.py:1056` 的 `financial_data_runner` 读 `_query`（或 frame）里的年份 / 报告期，把传给 D7 链的 `periods` 放宽到覆盖该期（`financials_block_for_target` 本来就收 `periods`；年份词表 `_HISTORICAL_MARKERS` 在 `evidence_capabilities.py:89` 已有），或直接传目标报告期。产物 `as_of` = 该期披露日，不是抓取日。

**为什么这是通解**：「某公司某期财报数字」这一类题，答案在一手链里的概率远高于在 160 字符 snippet 里；一手产物过 §2 的来源契约与判官，web 产物过不了。P0a 修的是这道题的授权，P0b 修的是这一类题。这也是 §3.6 第三条契约（「模型传的参数会被读」）在现役工具上的第一次兑现。

**回归用例（真值已知，可机器判）**：

| 题 | 真值 | 现状 | 期望 |
|---|---|---|---|
| 2024年贵州茅台营业总收入是多少亿元？ | 1741.44 亿元 | 两臂均给反推数 1741，参考 loop 明确拒绝断言小数位 | P0b：`financial_data` 产物含 2024-12-31 报告期行、数值 1741.44、`source` 为 D7 链之一、`as_of` 为披露日；P0a：授权集含 `web_search` 且至少一臂实际调用 |

**成本**：P0a 一行 + 一条测试；P0b 一个参数 + 一条测试。**这是五刀里唯一今天就能有 live 读数的。**

### 3.2 P1：弃权率提成一等读数

**问题**：现有评测（`scripts/run_quality_ablation.py`，`aggregate_components()` 为聚合单一真本源）读的是通过率与五维 rubric 分。**一个 100% 弃权的系统零错误、分数不难看、产品价值为零**——组件臂 11.1 分背后正是 10/10 弃权。

**改动**：

1. `run_quality_ablation.py` 的逐题记录增加 `abstained: bool` 与 `abstain_reason`（枚举：`evidence_gap` / `unsupported` / `judge_blocked` / `deadline_exhausted` / `other`）。
2. `aggregate_components()` 输出增加 `abstain_rate`，与均分并列，**不合并进总分**（一票否决式的二值量不折进连续分——见 `10_knowledge/veto-inside-a-continuous-score.md` 的教训）。
3. 报告模板要求两个数一起念：「均分 X / 弃权率 Y%」。单念任一个都不许。

**先做基线**：改完先在现有冻结题集（knevo28 + D 组 10）上重跑一次拿弃权率基线，**不改任何行为**。没有基线就没法判断 P0/P2/P3 是不是把弃权率压下去了。

**注意方差纪律**：弃权是二值量，比连续分更抖。沿用 `10_knowledge/eval-harness-variance-governance.md` 的做法——**塞一组两臂本该完全相同的样本当噪声底**，弃权率的门槛从那组现算，不套连续分的 `|Δ|≳2.4/20`。

> **状态（2026-09-03）**：三条改动已落（`intelligence/eval/abstention.py` + `run_quality_ablation.py` 逐题字段 / `abstention` 聚合块 / 报告「均分 X / 弃权率 Y%」并列；`rejudge_quality_ablation.py` 经同一份 `aggregate_components` 自动带上），钉子 21 条、变异两组见红。**基线已从 08-27 四臂 38 题产物回溯算出**（`docs/verification/2026-09-03-abstain-rate-baseline-offline.md`）：组件臂未见题 10/10 复现；生产臂该答的 32 题弃 8，其中 7 道是判官不可用扣稿（`judge_blocked`），模型自弃 1 道。**两个修正写进本节**：(a) `run_quality_ablation.py` 走的是 `intelligence.cli ask` 的 legacy 管线，不经过 ContinuousAgentEpisode——P0/P2/P3 改的是 episode 链，所以「P0 有没有压下弃权率」要在含 #537 的快照上经会话链重跑 38 题、用 `classify_episode` 判，消融壳的弃权率量的是 legacy 路径各组件；(b) 判官可用性是协变量，重跑前先看 `judge_unavailable_count`。38 题会话链重跑烧配额，待用户。

### 3.3 P2：判官判据从「来源白名单」改成「出处可追溯」

**这是五刀里唯一有风险的一刀。**

**问题**：`intelligence/services/episode_semantic_verifier.py`（4,793 行）的删句判据偏向「这个来源在不在我的分层里」。能力放大之后，新进来的来源它不认识，会整片删。前科两条：

- 2026-08-21：判官**删了 65% 真话**，修复后 B 臂零删句、31/31 数字有出处。
- 2026-09-02 茅台题：参考 loop 知道 1741.44 却拒绝断言。

**能力越多 → 不认识的来源越多 → 删得越狠 → 读数反而更差。** 这是 P0/P3 的直接对冲力量，不处理它，前面两刀白做。

**目标判据**：一句话可留，当且仅当它**指得到一条带 `hash` / `as_of` / `source` 的证据**，且证据与句子的语义绑定成立。**不再问这个 source 属于哪一档**。来源分档降级为**置信度标注**（写进正文的限定语），不再是**删除权**。

**这正好是 `10_knowledge/severity-demotion-moves-the-decision-downstream.md` 的反向应用**：把「删除」降级成「标注」，决定权交给读者而不是判官——**但前提是展示层真的把标注展示出来**。这条必须一起验，否则就是那条记忆警告的原形（降 severity 后展示层没下限 → 发空白答卷的镜像：发无标注的低档证据）。

**纪律：先量后改。** 顺序写死：

1. 先在**不改判据**的前提下，给判官的每次删句记一条结构化事件：`deleted_sentence` / `reason` / `bound_evidence_ids` / `source_tier`。
2. 跑现有题集，统计**因「来源档次不够」被删**的句子里，有多少是**有出处的真话**。
3. 这个数 ≥ 某个阈值（建议 10%，实测后定）才动判据。**低于阈值说明判官没在过度删，改它是白冒风险。**

**不做**：不抬 judge 窗口（`LEFTOVER_WINDOW_ISSUE` 处「不要靠再抬窗口罩尾部」的约束保持）。

> **状态（2026-09-03）**：第 1 步已落——`SemanticEpisodeOutcome.sentence_verdicts`（私有产物 `semantic_verifier.sentence_verdicts`），
> 每条拒句记 `stage`（preflight / judge）、`judge_round`、`sentence`、`decision`（**deleted / demoted_to_issue**）、`reasons`
> （judge / novel_numeric_condition / calendar_weekday / path_trend / unresolved_evidence_ordinal）、`judge_issues`（点到该句的判官原话）、
> `cited_evidence_ordinals` / `unresolved_evidence_ordinals` / `bound_evidence_hashes` / `source_tiers`。判据零改动，钉子 6 条、变异
> 「降级误记删除」2 红。读侧 `scripts/offline_judge_verdict_census.py` 算第 2 步的占比；对生产 814 个历史 run 报「不可判」（字段刚有），
> 第 2 步要等切流后积累。**本轮 live 发现修正本节前提**：当前判官对 `public_web` 不是「整片删」——腾讯题 5 条 `public_web` 证据全部绑定发布，
> 4 条 issue 全是**降级标注**（`decision=demoted_to_issue` 那一类，V8 语义降级已把「必需槽内的语义拒句」改成只记 issue），
> 见 `docs/verification/2026-09-03-web-chain-two-arm-live.md` §3。所以第 2 步要数的是两个数：`deleted` 里有出处的占比（判据是否过严），
> 以及 `demoted` 里低档来源的条数（标注是否被展示层吃掉——§3.3 那条「前提是展示层真的把标注展示出来」）。

### 3.4 P3：沙箱按 `derived_calculation` 落地

**定位**：这一刀**不修任何已量出的缺陷**。react 1.000 vs 8792 0.357、茅台题——全是取数类题，沙箱一个都不修。它开的是一类目前**完全答不了**的题：DCF/敏感性、回测、统计检验、跨源口径核对。**是能力扩张，不是修复。**

因此：**不要指望它抬现有读数**，现有冻结题集是机器可判的取数类，沙箱在上面测不出信号。要衡量它得**另冻一组计算类题**。

**协议**：

- 新增 produces 类型 `derived_calculation`。
- 产物**强制携带**：`input_evidence_hashes: tuple[str, ...]`（本回合已绑定证据的哈希）+ `script: str`（原样脚本）+ `as_of`。
- **`as_of` 从输入继承，取最旧的那一条**——不是运行日期。（反例：knevo 的演示脚本把 `AS_OF = "2026-09-02"` 写成运行日，他自己注释里标了「日期锚非数据披露日」，但字段仍然是运行日。）
- 沙箱只挂 **DuckDB 只读副本 + 本回合已绑定的证据集**。不给写库、不给外呼。

**「不给外呼」的理由是可复现，不是安全。** 不可复现的计算进不了证据体系，那这个工具就白建了。这一条与用户 2026-09-02 的裁决不冲突——他放开的是「不外呼」作为**能力限制**的理由；这里它是**产物有效性**的前提。

**它顺带答了一个 knevo 答不上的问题**：沙箱数与 provider 数不一致时听谁的？——**不是二选一，看推导链的输入是不是同一批证据**。有 `input_evidence_hashes` 就能判。

**第一个用例建议是跨源口径核对，不是 DCF。** 理由：

| | DCF | 跨源口径核对 |
|---|---|---|
| 输入 | 全是假设（knevo 那份 `np0=862.0` 自标 `[假设]`） | 两边都是已绑定证据 |
| 有无真值 | 无，判不了对错 | 有，谁对是可判的 |
| 现有工具能不能做 | 部分能（手算） | **完全不能**——D 系列 21 个证据块冲突了没人裁 |
| 产出 `input_evidence_hashes` | 空或伪造 | 天然完整 |

而且它接上一个反复出现的形状（`10_knowledge/cross-layer-vocabulary-reconciliation.md`：两个自洽子系统各用各的词表、中间无对账）——**沙箱可以当那个对账器**。

### 3.5 P4：底座 A/B——`sdk_glm` 主臂，`sdk_gpt` 可选第三臂

#### 3.5.1 先纠一个前提：pi / dsh 都有元能力，但都是挂在钩子上的插件 [实测 2026-09-03，全包扫描]

立案动因是「上 pi / dsh 的底座就有元能力了」。本稿 09-02 版写的是「两家都没有」——**重核后撤回**：`subagent|sandbox` 全包扫描在两家都命中，负面断言不成立。真实情况是：

| 元能力 | pi | dsh |
|---|---|---|
| 子代理 | 核心无；**有** `packages/coding-agent/examples/extensions/subagent/`（独立 pi 进程、隔离上下文、scout / planner / reviewer / worker、并行与链式），且 `packages/agent/docs/harness.md:98` 明写 Lanes 的用途之一是 subagents | **有一整个能力族** `packages/subagent/`（11 个包）：模型可调的 `subagent` 工具（`tool-subagent`），provider 多种（spawn / fork / acp / claude-code / codex / dsh-sdk），前台 / 后台 / 可续接三态，`maxDepth` 默认 3，toolFilter，并行派单 |
| 沙箱 | 核心**明确无**——`packages/coding-agent/docs/security.md` 原文：*"Pi does not include a built-in sandbox… Real isolation needs to come from the operating system or a virtualization/container boundary"*；但**有** `examples/extensions/sandbox/`（`@anthropic-ai/sandbox-runtime`，sandbox-exec / bwrap）与 `gondolin`（micro-VM 路由内置工具），见 `docs/containerization.md` | 有 `packages/sandbox/`（`sandbox` / `sandbox-policy` / `sandbox-local` / `sandbox-windows-acl`）+ `shell/bash-sandbox` + `fs/fs-sandbox`：**围绕进程执行的按会话限制策略层**（`SandboxMode` / `enforcement` / 带 `justification` 的 `sandbox_permissions` 同轮升权），README 自述 *"isolated environments replace complete capability implementations instead of registering here"*——不是计算服务 |

**两家的共同点比差异重要：子代理和沙箱全都不在循环里。** pi 挂在 extension 钩子上（`transformContext` / `beforeToolCall` / `shouldStopAfterTurn` 那一层），dsh 挂在 `ctx.subagents` / `ctx.sandbox` 服务与 `agent/pre-step` / `tools/pre-execute→allow|deny|ask` / `tools/post-execute→accept|block` 钩子上。换成谁的 loop 都不白送——装的还是插件。另外两家的「沙箱」都是**执行隔离**（bash 能跑什么、能碰什么），没有一家有 §3.4 那种带 `input_evidence_hashes` 的**计算产物**——P3 要建的东西两家都没有现成的，与底座无关。

**这反而把结论钉得更死**：元能力是**模型能点的工具**——注册表条目——与谁转循环正交。本仓已自证：`HarnessReferenceLoop` 与 `ContinuousAgentEpisode` 共用同一个 `ResearchToolRegistry` + `ToolBatchExecutor`。加一个工具 = 加一个 `ToolSpec`，不需要换 loop；换 loop 也不白送任何工具。

**该抄的是形状**：dsh `tool-subagent` 的工具契约（前台 / 后台 / 可续接三态、深度上限、toolFilter、失败时保留子代理的部分文本而不报成功）是 §3.5.5 子代理的参照；dsh 沙箱策略的字段划分是 §3.4 权限模型的参照。**抄形状、不换底座**——与 09-02 接缝命名对照 pi / dsh 原文同纪律。

**但注意 dsh 子代理契约里的一句**：*"Success contains only the child's final text."* 子代理回给父臂的是文本，不是带 `hash` / `as_of` / `source` 的证据。这条形状**不能原样抄**，见 §3.5.5。

#### 3.5.2 真正该跑的实验：`sdk_glm` 才是那一个环境变量 [实测]

```python
RuntimeBackendName = Literal["continuous_glm", "sdk_glm", "sdk_gpt", "codex_headless"]
```
（`intelligence/services/research_profile.py:69-74`）

- 切换点：环境变量 `AGENT_RUNTIME_BACKEND` → `resolve_runtime_backend()`（`intelligence/runtime/agent_runtime_factory.py:53-63`）。**无效名直接抛，不静默回落**——这条已有的纪律正好当 A/B 的第一道硬门。
- 依赖已装：`agents` **0.18.3**（`.venv-workbench`）。
- `openai_agents_runtime.py` 接了 harness 的**两个**方法：`:921` 收 `harness` 参数、`:1108` / `:1287` `assemble_prompt`、`:1147` / `:1402` `admit_finish`。文件内注释原文：「终局准入与 prompt 归领域 harness；本 runtime 只跑 SDK loop。」——它自己就说了只接这两处，其余 14 个方法见 §3.5.3。
- 生产现役：`continuous_glm` + `glm-5.3`（`baseline-health.json`）。

**两个 SDK 臂的成本完全不同**：

| | `sdk_glm` | `sdk_gpt` |
|---|---|---|
| 装配（`intelligence/api/app.py`） | `:405-427`——取 `providers[0]`，与 `continuous_glm` **同一个链首**（zhipu / glm-5.3、同 base_url），走 Chat Completions | `:428-453`——**要求 `providers[0].name == "openai"`，否则 `:437` 抛 `sdk_gpt requires an OpenAI provider`**；走 Responses API |
| 在 `finance-base-ab` 配方下 | `AGENT_RUNTIME_BACKEND=sdk_glm` 即可（`run-reference-loop.sh:48` 写死了 `continuous_glm`，要改成可覆盖） | **跑不起来**：脚本 `:36-39` 硬要求 `FORESIGHT_BUILTIN_LLM_API_KEY` 非空，链首因此是 zhipu。要跑得换凭证链（BYOK `openai` 或改 env），并决定 base_url 指中转还是直连 |
| finalizer / judge | 同一个 `GLMModelClient(providers)`（`:381-395`，与 backend 无关） | 同 |
| 与生产臂的差 | **只有壳**（及壳带来的中段差，§3.5.3） | 壳 + 模型 + 出口线路 |

`agent_runtime_factory.py:97-105` 的注释已经说明：名字里的 `glm` 是历史兼容名，不绑 provider；2026-07-25 那次 195 / 175 就是 Continuous 对 SDK **同模型**盲评。**所以纯壳差的那一臂是 `sdk_glm`，它才是「一个环境变量」；`sdk_gpt` 是一套配方，作可选第三臂，成本按上表写实。**

#### 3.5.3 Δ 里有什么：不是「纯底座差」

2026-08-06 记录：「『SDK 不如自建』这个印象要校准——2026-07-25 的 195/175 是 **GLM 下**跑的，切 gpt 后 A/B **零数据**。」该读数至今没补。今天跑比 8 月便宜，是因为三条 loop 的**入口与出口**已共用同一套 `ResearchHarness`（`assemble_prompt` / `admit_finish`），领域门在这两点上按构造相同——这是接缝线九张 PR 挣来的。

但**中段不同**。对 16 个 harness 方法的直接调用计数 [实测 2026-09-03]：`agent_episode.py` 14 个、`harness_reference_loop.py` 13 个、`openai_agents_runtime.py` **2 个**。SDK 臂没有 `govern_mode` / `steering_message` / `fallback_after_empty_batch` / `halt_after_tool_batch` / `retrieval_complete` / repair 三件（`classify_repair_need` / `warrant_repair` / `admit_repair_result`）；也不走 `ToolBatchExecutor`（使用者只有 `agent_episode.py` / `harness_reference_loop.py` / `episode_tool_batch.py` / `episode_scope.py`），因此没有 `dispatch_grants` 那套 stage-timeout 授予。

**所以 Δ(continuous_glm vs sdk_glm) = loop 差 + 中段领域钩子覆盖差（14 vs 2）+ 预算授予差。** 若用 `sdk_gpt`，再加模型差与出口线路差。写读数时四项要分开点名，不许合成一个「底座」。

两个方向都要能读：SDK 臂输了，可能只是它没有空池回退、没有 steering、没有 repair 分类——那是我们刚建的东西，不是「SDK 底座差」；SDK 臂**赢了**，说明无导向的 loop 比我们中段那套机器强，中段是净负——这才是「要不要换底座」这个问题的直接实验。

#### 3.5.4 硬门：必须断言生效模型，不是配置模型

`agent_runtime_factory._effective_env_model()` 的 docstring 记录了一次真实事故：**2026-08-08 生产出口切中转后，health 报 `glm-5.2`，实际跑 `gpt-5.6-sol`**——同一个函数里凭证判定改成了 provider-neutral，模型那半没跟着改。

那次的修法是让 health 也读 `detect_providers()`。但要看清：`detect_providers()` 读的是环境变量，给出的是我们**请求**的模型名；中转是否照着给，只有响应体里的 `model` 字段知道。**全仓目前没有任何地方落盘这个字段**——`llm_refine.py:1098-1103` 的 `_post_chat_message` 只留 `choices` 与 `usage`；`finance-base-ab` 产物里的 `"model": "glm-5.3"` 来自 `shape_lib/kernel.py:43` 的 `providers[0].model`，也是配置值。

A/B 的读数若取配置值，会把「模型没真的切过去」读成「SDK 底座没差别」。**硬门写死**：

1. 两臂 `source_revision` 相同；
2. 两臂 `runtime.backend` 分别自述 `continuous_glm` / `sdk_glm`（第三臂 `sdk_gpt` 另记）；
3. **两臂每个 model turn 的响应体 `model` 字段**落盘，并与请求的模型名比对；中转不回该字段时记「未回」，不填配置值；
4. 同题、同 harness（默认 `FinanceResearchHarness`）、同 `task_frame_hash`。

四条缺一条，该轮读数作废。**第 3 条是 P4 的前置代码改动**：continuous 臂在 `_post_chat_message` 取 `body["model"]`；SDK 臂的 `ModelResponse`（agents 0.18.3）只有 `output` / `usage` / `response_id` / `request_id`，要在 `build_glm_sdk_model` 已自建的 `httpx.AsyncClient` 上挂响应钩子取。两处采集 + 一个产物字段，与 §4 的 `authorized_capabilities` 同族——都是把生效值写进产物。配方复用 `finance-base-ab` 的隔离配置（resolved 快照 cwd、独立 users、启动器 env、RAG 预热），与 P2''-live 同规程。

#### 3.5.5 元能力：SDK 给的是派单机制，账本一分不给

- **机制白拿**：Agents SDK 的 `handoffs` / agents-as-tools ≈ 派单，Chat Completions 与 Responses 两条线都能用（handoff 本身是 function tool）。这是 knevo 唯一确认领先的一轴（其调用底账已行为证实），`sdk_*` 下不必自建**调度**。
- **账本不白拿**：子代理回到父臂的是文本——dsh 的契约原文 *"Success contains only the child's final text"*，SDK handoff 同理——没有 `hash` / `as_of` / `source`，进不了 `admit_finish` 的绑定。要让派单产物可用，子代理必须**共用或合并父臂的 `EvidenceLedger`**，父臂结论句绑到子代理铸出的证据上，而不是绑到它的总结文本。这笔成本在 `continuous_glm` 自建子代理与在 `sdk_*` 用 handoff 是同一笔，**底座选择不改变它**。
- **须先实测**：hosted tools（code interpreter / web search）只在 Responses API 一线（`sdk_gpt`，`build_gpt_sdk_model_factory`）。当前出口是中转（见 `_effective_env_model()` 记录的线路），**中转支不支持 hosted tools 未验，不得假设**。`sdk_glm` 走 Chat Completions，与 hosted tools 无关。
- **会撞墙**：即便支持，hosted tool 的产物由对端沙箱生成，**不携带本仓的 `hash` / `as_of` / `source`**，按 §2 来源契约进不了 `admit_finish` 的绑定。**因此 hosted code interpreter 不能替代 P3**，除非外面再包一层铸哈希。

#### 3.5.6 顺序

P4 **不排在 P0 前面**。P0a 是一行、P0b 是一个参数，都有已知真值、当天出读数；P4 要烧两臂配额，且要先落 §3.5.4 第 3 条的采集。P0 的修复对两臂同时生效（SDK 臂也走 `registry.authorized_specs(context.contract.allowed_capabilities)`），先做 P0 能让 P4 的 Δ 少一个已知污染源。

### 3.6 抄 knevo 的工具形状，契约自己做

用户裁决（2026-09-03）：

> 「knevo 的有些能力没用上，是他的工具调用契约没做好。我们反倒可以把他的工具抄过来，我们自己把契约做好。」

§1.4 的底账支持这个读法：他 22 次调用里，`finance_statement` 无 provider、`finance_graph_context` 找不到「贵州茅台」、`finance_shareholders` 失败——工具在菜单上，底下没源或没实体解析，模型试了才知道。我们这一层反而是做好了的：`_TOOL_CONTRACTS`（`research_tool_registry.py:960` 起）给每个工具写死「查不到 ≠ 不存在」「二手不升一手」「累计口径不还原」；`ProviderTrace` 分 `success` / `empty` / `error`；注册表只挂 `authorized_specs`，没授权的工具模型看不见。

**抄的规则**：抄形状（参数面、返回面、模型看到的描述），不抄实现；**每个进注册表的新工具，三条契约缺一不挂**：

1. **空结果语义**：返回为空时模型该写什么（证据缺口，不是否定结论）——沿用 `l3_lookup` 那条的写法。
2. **来源分档与 `as_of` 来源**：产物 tier 是什么、`as_of` 取披露日还是抓取日、能不能当公司级硬事实——沿用 `web_search` / `financial_data` 那两条的写法。
3. **参数含义与拒绝条件**：模型传的参数会被读（不是 P0b 修的那种 `_query` 摆设）；解析不到目标时报 `error` 带原因，不静默回空。

这三条与 §2「形状契约软」不冲突：形状契约管的是**允许谁进**（来源白名单、产出类型声明），本稿放软；这三条管的是**进来的工具得说清自己是谁**——空了怎么说、`as_of` 从哪来、参数读不读——是 §2 来源契约在工具面的落点，属硬。

**候选形状**（来源：用户转述的 knevo 22 次调用底账，[转述]）：

| knevo 工具 | 我们的对应 | 抄什么形状 | 契约要点 |
|---|---|---|---|
| `web_fetch` | **无** | 新增：给 URL 取正文 | tier `public_web`；`as_of` 取页面日期，取不到记抓取日并标明；契约写「二手，不替代一手」。这是 knevo 这题赢的机制，也是 `web_search` 从 160 字符线索升级成可读证据的前提 |
| `finance_search_data(providers=[...])` | `web_search` / `news_search` / `kb_search` 各一把 | 显式 `providers` 参数让模型选源，产物回显实际走了哪个 provider | 每个 provider 的空结果分开报，不合并成一个「无结果」 |
| `finance_provider_status` | 无「调用前可用性自述」；`ProviderTrace` 是事后 | 注册表在 prompt 里自述当前 ready 的源（`fetch_enabled()`、库文件存在、key 存在） | 与 §4 的 `authorized_capabilities` 同一份数据：模型看到的 = 产物记的 |
| `finance_statement` | `financial_data`（P0b 之后） | 报告期参数 | knevo 这条「无 provider 支持」就是契约缺失的原型：我们的规矩是没源的工具不进注册表 |
| `finance_graph_context` | `graph_lookup` | 实体解析先于查询；hops 参数 | `entity_not_found` 要区分「库里没有」与「没解析到」——前者是缺口，后者是工具错 |
| `finance_shareholders` | **无** | 十大股东 / 流通股东 | 需一手源，本稿只记不排 |
| `finance-researcher` 子代理 | 无 | 按 dsh `tool-subagent` 形状（§3.5.1） | 结果携带证据引用，不只文本（§3.5.5） |

**本稿排期的只有两项**：`financial_data` 报告期（即 P0b）、`web_fetch` 新增（排在 P0a 之后——它决定 web 线索能不能升级成可读证据，是 P0a 三分法里第三种结果的出路之一）。其余记形状不排期——每加一个工具占一个槽，预算拥挤的老账（`evidence_capabilities.py:109-116`）还在，先等 P1 的弃权率基线。

**这一节和 §3.5.1 是同一句话的两面**：pi / dsh 的元能力、knevo 的工具，全都是挂在注册表 / 钩子上的东西。差距在工具面与契约面，不在 loop。

---

## 4. 顺带修两个诊断缺口：授权集不进产物、生效模型不进产物

定位 §1.3 那一行花了四步，原因是**产物里没有授权集**。

`finance-base-ab/out/reference-loop-0902b/episode.json` 里能找到 `diagnostics.question_type` 与 `notes.first_turn.tool_set`（实际调用），**但没有「这一轮授权了哪些能力」**。于是从收据上无法区分两件事：

- 工具**被授权但模型没选**（→ 检索规划问题）
- 工具**压根没授权**（→ 策略表问题）

这两者的修法完全不同。**改动**：episode 产物增加 `authorized_capabilities`（解析后的 floor ∪ 计划授权），与 `tool_set` 并列；同一份数据也是 §3.6 `finance_provider_status` 形状的供数源——模型在 prompt 里看到的可用源，就是产物里记的那份。

第二个缺口是 §3.5.4 说的：产物里的 `"model"` 是 `providers[0].model`，配置值；响应体的 `model` 字段全仓无人落盘。**改动**：逐 model turn 记 `served_model`（continuous 臂在 `_post_chat_message`，SDK 臂在 httpx 响应钩子），与请求模型名并列。

两者都是 `10_knowledge/info-not-delivered-bug-pattern.md` 的同族形状——**验证要断言生效值，不是配置值**。

---

## 5. 验收（缺一条不算）

**P0a**

1. 静态：以茅台题的 `TaskFrame`（`question_type=financial_analysis`）调 `runtime_capabilities_for_frame()`，断言结果含 `web_search`；且 20 条策略里不含 `web_search` 的恰为 4 条本地盘面/技术面策略（断言写成名单，新增策略漏授权会红）。
2. 变异：把 `"web_search"` 从元组里拿掉 → 第 1 条必须红。（未被变异证伪过的守门测试是假门禁。）
3. Live：茅台题重跑，**授权集含 `web_search`**（读 §4 新增字段）**且**至少一臂实际调用了它。两个读数分开记，不许合并。
4. 结果按三分法记，落哪一格都写明：(a) 答案含 1741.44 且带来源 + as-of；(b) web 拿到 1741.44 但正文只许写「待验证线索」——记为「授权达成、断言受契约 / 判官所限」，转 P0b / P2；(c) web 也拿不到，写出为何。

**P0b**

5. `financial_data` 对「2024 年 600519」返回含 2024-12-31 报告期行、数值 1741.44、`source` 为 D7 链之一、`as_of` 为披露日（fixture 固定日历为 2026-09，确保该期在默认 6 期窗外）。
6. 变异：把 runner 里读年份 / 报告期那段拿掉 → 第 5 条必须红。
7. Live：茅台题重跑，至少一臂以 `financial_data` 的一手证据写出 1741.44 并通过 `admit_finish` 绑定。

**§3.6 抄形状**

8. 注册表守门：每个 `ToolSpec` 必须在 `_TOOL_CONTRACTS` 有条目（§3.6 三条契约的落点），否则装配期抛（有牙测试：注册一个无契约的 stub → 红）。这条对现役工具一并生效，先跑一遍看谁裸着；`produces` 仍按 §1.2 当软先验，不进这道门。
9. `web_fetch`：给定新浪财务指标页 URL，产物 tier 为 `public_web`、`as_of` 非空且标明取自页面日期还是抓取日、`source` 为该 URL；给定不可达 URL，`ProviderTrace.status == "error"` 带原因，不静默回空。

**P1**

10. `aggregate_components()` 输出含 `abstain_rate`，且**不进总分**。
11. 现有冻结题集（knevo28 + D 组 10）弃权率基线落盘，含逐题 `abstain_reason` 分布。
12. 噪声底：两臂同码同题组的弃权率 Δ 实测，门槛从该组现算。

**P2**

13. 删句事件结构化落盘（`deleted_sentence` / `reason` / `bound_evidence_ids` / `source_tier`），**判据未改**。
14. 「因来源档次被删的有出处真话」占比实测落盘。
15. 该占比 < 阈值时，本刀**停在这里不再往下**，并把这个结论写进收据。（停下也是验收通过。）

**P3**

16. `derived_calculation` 产物无 `input_evidence_hashes` 时，`admit_finish` **驳回**绑定它的结论句（有牙测试）。
17. `as_of` 取输入最旧值：构造两条不同 as-of 的输入证据，断言产物取旧的那条。
18. 跨源口径核对用例端到端跑通，产物哈希链完整。

**P4**

19. 四条硬门全部落盘（§3.5.4）：同 revision、两臂 backend 自述 `continuous_glm` / `sdk_glm`、**两臂逐 turn 的响应体 `model`**（不是 `providers[0].model`）、同 `task_frame_hash`。
20. 逐题读数含 `abstain_rate`（依赖 P1 已落地——**P4 排在 P1 之后**）。
21. 结论只在超过噪声底门槛时才写。噪声底做法沿用 2026-08-27：**塞一组两臂同码同题的样本，其 Δ 真值必为 0**，门槛从该组现算，不套 8 月的 `|Δ|≳2.4/20`（那是连续分的门槛，且是 GLM 下量的）。
22. 读数里 Δ 的四项分开写：loop 差、中段钩子覆盖差（14 vs 2）、预算授予差（两臂 `tool_calls` 与 `zero_grant` 计数并列）、模型差（仅第三臂）。合成一个「底座差」的读数作废。
23. hosted tools 实测结论落盘（中转支持与否）——**只在第三臂 `sdk_gpt` 真跑了才有**；没跑就写「未验」，不得从 `sdk_glm` 臂推断。这决定 P3 是不是还要自建。

**全局**

24. 全量 pytest 与基线同一组红（当前 5 红 = `test_dream_mine` 环境项），passed 只增不减。
25. `python3 scripts/layer_audit.py` ERROR 0。
26. `python3 /Users/a77/agent-memory/scripts/graph_audit.py` exit 0（新增能力节点要回写能力图谱，不另建第二份清单）。

---

## 6. 非目标 / 红线

- **不删 `ToolSpec.produces`**。它作为检索规划的先验仍有用，只是不当硬指标。
- **不改 `admit_finish` 的绑定必须性**。输出必须带证据索引这条是本稿的前提，不在放开范围内。
- **不抬 judge 窗口**。
- **不动 90/60/30 预算线**。茅台题里 `l3_lookup` / `evidence_lookup` 拿到零授予是预算侧的事，与本稿正交，另案——但它是 P4 的混杂变量，§3.5.3 已点名，读数里要并列写出（第 22 条）；另案时以 knevo 22 次对我们 4 次为起点。
- **不切 8792**。本稿零运行时改动；P0 实施后的切流由用户裁决。
- **不做 pi / dsh / knevo 的 loop 移植**——抄的只是工具形状与契约参照（§3.5.1、§3.6）。也不删 `continuous_glm`——P4 是对照，不是替换；任一 SDK 臂胜出也要另案裁决切不切。
- **P4 的 Δ 不许写成「底座差」**——四项分开（§3.5.3、第 22 条）。
- **没有三条契约的工具不进注册表**（§3.6、第 8 条）。抄 knevo 的形状不抄他「挂着但没源」的状态。
- **hosted tools 未验之前不写进任何设计。**
- **落 main 那一下交给用户。**

---

## 7. 已知反对意见与回应

**「放开输入侧会让模型乱选工具、烧预算」**
——P0a 只加一条 `mandatory=False` 的授权，不强制调用；P0b 不加工具，只让现役工具读它本该读的参数。真实风险是预算拥挤（`evidence_capabilities.py:109-116` 的注释已记录：一轮 research 4-6 次调用就 `budget_exhausted`，广授权会挤掉盘面查询）。**所以本稿只补一条策略，不做全局放开**；要不要更广，等 P1 的弃权率基线出来再谈。

**「P2 改松了会漏幻觉」**
——正是因此写死「先量后改」，且给了「量完发现不该改就停」的验收出口（第 15 条）。

**「沙箱不修已知缺陷，为什么还做」**
——用户裁决明确要能力放大，且 §3.4 已如实写明它不抬现有读数、需要另冻题集。这是知情决策，不是顺手夹带。

**「先换 pi / dsh 底座拿元能力，再做这份工单」**
——§3.5.1 重核后的事实是：两家都有子代理与沙箱，但**都是挂在钩子上的插件**，换 loop 不白送，装的还是插件。元能力是注册表条目，与循环归属正交。且 P0a 是一行、P0b 是一个参数，排在任何移植之后都是错的顺序。**真正对应这个诉求的实验是 P4，主臂 `sdk_glm` 的代价是一个环境变量。**

**「那 SDK 臂赢了是不是就该切」**
——不是本稿范围。P4 只产出读数；切流是另案，且要过 acceptance-workflow 的主干门禁与三项验证。另外读数要按 §3.5.3 拆：`sdk_glm` 对 `continuous_glm` 的 Δ 含 loop 差、中段钩子覆盖差、预算授予差，**不含模型差**；`sdk_gpt` 再加模型差与出口线路差。要把模型差单独分离出来，得 `sdk_glm` 与 `sdk_gpt` 同跑。本稿主臂 `sdk_glm`、`sdk_gpt` 可选；哪一臂赢都先问「赢在四项里的哪一项」，再谈切不切。

**「抄 knevo 的工具，不就把他的失败也抄过来」**
——抄的是形状不是实现。他失败在契约缺失：工具挂着、底下没源、实体没解析，模型试了才知道。§3.6 的三条契约就是防这个：没源不挂（第 8 条守门）、空结果有语义、参数真被读。我们已经在现役工具上这么做了，只是要让新工具也过同一道门。

---

## 8. 成立条件

tree：`/Users/a77/fwp-wt-capability-amplification` @ `spec/capability-amplification-output-gate`，基线 `gitea/main@daea04a0`。09-02 版本稿为唯一改动；09-03 实施后同树另有 18 个已跟踪文件改动 + 4 个新测试文件 + 收据与在途交接（全部未提交），以及仓外 `/Users/a77/finance-base-ab/shape_lib/project.py` 的三个 `notes` 键（该目录不受版本控制）——清单见收据。
主树 `finance-workspace-private` 停在 `fix/observation-qualifier-order`（脏、不在 gitea/main、归属不明），**本轮未动**。
读数来源：`finance-base-ab/out/reference-loop-0902b/`（09-02 20:20 两臂 live）、2026-08-27 四臂实验、2026-08-28 react round2、2026-09-02 knevo 对照（用户转述其 22 次调用底账与 `finance_provider_status` 原始返回；§1.4 表与 §3.6 候选形状均为 [转述]）。
静态核实：`evidence_capabilities.py` / `task_frame.py` / `research_tool_registry.py` / `research_harness.py` / `research_profile.py` / `agent_runtime_factory.py` / `openai_agents_runtime.py` / `api/app.py` / `episode_tools.py` / `market_financials.py` / `agent_research.py` / `llm_refine.py` 均在本树读取，行号对该 revision 成立；`finance-base-ab/run-reference-loop.sh` 与 `shape_lib/kernel.py` 在 `/Users/a77/finance-base-ab` 读取。
§1.3 第二层「2024 年报在默认 6 期窗外」09-02 版是按报告期日历做的静态推断；**09-03 已用 F10 只读探针复现**（第 7 行即 2024 年报 1741.44，披露日 2025-04-03），P0b 第 5 条的 fixture 逐字复刻那 8 行。同日另发现：私有产物 `continuous-episode.json` 的 `contract.allowed_capabilities` 一直记着授权集（两臂同为 7 项、无 `web_search`），§4 说的「产物里没有」指的是 finance-base-ab 投影 `episode.json`，修法因此落在投影层。
§3.6 第 8 条首跑读数：生产装配 `build_episode_registry` 自建的 `finance_query` / `evidence_search` / `memory_lookup` 三个 spec 未接 `contract=`，`_TOOL_CONTRACTS` 的条目写好了但模型从没见过；已接上并由守门钉住。
P0b 初版（上一会话）用 `\b(20\d{2})\b` 抓年份，Python `\w` 含 CJK，「2024年」不命中，对茅台问句是空转；已改数字边界并写钉子。
§3.5.1 的对照源（只读，未改动）：pi `/Users/a77/pi`、dsh `/Users/a77/deepseek-harness`。09-02 版的负面断言（两家均无子代理 / 沙箱）用 `spawn.?sub|subagent|sub_agent|sandbox` 全包扫描（排除 node_modules / dist / target）于 09-03 重跑后**不成立**，命中：pi `packages/coding-agent/examples/extensions/{subagent,sandbox,gondolin}/`、`docs/containerization.md`、`packages/agent/docs/harness.md:98`；dsh `packages/subagent/`（11 个包）、`packages/sandbox/`（4 个包）、`shell/bash-sandbox`、`fs/fs-sandbox`、`AGENTS.md:28`。本版结论改为「两家都有、都是插件、都不在循环里」；这仍是一条对「不在循环里」的断言，若两家将来把子代理或沙箱做进 loop 本体，需重验。dsh `tool-subagent` 契约引文取自其 `README.md`。
§3.5.3 的调用计数是对 16 个方法名做 `harness\.<name>` 正则直接计数（`agent_episode.py` 14 / `harness_reference_loop.py` 13 / `openai_agents_runtime.py` 2），间接调用未计；`ToolBatchExecutor` 使用者按 `rg -l` 列出。`ModelResponse` 字段（output / usage / response_id / request_id）读自 `.venv-workbench` 里的 agents 0.18.3。
`agents` 0.18.3 版本读自 `.venv-workbench/bin/python`（该 venv 是本仓测试与运行的唯一解释器）。
未执行（09-03 实施后仍成立的部分）：~~**未跑任何一臂 A/B**、未跑 P0a / P0b 的 live 条（§5 第 3、4、7 条）~~、P1–P4 未动。已执行：P0a、P0b、§3.6 第 8 / 9 条、§4 两个字段的代码与静态验收；全量 pytest、四道审计、能力图谱审计——读数在收据。
**09-03 10:36 补：P0 live 两臂已跑**（`finance-base-ab` 配方，快照 `ccf9343162d0` = PR #537 合入后的 main），§5 第 7 条 ✅ 两臂、第 4 条落 (a)、第 3 条授权 ✅ / 实际调用 ✗（`financial_data` 传 `report_period` 一手拿到 1741.44，web 未被需要）；`notes.authorized_capabilities` 9 项含 `web_search` / `web_fetch`，`notes.served_models` == 请求值。§1.3 的根因判断（一行授权 + 一层工具窗口）在 live 上被第二层证实、第一层未被用到。同日 10:41 8792 切到该快照（§6「不切 8792」指本稿零运行时改动那一版；切流按 §6 末条由用户「持续推进」授权执行）。P4 硬门第 4 条之外新发现两 loop 首轮请求差 4 token（配方 ±3 未过），P4 前须定位。读数与产物路径在收据「P0 live 读数」节。
证据等级：§1.1–§1.2、§1.3 第一层与第二层、§3.5.1–§3.5.3 为 [实测]；§1.4 knevo 部分与 §3.6 候选形状为 [转述]；§3 各刀的效果预期为 [推断]，验收即为其证伪路径。
