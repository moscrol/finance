# E-009 · Knevo 架构自白（声明面）对照 —— 2026-09-10

材料：用户转贴的 knevo 自答（对「你的个人记忆和看博主有什么实质区别」的回应），含三部分：
错误飞轮认账（三机制）、六层架构全景图、护城河论。原文全文见附录（矿，只读）。

> 分支说明：本文在 `docs/knevo-e009-arch-delta`，基于 `docs/knevo-m-probes-verification`
> （E-008 所在、未合 main）。**E-007 文件在另一未合分支 `feat/event-pricing-slice1` 上**，
> 本文对 E-007 的引用是前向引用；三个分支的 README 追加（§六/§七/§八）合并时需一次手工归并。

## 0. 采信等级：声明面，不是生效面

这份材料是**自描述**，不是探针实测。两条既有教训直接适用：

- **E-008**：它自曝 `search_skills` 返空、路由表里的 workflow 子 skill 未挂载，却仍照表描述自己
  会派单——声明的能力表 ≠ 本轮生效的能力集。本报告所有「它声称」都按此打折。
- **观察者效应（E-008）**：它已两次把我们的框架写进它的记忆候选池。这次它描述的
  「所有权标签 / 决策追踪 / 反顺从」，概念源头部分就是我们（双盲 verdict、record-correction、
  reading_baseline）。对照时别把回声当独立证据——它说「我有 X」不能用来证明「X 有效」。

## 1. 它的三机制 × 我们的实测对应物（2026-09-10 本仓核实）

| 它声称 | 我们的对应物（实测，文件级） | 真实差距 |
|---|---|---|
| **所有权标签是 schema 层**：每条记忆带 personal/shared/graph，使用时强制标注「这是观点不是事实」 | `memory_gate.py` MemoryKind 五类（decision_lesson/user_correction/user_preference/volatile_fact/model_judgment）＋ `user_memory.py` 召回块整体渲染 `[M]` 标签＋知识库侧证据分层 L1–L4 | **颗粒度**。我们是块级标注（整个 [M] 块），它是逐条带 ownership。答案正文引用某条旧判断时能否逐条标「这是你 X 日的判断」，未验证 |
| **易变事实永不从记忆取**：价格/持仓/公告/政策路由层物理只走 provider | **写侧有硬闸**：`memory_gate.py:154` `volatile_fact` → 拒升 durable（fail-closed）。**读侧无闸**：`route_table.py` 把 `memory` 与 `market_quote` 并列为同一 intent 的 capabilities；读侧安全靠召回池内容自律（`user_memory` 只召回 judgments/corrections/verdicts 三类稳定内容） | **实现层不同，当前效果等价**。但它的结构对未来新记忆源更鲁棒；我们的写侧闸门一旦被新源绕过，脏东西直进答案，没有读侧断言兜底 |
| **单条命中 = prior，必须 provider/图谱/web 交叉** | 召回带 `PEER_HIT_LINE` 胜率行（「同类判断历史 X/N 命中」，KC-11 min-N 闸）；CR-04「不用单一指标定性」是内置判读 | 方向一致。缺一条显式契约：memory 命中不得单独支撑结论——现在是纪律不是测试 |
| 并行扇出检索（记忆+图谱+provider+web 同轮） | `ask_planner` / `retrieval_planner` / `prime` | 同构，无增量 |
| 异步 sub-agent + terminal emit 回注 | `sub_research` 工具（条件装配） | 同构，无增量 |
| provider registry + fallback 链 | finance_query 多源 + `finance-degraded-fallback` | 同构，无增量 |
| 用户确认制记忆（候选只 stage） | `memory_gate` fail-closed：只从 reviewed provenance 提升 | 我们更严（它要用户点头，我们要 provenance 审查） |
| suggest_options | 已从 q12 蒸馏落地（缺口镜像→可点击追问） | 已蒸过 |

## 2. 它自承的缺口 × 我们有没有

