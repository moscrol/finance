# feat/adaptive-research-loop

## 这个分支做什么
模型自主选视角并随证据调整；不固定股票池。继续同会话反馈/公开保真，不转K3外审。树 `~/finance-worktrees/adaptive-research-loop`。

## 决策与被否方案
- 原句/阶段回原REPAIR_GOAL；否按删句后编号猜原句。
- 诊断与授权分离；否让诊断改预算/增额度。数字补证诊断仅在授权后投递。
- SDK复用领域消息，否私自截短/另造提示；缺历史仍闭工具。
- 发布只对未解决机械/前置反馈降级；`judge`语义删句或降级为issue算已处理，否一律降级会误伤合法历史完成态。
- 不恢复拒句/拼私有gaps。完整理由见 `docs/handoffs/2026-09-21-adaptive-repair-publication.md`。

## 当前状态
最后一个业务提交 `7172ba30e`，其后只有文档提交；代码树干净，未push/PR/合main/部署。公开发布上限已接入并完成误降级修正。证据目录 `~/.finance-runtime/adaptive-repair-publication-20260921/` 已补齐 README / 范围审计 / 目录外校验日志。

2026-09-21 复核已撤回一项曾未提交的改动（悬空连接词剥离），见下「候选：悬空连接词剥离（已撤回）」。

2026-09-21 11:10 跑了真实模型冒烟第 1 题（寒武纪可证伪跟踪条件，单臂 off，生产配置 glm-5.3-flash + judge llm），代码未改；结果见下「真实模型冒烟 1/3–5」，原件 `~/.finance-runtime/adaptive-live-smoke-20260921/`（README / SHA256SUMS，目录外校验日志同名 `-verification.log`）。12:09 跑了第 2 题（东阳光，「只用本地资料」型），见「真实模型冒烟 2/3–5」，原件 `~/.finance-runtime/adaptive-live-smoke-20260921-q2/`。

## 已验证
精确全量 `12096P/85S/2X/17 warnings`，收据 `~/.finance-runtime/test-receipts/20260920T220029Z-7172ba30.json` 绑定 `7172ba30e`（`dirty=False`、`exit_status=0`、依赖指纹未绕过）；`7172ba30e..HEAD` 用 `git diff --name-only` 验证只出 `docs/`，故该收据代表当前代码——**下一个 agent 接手时请重跑这一条验证，再有业务提交它就不成立了**。定向历史4P、发布矩阵21P、跨后端24P、Ruff通过。最终撤线：去发布上限16F/恢复24P；误把已解决语义修订当未解决3F/恢复22P。

## 候选：悬空连接词剥离（已撤回）
问题真实：语义删句后幸存句以「反之/但/因此」开头，公开投影留悬空半句。实现有缺陷，已撤回，补丁存 `~/.finance-runtime/adaptive-repair-publication-20260921/orphan-connective-candidate.patch`（`git apply` 可恢复）。

撤回原因：`_strip_orphan_backref_connective()` 只判断行首是否**以**连接词开头，不要求该连接词是独立话语标记，把词素当成了标记。四条反例（实测，撤回前跑过）：

| 输入 | 该实现输出 |
|---|---|
| `相反的观点认为量能不足。` | `的观点认为量能不足。` |
| `同理可证丙。` | `可证丙。` |
| `所以说丙。` | `说丙。` |
| `但丁的观点是丙。` | `丁的观点是丙。` |

随附的 5 条测试全部只覆盖「连接词后接标点或独立成句」的顺风样本，加一个假朋友 `但凡`，四条反例一条都红不了。

要重做须先解决：连接词表里 `但/相反/同理/所以/因此/不过` 都是**兼类**（既是话语标记也是词素），而主用例 `但上涨家数仍待改善。` 恰恰不带标点，所以「必须后接标点」这个统一守卫会废掉主用例——需要逐词分档（无歧义的多字标记可裸剥，兼类词要求后接标点），不是一张词表能收的。收益只是 partial 答案的表面整洁，而 partial 状态与公开提示已把不完整讲清楚；且本分支立场是宿主只删无据句、不改已接受正文，剥连接词是在改已接受句。重做前先论证这条收益值得。

