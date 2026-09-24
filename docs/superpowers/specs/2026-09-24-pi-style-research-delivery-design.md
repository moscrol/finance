# 8792 的 Pi 式研究能力兑现

日期：2026-09-24
分支：`feat/pi-research-loop`
开工基线：`4cc15e703f81`（创建 worktree 时的 gitea/main）。
目标服务：8792；本单授权为设计、分支实施及离线验证，不包含合回 main、上线、扩大其他任务模型预算。
活状态：`docs/handoffs/inflight/feat-pi-research-loop.md`；本文件定义合同，不作为部署状态缓存。

## 1. 用户目标与问题

用户希望 8792 具备当前 Pi 会话那种持续研究能力，并指出底座已经吸收过 Pi/dsh。需要兑现的是行为，不是再次改名或搬一套框架：

> 在授权的数据范围和总预算内，自主选择下一步，读取刚拿到的材料，遇到失败换路，找到反证时修订判断，最后交付有来源、有边界的金融答案。

ReAct 是“推理、行动、观察结果，再决定下一步”的循环。它不是无限循环，也不等于开放宿主 Shell。金融 Harness 是证据、截止日和完成条件的执行层，保留它并不要求研究路径预先写死。

此前对话依据旧树与 08/09 月初文档，把若干现有能力说成待接入。此规格以新基线符号和在途 owner 为准，不沿用这些负面推断。

## 2. 已有成果与依赖

| 面 | 已有实现 / 一手指针 | 本单如何处理 |
| --- | --- | --- |
| Python 连续循环和金融判定分离 | `runtime/agent_episode.py`、`services/research_harness.py`；09-02 解耦 spec | 复用，不新建生产 Loop，不复制领域判定 |
| 参考 Loop | `runtime/harness_reference_loop.py` | 保持验证用途；它不具备生产 Episode 的全部存储、预算与生命周期合同，不能直接替换 |
| 网页检索与取正文 | `research_tool_registry.py` 的 `web_search/web_fetch`；`episode_tools.py` | 定义、装配、授权、菜单可见、实际执行分开验；不声称缺工具，也不借本单放开 local_only |
| 子研究 | `sub_research.py`、`continuous_sub_research.py`、注册表 `sub_research` | 已有，不另造子 Agent；父预算、证据回收和取消沿现有合同 |
| 派生计算 | 注册表 `derived_calculation` | 已有只读沙箱，不等于宿主 bash；是否授权取决于本轮合同；不替 #868 开此能力 |
| 进展提示 | `runtime/research_progress.py`；能力图谱“研究进展账与停滞收口” | 已有换查询、换工具、无增量提示；提示可达不等于模型会遵从，停滞硬收口不在本单默认打开 |
| 中途指令与持久化 | `episode_inbox.py`、`episode_store.py`、现有 conformance R 系列 | 复用既有测试，不另建事件账本；不宣称完整跨进程续跑已认证 |
| 自主研究视角 / 修订公开稿 / 传输截止 | `feat/adaptive-research-loop`，PR #868；09-20 自主视角 spec、INDEX #72/#75/#76 | 有 owner，未合入本基线；本单不重写它的生产文件、不追加其真实模型请求 |
| 真实入口与发布 | `docs/agent-product-door.md`、`TurnOrchestrator`、`ContinuousTurnAdapter` | 最终验收必须穿过 Workbench 入口；只跑 Runtime 的测试不冒充端到端或生产验收 |

2026-09-24 本次只读 `finance-workspace-runtime` 软链指向 `finance-workspace-3b7e473575b0`，与基线不同。这是部署目录线索，不是进程身份、开关、数据就绪或能力验收；未在 8792 发问。

#868 原分支交接仍停在 `e7a6cb412`、131/152。共享项目笔记与新批原件 `~/.finance-runtime/reviews/pr868-glm-qc-20260924-1405/STATE.md` 已推进到候选 `ce2a2713121a`，工程四叶绿，独审在 spec/execute 因交付漏 `complete: true` 被拒收并封存。累计 166/209、剩 43，不足原定完整双轴新批 78；旧批不可重试。额度与后续方案由原 owner 维护，本单不以用户“推进”重置或扩大，也不把未分类的探针失败写成产品缺陷。这是读到的开工快照，后续必须重查原件；自然验收仍未闭合。

