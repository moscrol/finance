# 当日盘面路由与出口纪律 Verification

- 日期：2026-08-09
- 分支：`fix/market-routing-default`（基线 `96419ebd`，即已合入 main 的接缝阶梯）
- 范围：当日盘面判定的路由形状、首轮预算借用的测试覆盖、两个工具的行为契约
- 结论：四个提交全部通过聚焦回归与全量对照；**三条原计划前提被实测推翻**，见 §5

## 1. 起因

上一轮把 knevo 的 44 轮工程探针原文落库（`agent-memory/60_dialogues/knevo/2026-08-08-*`，6856 行、110 次工具调用带 input/output），据此提出一批「值得吸收」的改动。本轮逐条核实，其中三条的前提是错的——**能力已存在，或者我们的形式更硬**。

## 2. 路由形状：从 10/18 到 18/18

`is_current_market_query` 初版是单条 `has_time AND has_subject`，两张词表却互相重叠：`主线/盘面/市场结构/成交/涨停` 同时在时间词表和主体词表里，AND 对这五个词**退化成单词命中**。

实测 18 条自然问法（改前）：

| 失败类型 | 例子 | 原因 |
|---|---|---|
| 常用时间词缺席 | 今天板块表现如何 | 时间词表里没有「今天」 |
| 显式日期不算时效信号 | 以 2026-08-07 收盘为准，A股整体市场处于什么状态 | 一个时间词都命中不了 |
| 度量提问被要求配时间词 | 涨停家数多少 | 无时间词直接判 False |
| 今昔对比被整条否掉 | 最近行情和2024年哪段像 | 历史词无条件 `return False` |
| **过度触发** | 如何判断主线候选和噪音 | 词表重叠导致纯方法题拿到行情数据 |

改后判定拆成分层信号（时间 / 主体 / 度量 / 现状 / 前瞻 / 显式日期），历史词只在「没有任何当期时间信号」时才排除，方法类提问先行排除。

**读数：10/18 → 18/18。** 18 条连同「为什么它曾经漏/曾经误触发」一起固化进 `test_evidence_capabilities.py`（探针原在 gitignore 的 `tmp/` 下，注释引用它等于死指针）。

一处顺带发现：`test_comparative_mainline_decision_overrides_single_theme_defaults` **原先是靠这个 bug 通过的**——「未来一个月哪个更可能成为A股主线」命中的是退化后的单词「主线」。词表拆开后它掉了，但它的期望是对的（判断未来主线要以当前主线结构为基线），缺的信号是前瞻时间词，于是补 `_FORWARD_TIME_MARKERS`。

## 3. 关键词表 vs finance-mode：差别不在词选得好

用户的判断（「不如 finance-mode 那些」）成立，但原因不是词表大小，是两个结构性选择：

| | finance-mode | 我们（改前） |
|---|---|---|
| 没命中时默认 | 除三类豁免外都要查，「拿不准默认检索」 | 命中才给，没命中降级 |
| 失效方向 | 多查——浪费预算，有上限 | **少查**——答案看起来完整但底下没数据，代价不封顶 |
| 类别由谁解析 | 语义类别（「出现具体标的」）交给模型 | 表面形式（字符串含「当前」）交给正则 |

可迁移原则：**在开放输入空间上做精确匹配的闸门一定会漏；闸门放出口，入口放宽。** 入口宽的代价有界（浪费预算），出口宽的代价无界（错答案带着自信发出去）。

同时确认了一条便宜的不对称性：**授权 ≠ 调用**。放宽 `allowed_capabilities` 几乎免费（选哪个工具仍由模型自主），真正花预算的是 `mandatory`。而且放宽 allowed 永不触发 `mandatory ⊆ allowed` 那条契约不变量，改动方向与不变量同向。

## 4. 去重：显式日期正则收成单一来源

`task_frame._EXPLICIT_DATE_RE` 早已存在。我最初在 `evidence_capabilities` 复制了一份——两个必须保持一致的正则就是漂移隐患。改为 `task_frame.has_explicit_date()` 单一来源。

`entity_anchor.resolve_entity_anchor` **刻意不接**：它需要 `KnowledgeAdapter`，接进去会让一个纯判定函数带上 IO 依赖，测试也得开始造知识库桩件。而「提到具体标的就该查行情」这条已由度量词覆盖大部分（「茅台现在多少钱」实测通过）。

## 5. 三条被推翻的前提（本轮最重要）

### 5.1 turn 边界预算检查——两样都已在生产

原计划「验证 turn 边界检查以替代 synthesis 预留」。实测：

- 循环本身就在轮次边界求值预算（`agent_episode.py:467`），不在 token 生成中途注入截断；
- 首轮饿死也已有补丁：`_opening_planning_timeout` 向 `synthesis_reserve` 借**超出一次合成所需**的余量，注释里带 run 8792 的现场算术（`26.67s` 低于 provider P50 28s → 三个 run 全 `TimeoutError` → 零 binding → 模板答案；借入后 60s ≥ P95）。

真正缺的是**这条算术零测试覆盖**——全仓只有 1 处测试碰到 `retrieval_deadline_closed`，`_opening_planning_timeout` / `MIN_SYNTHESIS_RESERVE_FLOOR_SECONDS` 无断言。已补 6 条不变量断言（借的是余量不是整段、地板不被侵蚀、非首轮不借、上界仍是 `llm_timeout`）。

### 5.2 `output_review` 已接线——我先前说「没接线」是错的