## 真实模型冒烟 1/3–5（2026-09-21，n=1 诊断非裁决）
run `run_20260921_111040_597004`，490.72 s，`outcome=partial / stop_reason=repair_model_unavailable / judge_status=repaired`，公开稿无提示。修复回路在生产路径上真点着了：repair_goal #1 打回两句「毛利率跌破45%」（`novel_numeric_condition`），模型**整体重写**（改为以 55.25% 为锚的相对条件 + 新增「阈值性质声明」，并自行去掉未点名的其他推演阈值）；宿主未恢复任何拒句，判官降级的两句「东阳光模式」由 v11 检索抬回但**公开稿无引用**。repair_goal #2 要 `track_next_watch`，调用 93 s 后流式失败 → partial 带稿交付。发布上限未触发且**应当**未触发（无未解决审查反馈）。发现（详见原件 README）：① 模型写「裁判变量」（judgment_delta 词汇），`track_contract` 只认「下期关注」，两解析器对「**粗体内联**：①②③」都解不出，`_ITEM_START` 把 `**` 首个 `*` 当项目符号——多余修复轮由此而来（解析器在 main 就有，本分支让它从进收据变成花预算）；② partial 只在 report/gate_receipt，`message.status=transport=completed`，前端 `MessageBubble` 显示「已完成」，webapp 无 `answer_status` 消费者；带稿的 `repair_model_unavailable` 没有公开成因通道；③ 授予 30 s 只是 `urlopen` 单次读超时，非墙钟上限；`_failure_reason` 只进进程内 `_CALL_LEDGER`，原件分不出超时还是网关错；④ 四张个股表键 `stock_ts_code='688256.SH'`，模型 3/4 次传裸码，`finance_query` 不归一也不报格式错，数据到 09-18 都在却答成「本地缺失」；唯一带 `.SH` 的查询打在 `fact_stock_daily_hithink`（最大日 09-08），gap 文案读起来像全局；⑤ 判官注册表只含绑定∪引用证据，东阳光证据在 `outcome.evidence` 里但未绑未引，判官「不存在」相对其投影成立；⑥ 首稿非 FINAL_JSON，+1 调用。

## 真实模型冒烟 2/3–5（2026-09-21，「只用本地资料」型，n=1）
run `run_20260921_120952_719744`（东阳光 9 月量价 vs 板块），169.73 s，`outcome=partial / stop_reason=repair_model_stop / judge_status=repaired / semantic_verifier_stale=true`。`local_only` 上限活体成立（授权面收为 `finance_query/evidence_lookup/memory_lookup/mainline_context` 四工具，10 次调用无越界，v11 因 `no_retriever` 跳过；注意该上限**不含 kb_search/evidence_search**，「本地」= 已审定的纯本地 runner，不是 wiki）。判官 round 1 降级三句真实错误（「换手率始终低于1%」在 9/01–9/04 无数据、「9/17 板块普跌」与 E48/E49 不符、20 日 vs 单日口径混用），修复轮 27 s 内把三句全改对并如实自报 `partial`；`admit_repair_result` 规定无工具修复须自报 completed 才算进展 → `repair_model_stop` → 适配器按终局处理、不对新稿重跑判官、置 `semantic_verifier_stale=true` → **公开稿 = 修复前稿 A，三句错句原样发布**，而 `outcome.draft` 是改好的稿 B（三层稿件比对见 q2 README）。发布上限对此形状盲：judge 记录被当作「已处理」。`completed_without_tool` / `_TERMINAL_REPAIR_STOP_REASONS` / stale 不重核 都在 gitea/main 上；本分支新增的判官原句回传（`semantic_repair_feedback`）让修复轮得以开启，净效果是「多一轮调用、公开文本不变、状态变 partial 且无解释」——这是本分支承诺链（反馈→修订→公开保真）的最后一环断点。其余：裸股票代码 2/2 复现（模型第二批自改 `.SH`）；「当前用户任务未授权历史窗口」挡住 8 月末基准价，模型如实记缺口；`scripts/probe_tool.py` 因 `ALL_TOOLS=tuple(_DEFAULT_TOOL_METADATA)` 含三个非能力工具名（`history_query/read_history_result/save_history_research`）在本分支与 main 上都 `ValueError` 构造失败，`test_probe_tool_arguments.py` 只测参数抓不到。原件 `~/.finance-runtime/adaptive-live-smoke-20260921-q2/`（README / SHA256SUMS / 目录外校验日志）。