## 3. 边界与选择

### 3.1 保持一条生产循环

```text
Workbench / TurnOrchestrator
  -> ContinuousTurnAdapter
  -> GLMAgentRuntime (provider-neutral)
  -> ContinuousAgentEpisode
       -> authorized ResearchToolRegistry / ToolBatchExecutor
       -> FinanceResearchHarness / EvidenceLedger
  -> structural + semantic verification / repair / public projection
```

研究动作由模型选择；准不准执行由工具授权与底座预算决定；观察如何呈现、金融证据和答案是否成立由领域层决定。修订必须回到同一 Episode，不靠宿主拼答案，也不另起一套研究状态真本。

| 方案 | 决定 | 原因与代价 |
| --- | --- | --- |
| 继续现有 Python Episode，补行为合同并接续 #868 | 采用 | 保留已有金融和生命周期合同；要证明真实研究改善，不能以结构测试交差 |
| 把 HarnessReferenceLoop 登记为生产 backend | 本单不做 | 参考机刻意省略生产机制；更少代码不能证明可安全上线 |
| 直接嵌入 Pi/dsh SDK | 本单不做 | 会增加跨语言、会话/预算对账成本；当前没有证据表明必须换引擎 |
| 开宿主 bash / 任意文件 / 任意联网 | 不做 | 用户要研究能力，不是宿主权限；只读沙箱与受控工具才是当前权限边界 |
| 抬预算或关闭金融验证求完成 | 不做 | 改善必须区分取证、调用截止、修订与发布；不能把更多耗时或漏检叫能力提升 |
| 为本题固定工具序或股票池 | 不做 | 测试夹具可固定输入，生产不把夹具写成路径；下一步由新观察驱动 |

## 4. 行为合同

| ID | 可证伪行为 | 验收证据 |
| --- | --- | --- |
| RCH-1 观察驱动追查 | 第一工具给出的新标识/线索可进入下一轮请求，第二工具实际收到它 | Runtime 真实 runner 记录、模型请求中的 tool 消息、最终绑定；换线索时下游实参也变 |
| RCH-2 局部失败换路 | 空结果或单工具失败回到模型，剩余授权与预算允许另一工具继续；失败不算事实 | 先失败后成功的同 Episode 轨迹，错误/空结果可见、成功证据不丢 |
| RCH-3 授权边界 | 已注册但未授权的工具不进菜单，模型强行调用也不能执行；可继续合法研究 | 禁止 runner 的零调用见证和后续合法调用；不是仅查工具名称表 |
| RCH-4 证据终局门 | 真实证据可绑定交付；伪造引用不能因稿件流畅而被放行 | 默认 FinanceResearchHarness 的接受/拒绝对照，不注入放行 Harness |
| RCH-5 有界探索 | 调用槽或绝对截止耗尽、取消到来后不新派研究副作用；保留已得证据与诚实缺口 | 现有预算/取消 conformance，加本单跨多步取证的停止反例；真实传输绝对截止归 #72 |
| RCH-6 修订与公开一致 | 反证/判官反馈后审的是新稿，公开的也是被审过的那份；未完成不能升格 | #868/#76 真实 Workbench 原件、稿件阶段与精确 message/run 身份 |
| RCH-7 用户指定来源 | local_only/material_only 限制贯彻到菜单、工具、子研究、补证、修复 | 原 owner 的来源边界验收，不把本单 mock 工具等同真实来源合规 |
| RCH-8 简单题不被复杂化 | 单一事实已足够时允许直接回答，不强迫多视角、子研究或额外规划轮 | 与复杂题并列的真实样本，既看正确性，也看额外往返与成本 |

RCH-1 到 RCH-5 的离线通过只表示“循环允许并约束了这种行为”；模型替身的判断不是自然模型能力。真实模型是否主动换路、有没有遗漏关键反证，必须另验 RCH-6 到 RCH-8 及真实 RCH-1/2。

## 5. 施工顺序

### P0：本分支立即实施，零真实模型调用

新增 `intelligence/tests/conformance/test_research_chain.py`。复用既有 frame/context/finish 夹具和真实 `GLMAgentRuntime.start()`、默认金融 Harness、ResearchToolRegistry；仅替换模型和数据源。