第一次搜索只用了 `from intelligence.services.output_review import` 一种写法，漏掉 `from intelligence.services import ... output_review` 的模块级导入。实际它在 `ask.py:4135` 已接线，6 项检查（本地数据新鲜度 / 证据分层 / 反证 / 缺口显式化 / 可验证假设 / 弱证据硬写），且 WARN 会回灌做一轮定向修订。

但它**只覆盖 Engine B**：continuous episode 走 `_complete_continuous_turn` 提前 return，`_continuous_answer_coverage` 的 docstring 自己写明了这一点（「returns before the orchestrator's `task_fulfillment` gate」）。这是真实的覆盖缺口，但属于 Phase 1「先量后改」的既有决定，不在本轮动。

### 5.3 重试上限——我们的形式更硬

knevo 的「最多 3 次改写重试」是 skill 文本。我们的对应物是运行期硬拒绝：`episode_tool_batch.py:218` 对 `(tool, normalized_query)` 重复调用直接 `rejected: duplicate_query`，并计入 `metrics.duplicate_queries`；`max_retries_per_skill` 默认 `0`。

模型**不可能**绕过它。因此这条不需要「吸收」，反而是 knevo 承认自己缺的那类 harness 保证。

### 5.4 顺带纠正上一轮对 knevo 的定性

上一轮我说「knevo 在入口硬导、我们只在出口拦」。原文里 knevo 自己否掉了这个说法：

> 目前确实是纯靠 skill 文本约束，没有 harness 层的程序化 guardrail。

它把 T1-T5 检索硬触发明确归入「非 harness 级（可能不遵守）」，自评单轮 95%+，并说「如果你们有 post-generation checker，错误捕获率会比我高一个数量级」。

行为数据侧印证：43 个 assistant 轮里 **9 轮零工具调用**，中位数 1-2 次（其中一轮「沙箱工具测试」打了 30 次调用、105 credits）。真实格局是**它有入口导但是软的，我们有出口拦而且是硬的**。

## 6. 工具行为契约：补齐真实缺口

12 个工具里只有 4 个有行为契约（`market_data` / `l3_lookup` / `web_search` / `news_search`）。缺的两个恰好对应 knevo 点出的两类陷阱：

- `financial_data`：返回**累计口径**（中报=H1、三季报=前三季累计），不做单季还原。依据是 `market_financials.py` 的口径说明；而 block 里那行说明会被 `_NON_EVIDENCE_PREFIXES`（`使用要求：`）过滤掉，模型不一定看得到——所以必须进契约。
- `memory_lookup`：返回的是这位用户的历史先验，**不是市场事实**，不能当证据引用；空命中要写成明确缺口。

严格遵守契约表表头那句「只写验证过的，没有依据的宁可留空」——两条都来自代码实测而非推测。

## 7. 验证命令与读数

```bash
PY=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
$PY -m pytest intelligence/tests/test_evidence_capabilities.py \
  intelligence/tests/test_turn_control_core.py \
  intelligence/tests/test_task_frame.py            # 118 passed
$PY -m pytest intelligence/tests/test_agent_episode.py -k opening_planning  #   6 passed
$PY -m pytest intelligence/tests/test_tool_behavior_contract.py \
  intelligence/tests/test_episode_protocol.py \
  intelligence/tests/test_episode_tools.py         # 176 passed
$PY -m pytest intelligence/tests/test_episode_seam_ladder.py  #  44 passed
$PY -m pytest intelligence/tests                   # 3971 passed / 13 failed
```

**那 13 个失败与本轮无关**，全在 `test_subconscious.py` / `test_userspace.py`。已用 `git stash` + `git checkout HEAD~1 --` 两次回退对照确认：改动不存在时同样失败。

**一条环境教训**：用宿主 `python3` 跑会出现 70 failed 与 `ModuleNotFoundError: No module named 'fastapi'`——那是解释器用错，不是环境缺包。正确解释器是 `.venv-workbench/bin/python`（pre-commit 的 `agent-workspace-facts` hook 每次提交都会打印它）。

## 8. 提交

| revision | 内容 |
|---|---|
| `300cbed6` | 拆开时间信号与主体信号，补齐当日盘面判定的三条入口 |
| `245db33e` | 显式日期正则收成单一来源 |
| `2279aff4` | 钉住首轮向 synthesis reserve 借余量的算术 |
| `871eb48d` | 给 `financial_data` 与 `memory_lookup` 补行为契约 |

均通过 pre-commit（密钥/大文件/冲突/ruff/层级审计 ERROR 0 条）。**未合 main，等确认。**

## 9. 未做与待定

- **Engine A 的出口闸门**（§5.2）：真实缺口，但属 Phase 1「先量后改」的既有决定，需要分布数据才好定策略。
- **入口硬导**：优先级已下调——knevo 那半只有 95%，而我们的祈使句版本已被 `run_20260808_102708` 证伪（槽位、授权、强制指令三样都在，模型仍把 7 次预算全投给市场侧）。真要做只做「结构收窄」形式。
- **`agent-memory` auto-sync**：launchd `com.a77.agent-memory-sync` 每 180 秒跑 `~/bin/agent-memory-sync.sh`，`git add -A` 全量提交并 push `origin/main`。它在 14:24 自动提交了 knevo 原文（`b50db773`）。是否排除 `60_dialogues/` 待用户决定。
- **vault lint 既有 2 条 ERROR**：`knevo-reverse-session-2026-08-07.md` / `knevo-engineering-probes-2026-08-07.md` 缺 `source` 字段，均为 08-08 auto-sync 提交，非本轮引入。