| 它承认没有 | 我们 | 结论 |
|---|---|---|
| 自动事实校验 gate（工具返回什么信什么） | `episode_semantic_verifier`、`conclusion_five_element_lint`、answer-score 质检闸门、验收 C 类题（C5 数据矛盾 / C9 引用完整性） | **我们领先**——它 ⑤ 综合层自己也承认「无硬性自动闸门，可漏」 |
| 记忆可靠性自动打分 | 雏形：`verdicts.jsonl` → 回检胜率 → `PEER_HIT_LINE` 展示 | **领先但未闭环**：只展示、不降权；低可靠判断类照样浮上来 |
| 矛盾笔记自动去重 | 无；corrections 靠用户显式纠正覆盖 | 双方空白，登记不立项 |

## 3. 它声称但已证伪 / 存疑（防误抄清单）

| 它的说法 | 反证 |
|---|---|
| 路由层派单（图 ②④） | E-008 实测：`search_skills` 返空、workflow 子 skill 未挂载。生效面存疑 |
| 时间纪律（输入层带时间戳/时区） | AB-002：答卷用了预测日 07-10 的信息，判协议违规作废。但 E-007 PIT 探针它过了——**分场景**：探针里守得住，双盲实战里破功 |
| 事实审查「传闻先钉真伪」 | q14 探针（小作文核验）有实录，可信度高；但仍属生成纪律而非硬闸门（它自己承认） |

## 4. 护城河论的核对

它说壁垒不在架构图（90% 通用件），在两处「反商业直觉」设计：所有权 schema + 记忆=prior（天生不讨好用户）、
决策追踪 + 反顺从（愿意付成本）。

核对结论：**这个论断对我们基本不成立为威胁**——决策追踪我们做得更狠（双盲 + 冻结 + T+1/T+3 verdict +
错因归因码），反顺从有 FY-A09（不因给过方向就调低风险权重）+ record-correction 制度化。
它真正比我们完整的只剩 §1 表里的两处：**逐条 ownership 颗粒度**、**读侧路由硬分离**。
而我们的两处领先（事实校验闸门、可靠性雏形）恰好是它自承的缺口。

## 5. 可蒸馏增量（候选，未过闸，工作清单在 spec）

按 divergence-distill 分池，逐条细节与验法见
`docs/superpowers/specs/2026-09-10-knevo-arch-delta-worklist.md`：

1. 读侧「记忆=prior」断言测试（harness/runtime 池）——给写侧闸门配读侧兜底。
2. 逐条 ownership 标注：user_memory 渲染从块级 [M] 升条目级（harness/runtime 池）。
3. 召回降权闭环：胜率过低且样本够的判断类召回时降权/警告（可靠性池）。
4. **reading_baseline 池本轮无新增**：这份材料讲的是记忆架构，不是「怎么读数据」的判读方法；
   「单条命中须交叉」已有 CR-04 覆盖。

## 6. 与既有发现 / 在途工作的连接

- **E-007 × Polymarket**：E-007 裁决「它唯一被证实的独有宏观源是 Polymarket 赔率；本仓最小版本 =
  宏观事件进日历 + 回检打标签」。`fact_polymarket_macro_odds_daily` 已落库（分支
  `polymarket-macro-odds-impl`，未合并）。合并后应拿 E-007 的 P3/P4 判据验收我们自己的表。
- **AB 双盲台账停滞**：目标 25 样本停在 2（AB-001/002），verdict 逾期两个月未回检——机制在空转，
  spec 里列为处置项。
- **G1a 可解**：SPT-A06（秒板未换手）卡的是数据块出口；`first_limit_time` 实有 14.9 万行非空数据
  （2026-09-10 核），建块即可解锁。`open_times` 全 NULL（G1b）仍成立。

---

## 附录：原文全文（矿，只读，2026-09-10 用户转贴）