模型替身根据收到的观察决定后续请求，不能只播放预定工具序。测试覆盖：不同线索的真实参数传递、空结果/异常后改查、越权拒绝后恢复、合法与伪造终局、预算/取消停止。上下文、证据日期、运行开关在夹具内固定，不继承宿主策略；runner 和模型都不联网、不读生产库。

原有符合性测试继续负责平台机制，不为本单复制一套取消、持久化或预算框架。若 P0 暴露生产缺陷，先确认是否归 #868/其他 owner；只有不重叠的最小修复在本分支做，不为得到绿删掉断言。

### P1：接续现有自主研究候选，不并行重造

由 #868 owner 完成当前确切候选的独审/工程欠项；#72 负责传输截止，#75 负责独审，#76 负责真实改稿与自然研究。读取最新交接而非复制本 spec 的开工快照。可先在本任务分支组合候选做离线兼容验证，不能把 main 的绿签给组合，也不能由此越过独审启动 P2。

组合上的 `test_research_chain.py` 显式覆盖 `WORKBENCH_ADAPTIVE_RESEARCH=off/on`，不继承宿主开关。quick 档保持原有观察驱动链；deep 档在开关打开后验证首批观察、一次无工具复核、继续追查与证据绑定，第二步实参仍来自实际观察。无工具菜单可能是复核，也可能是预算收口，模型替身按收到的消息区分；耗尽额度后不插入复核、不重开工具。取消在 quick/deep 档均阻止下一次 runner。启用严格消息对账，确认复核也经过真实 Episode 的事件投影。这是组合机制证据，不是自然模型质量或 #868 独审的替代。

### P2：真实研究兑现

隔离用户目录和旁路服务，固定候选/模型/provider、授权工具、输入资料与预算，走真实 Workbench HTTP 门。样本至少覆盖：多步证据追查、工具失败后改向、反证后修订、简单事实对照。先复用 #76 的题和轨迹工具，不新增相同用途的跑分框架；具体真实请求额度和题目在执行前按原 owner 的授权卡确认。

每题记录：第一次路径分叉、实际获批窗口、工具参数与原件、已知/未知/否定事实区分、核验前后稿件、最终公开稿及状态。不能仅以工具调用更多、计划更长、状态 completed、pytest 通过来签质量提升。

### P3：合入与 8792 上线

固定候选通过仓库要求的完整工程门禁、独立验收及自然研究验收后，分别取得合入与部署确认。用既有 canonical-8792-cutover 流程部署，不就地改快照。切前后核代码身份、配置、数据 readiness、回滚锚与真实入口探针；生产新样本闭合后才能说“8792 已获得本 spec 能力”。

## 6. P0 验收命令与反证

在分支根，使用主树 `.venv-workbench/bin/python`：

```bash
$PY -m pytest -q intelligence/tests/conformance/test_research_chain.py
$PY -m pytest -q intelligence/tests/conformance intelligence/tests/test_glm_agent_runtime.py intelligence/tests/test_research_progress.py
$PY -m ruff check intelligence/tests/conformance/test_research_chain.py
```

定向测试收据不能用 `--require-full-scope` 冒充全量。P0 不修改前端或 Runtime 行为，不取得合入许可；合入前完整门禁另跑。

反证至少覆盖：把模型可见线索改错，RCH-1 应红；把未授权工具漏进菜单，RCH-3 应红；宿主替模型洗掉伪造引用，RCH-4 应红；停止扣调用额度，RCH-5 应红。空结果/异常的恢复另有正向场景，不把菜单泄露反例夸成所有授权层都被绕过。优先用 pytest 的局部 monkeypatch 在测试中构造受控故障，不改其他工作树，也不对生产进程注入。

## 7. 回退与交付口径

P0 只增加 spec、符合性测试和收据，没有运行开关或生产行为要回滚。后续自主视角的回退沿 #868 的默认关闭开关，但其共用修订接线不受该开关全部控制，部署回退必须按精确代码快照，不把关一个开关等同回退整个 PR。

本单交付分四栏报告：离线机制、自然模型、合入、生产部署。没有证据的栏写未验，不把设计继承、定义存在、注册可见或历史上线合成一个“已完成”。