## 未验证 / 已知边界
自然模型公开保真、披露重要限制、持续观察后改向未验；脚本模型/SDK runner不代表质量。其他后端、真实费用/上下文窗口、裸代码后缀、监管覆盖、独立Spec/Quality、合流/部署未验。judge off不审gaps；17 warnings非零warning结论。

## 下一步
**冒烟 2 的「修复稿被丢弃」是本分支承诺链的断点，建议先定修法再继续验收**（候选，未做，待用户定）：A 进度判定改看修复目标句是否被改写，不看模型自报状态词；B 终局修复后若 `outcome.draft != verified.outcome.draft`，预算允许就对新稿重跑判官，否则发布新稿并压 partial 带提示，至少不得发布未采纳的旧稿；C 发布上限把 `semantic_verifier_stale && 稿件不一致` 视为未解决。测试矩阵要补「无工具修复 + 模型自报 partial」这一格。

两个参数不需要用户选：生产 `/api/health` 自报 `agent_runtime.model=glm-5.3-flash`；`ASK_SEMANTIC_JUDGE` 在生产进程未设 → `judge_mode.py` 默认 `llm`（关着的是独立判官，启动器 `LLM_JUDGE_API_KEY` 被注释）。冒烟 1/3–5 已跑（上节），剩 2–4 道**未见**题单臂跑 `scripts/compare_adaptive_research.py --arms off`（解释器用主树 `.venv-workbench/bin/python`，树里没有 `.venv-run`）+ `scripts/inspect_adaptive_research.py --project-current-judge-status`，每题另建目录。**每题发前先用 `scripts/probe_tool.py` 走运行时工具路径验数据前提**（带 `.SH` 后缀查 `finance_query`），别直接查库。四道旧题 + 寒武纪已烧成回归题。题里要含一道「只用本地资料」型（`b6df991f` 只有工程验证）。冒烟发现 ①–④ 是候选工单，都涉及 main 上的共用件（`track_contract` / `judgment_delta` 解析器、状态投影与前端、`_post_chat_message_stream` 超时语义、`finance_query` 代码归一），要不要在本分支修、还是另开分支，待用户定；不要顺手改。

合入前另需：在最终 revision 重跑前端与 E2E（`3c30eceb` 之后只改了后端与文档，前端叶子结论可沿用，但 E2E 跑的是后端，最终 revision 上没有 E2E 结论）。不要push、合main、部署、K3、付费外审或删生产，除非明确授权。

## 踩过的坑
`judge_status=repaired`不是单独发布判据；必须结合`sentence_verdicts`阶段/原因。历史`demoted_to_issue`是已完成的保留式语义降级，不是残句。撤线前先固定提交并让临时树指向精确revision；收据不能移绑后续文档tip。

中文连接词表做正文改写必须按「是否兼类」分档，不能统一规则：`但/相反/同理/所以/因此/不过` 既是话语标记也是词素，`但丁/相反的/同理可证/所以说` 会被整片误剥。配套测试若只取顺风样本（连接词后接标点），四条反例一条都红不了——**每条规则至少配一个兄弟措辞反例**，否则测试绿只证明写法一致，不证明规则成立。

结构核验判「缺 X」时，先把交付稿喂给那个槽的解析器复现，再决定是模型没写还是解析器不认：本次「缺 track_next_watch」实为词汇不相认（模型写了裁判变量），修复轮白花。`judge_status=repaired` + 两句 `lifted` 的组合不代表公开稿有引用支撑——抬回不补 E 号。冒烟题的数据前提要经运行时工具路径验，直接查库会漏掉代码格式这层。

`judge_status=repaired` + 有修复轮 ≠ 修复进了公开稿：先比 `outcome.draft` / `semantic_verifier.verified.outcome.draft` / `semantic_verifier.public_answer` 三层，`semantic_verifier_stale=true` 且 outcome 稿与公开稿不同 = 有修复被丢。`probe_tool.py` 当前构造即失败，用 /tmp 包装器把 `ALL_TOOLS` 里三个历史工具名滤掉再跑（q2 README 有法子）；探 `finance_query` 前要先 `eval` 启动器全部 `export`（`FINANCE_WS` 决定库路径，`OPENAI_API_KEY` 由 `FORESIGHT_BUILTIN_LLM_API_KEY` 派生，单独 eval 一行会得到空密钥和 401）。