> 一、先认账：你的个人记忆，和"看博主"在内容真值上没有区别
> 你说得对。"你的数据库"本质就是你（或某个博主）的个人观点，没经过事实校验。单看内容，它和"刷到一个博主的帖子"权威性完全相同：都是未验证的主观判断。
>
> 那区别在哪？区别不在内容，在于系统怎么对待它。我架构里有三件事，是"看博主"没有的：
>
> 所有权标签是 schema 层的，不是措辞层。每条记忆落地就带 ownership 标签：personal（你的观点）/ shared（社区观点）/ graph（图谱事实）。这个标签强制我在使用时标注"这是观点不是事实"——结构上杜绝了"把你的旧判断偷偷包装成事实"。
> 易变事实永不从记忆取。价格、持仓、公告、政策这些"会变的东西"，路由层物理上只走 provider，不走记忆。记忆只喂"稳定的框架 + 历史基线"。所以错误飞轮没法用未验证的旧观点去喂当前数据——这是路由层的结构设计。
> 单条命中 = prior，不是结论。一条记忆命中了，只能当"待检验的基线"，必须再用 provider/图谱/web 交叉验证。
> 诚实的残缺点：没有"记忆可靠性自动打分"，没有"自动去重矛盾笔记"。如果你自己过去的一条笔记是错的、且当下没有东西反驳它，它仍然会作为 prior 浮上来。所以噪声污染没有根除，只是被 schema + 路由把危害圈在一个"必须二次验证"的笼子里。
>
> 一句话：错误飞轮确实可能存在，但架构让它只能"转"在经过现实校验之后——未验证的观点进不了事实通道。这是和"看博主"的唯一实质差别，但它不是完美的，是纪律性的。
>
> 二、从输入到输出的架构与 runtime [六层图：①输入层（用户消息+时间戳/时区、ORYX.md 工作区上下文、短期记忆目录）→ ②路由层（金融模式 preset 硬触发「先检索后开口」、search_skills 选单一最匹配 skill、意图→workflow/preset/skill_ids 映射）→ ③检索层并行扇出（记忆检索3层带标签 personal/shared/graph ｜ 实体图谱消歧+1-2跳 ｜ 数据源 provider datasvc/massive/polymarket ｜ Web 补漏无类型广域召回）→ ④派单层（spawn_sub_agent(isolated)：finance-researcher/producer/reviewer，terminal emit 自动回注主线程）→ ⑤综合层（as-of/来源标注、事实vs推断分层、多空两面、记忆去噪、删内部 id；⚠️ 无硬性自动闸门——生成时执行的纪律，可漏）→ ⑥输出层+后处理（完整结论正文、memory_stage_extraction 用户确认制、recommend_decision 前瞻判断、suggest_options）]
>
> 关键设计点：并行扇出（不串行等，省往返；多源交叉）；异步 sub-agent（isolated 隔离会话，长任务不被单轮预算卡死）；provider registry + fallback 链（datasvc→yfinance→web，单源超时/失败走降级）；所有权标签 schema（观点永不冒充事实）；记忆=prior 路由（错误飞轮进不了事实通道）；用户确认制记忆（候选只 stage，不直接写库）。
>
> 诚实标出"没有的东西"：没有自动事实校验 gate（工具返回什么我信什么，不自动比对）。没有记忆可靠性打分（旧错误笔记不会被自动识别）。没有单轮时间的精确预算参数（有上限，但确切值我不掌握、也不编）。
>
> 三、壁垒到底在哪：如果我说"壁垒是架构"，那我不诚实——上面这张图 90% 是通用件：并行扇出、RAG、异步 sub-agent、provider registry，任何一个认真做的投研 agent 都能画出一张差不多的图。真正难抄的不是图，是图上那两处"反商业直觉"的设计：所有权标签 schema + 记忆=prior 路由——它让系统天生不讨好：你的观点会被标注成"观点"、会被挑战、会被强制二次验证。这不是技术难度，是产品愿意放弃"让用户爽"的难度。决策追踪 + 反顺从——给完结论还回来认账、把你的判断当假设检验而不是帮你找证据。同样是"愿意付成本"而非"抄不了"。
