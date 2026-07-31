# Start Here — next session (2026-07-31, 下午场)

按冷启动写。§1–§2 先读，§3 是接手的任务，§6 是别重做的。

上一份 `2026-07-31-next-session-start-here.md` 的 §4（明日前瞻）已经做完并验证，
那份现在只剩 §5 的其余条目还有效。

## 1. 环境

```
代码（在这里干活）  /Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17
分支               fix/foresight-required-outputs  ← 不是 main，11 个 commit，未推 origin
数据根             /Users/a77/finance-workspace-private
Python             /Users/a77/finance-workspace-private/.venv-workbench/bin/python
线上运行时         8792 → /Users/a77/finance-workspace-runtime → 028bab57（**仍是旧代码**）
```

两种配置都要跑：

```bash
FINANCE_WS=/Users/a77/finance-workspace-private $PY -m pytest -q -p no:randomly
$PY -m pytest -q -p no:randomly
```

基线：**3,824 passed / 3 skipped / 11 个既有环境失败**（`test_subconscious` ×8、
`test_userspace` ×3）。ruff 在 worktree 根跑 `ruff check .` 是 **165 个 error**，
全部既有（我 `git stash` 对比过 HEAD，数字一模一样）。
> ⚠️ 上一版 handoff 写的「31 个」对不上，别拿它当基线——看到 165 不是你弄坏的。

> ⚠️ 见过一次 12 failed / 3793 passed，代码没动重跑就回到 11 / 3794。那是看板 #14
> 的 flaky episode-citations test，**不是回归**。看到 12 先重跑一次再查。

## 2. 会浪费你时间的三件事

**LLM 是 5 小时滚动配额**，约 15 次 canary 跑光。优先用离线复现台（从 run 目录重建
claim + 正文直接喂门禁），别动不动起 server。

**旁路 server 端口被占会静默测成别人的代码。** uvicorn 只在日志写一行
`address already in use` 就退出，但那个端口上原有的进程照常返 200，smoke 照常出结果。
8799 上常年挂着一个旧 server。起完必须验两件事（`/api/health` 不能用来判断跑的是哪份代码，
它的 `source_revision` 报的是**数据仓**）：

```bash
grep -c "address already in use" <log>          # 必须 0
ps eww <pid> | tr ' ' '\n' | grep ^PYTHONPATH=  # 必须是你的 worktree
```

完整跑法在 agent 记忆 `workbench-canary-side-server`。

**界面会把内部 id 中文化**——`scenario_tree` 显示成 `情景树`、`registry` 显示成 `工具目录`。
用户贴回来的报错要先反译。

**run 目录不在数据根里。** 线上跑出来的 run 落在
`~/.local/share/finance-workbench/users/default/runs/`，
**不是** `finance-workspace-private/intelligence/users/*/runs/`（那里最新的只到 07-10）。
离线复现台要读 0731 的数据就去前者。存的是 `answer_spec.json` / `report.json` /
`trace.jsonl`，**`run.json` 里 `query` 是 `None`**，问题原文得从 `stream.jsonl` 找。
另外 `AnswerSpec` **没有 `from_dict`**，`answer_spec.json` 只能当普通 dict 读。

## 3. 接手这个：P1「拒绝可恢复」

### 现状与目标

现在的形状是二值的：

```
task_fulfillment 判缺 → fail_closed_answer_spec() → 整份答案换成缺口模板
```

官方 Claude Code 的做法是**拒绝作为反馈回灌**：工具被拒时，模型收到的是一条拒绝消息
**作为 tool result**，然后换方法或说明无法继续（`agent-sdk/permissions`；`PermissionDenied`
hook 的官方用例原文就是「告诉模型它可以重试」）。

目标形状：

```
门禁判缺 → 把具体缺口回灌给 composer 做一轮定向补写 → 重新过门禁 → 仍不过才 fail-closed
```

### 接缝已经定位好了

- **改这里**：`intelligence/services/conversation_orchestrator.py:2713`
  —— `result.answer_spec = task_fulfillment.fail_closed_answer_spec(...)`，
  当前是 `if fulfillment.status != "complete":` 直接兜底。
- **照这个抄**：项目里**已经有一个「门禁错误回灌 + 定向修复」的完整实现**：
  - `intelligence/services/llm_refine.py:1407` `claim_binding_revision_user_content()`
  - 调用处 `intelligence/services/ask_synthesis.py:1037`，含
    `claim_binding_revision_ms` / `_reason` 两个遥测字段
  照它的形状写一个 `fulfillment_revision_user_content()` 即可，不用从零设计。
- **回灌的内容现成**：`FulfillmentItem.gap` 已经写清了「为什么没绑上」四种情况
  （`registry 里没有该输出对应的 claim` / `候选 N 条但正文里没出现它们的文本` /
  `候选 N 条且正文已写到但证据未能绑定` / `已绑定但正文缺少该输出的措辞标记`）。
  这是 `66e60dc3` 那次专门加的诊断，正是为了这一步。

### 必须守住的三条

1. **只补一轮。** 官方压缩逻辑连续 3 次失败就熔断（`autoCompact.ts:67-70`）；
   我们这里一轮足够，第二轮仍不过就 fail-closed。不要写成不封顶的循环。
   > 马书 ch27「模式二 渐进式自主」给了更完整的形状：`DENIAL_LIMITS =
   > { maxConsecutive: 3, maxTotal: 20 }`，分类器连续 3 次或累计 20 次拒绝后
   > **永久回退到人工确认**，每次成功调用重置计数器。要点是「自主不是全有或全无，
   > 而是连续光谱，且光谱的每个位置都有安全网」。我们一轮就够，但**计数器要落在
   > 会话级而不是单次调用级**，否则同一个问题反复问会反复烧 LLM 配额。
2. **补写只能用 registry 里已有的事实。** 回灌提示词必须带来源约束，否则等于
   鼓励为了过门禁而编——`_required_outputs_block()` 里那句
   「只能用 claim registry 里的事实来覆盖；registry 里没有支撑的那一条，写成明确的
   缺口或边界，不要为了凑齐而编」可以直接复用。
3. **补写后必须重新过门禁**，不能因为「跑过修复轮」就放行。这是唯一容易写错成
   放宽门禁的地方。

### 怎么验

离线：从 `run_20260731_024144_312047` 重建（三个必需输出判缺的那轮），确认回灌后能补齐。
在线：一次 canary，看 `answer_status` 从 `missing` 变 `complete` 且正文确实补了缺口段。

## 4. 剩下的 plan（P2–P4，按性价比）

| # | 改动 | 依据 |
|---|---|---|
| P2 | **重试/降级体系** | 马书 ch06b 给了完整蓝图，见下 |
| P3 | ~~registry 选择而非截断~~ **降级为 P3'：只补一句「已省略 N 条」** | 实测截断当前不咬人，见下 |
| P4 | **告知模型上下文会被压缩**，别提前收尾 | 官方 PE 给了现成模板，见 `_sources/prompt-engineering/` |

### P2 的蓝图（马书 ch06b «API 通信层» 全章讲这个）

抄这四条，按顺序：

1. ~~**前台/后台减载**~~ ✅ **已做，commit `ee6e2d80`。** CC 的
   `FOREGROUND_529_RETRY_SOURCES` 白名单**只有用户正在等结果的请求才重试过载**；
   摘要、标题、建议、**分类器**一律立即放弃。我们的 judge 就是分类器。
   落地形状：`ask_synthesis._judge_outage_release()` + 新状态
   `judge_outage_released`（在 `_PROMOTABLE_SHADOW_STATUSES` 里）。
   **三条约束照抄 episode 侧已有的 `_transient_failure_candidate`**——
   这个项目里早就有一份同样的实现，别再发明第二套。
   顺带把 `LlmCallLedger` 预算耗尽从 `provider_unavailable` 拆成
   `call_budget_exhausted`（原先对外读起来像「供应商挂了」，其实是我们自己的限额）。
2. ~~**三层错误漏斗**~~ ✅ **已做，commit `3a2cb19d`。** 诊断细、决策粗。
   落地时抓到一个真 bug：产生点 `llm_refine` 写的是「LLM 合成 HTTP {code}」，
   但分类器只判 `"http" in normalized` 就返回 `provider_http_error`，把
   400/401/429/500/529 全塌成一类——于是 HTTP 400（我们自己请求构造错了）
   也走了瞬时故障放行。现在拆成 `provider_rate_limited`（429）/
   `provider_overloaded`（5xx）/ `provider_request_rejected`（4xx 其余，fail-closed）。
   > ⚠️ **这条分界线跟 ch06b 的 `shouldRetry` 不一样，别照抄。** 它问「该不该
   > 重试」（401 该重试，可能是别的进程刷新了 token）；我们问「被审对象是不是
   > 无辜的」（401 之后每次调用都会失败，放行会从例外变成常态）。
3. **双看门狗**：idle 90s（**中断**流）+ stall 30s（**只记日志不中断**）。
   ✅ **日志型那半已做，commit `20ba8caf`**：`llm_stream_telemetry.max_delta_gap_ms`，
   TTFB 不计入。**故意没设阈值**——ch06b 的 30s 来自 Anthropic 的生产数据，
   我们单 phase 预算才 31-45 秒，照抄等于永不触发。**下一步是先看这个字段的
   实测分布，再决定阈值和要不要做中断型那半。**
   > 注意 CC 的 idle 看门狗自己也还在灰度（要 `CLAUDE_ENABLE_STREAM_WATCHDOG`
   > 显式打开）——连 Anthropic 都没默认开中断型的那半。
4. ⚠️ **流转非流式有坑，别照抄。** 真实事故 inc-4258：流式已经开始执行工具、回退到
   非流式重试后**同一个工具执行了两次**。CC 为此加了开关可以禁用整条回退路径。
   我们要做这条，必须先确认回退点之前没有产生过副作用。

其它可复用常量：10 次重试预算 = 500ms×2^(n-1) + 0~25% 抖动（防雷群），总等待约 2.5–3 分钟。

### P3 降级了：我实测了截断，它当前不咬人

10 个 0731 run 里 **2 个**超出 12,000 字符窗口（最大 15,429 字符 / 71 条 claim →
入窗 54、丢弃 17，**丢的全是 `company_table` 的 `company_mapping` / `company_evidence`**）。
但这**两个 run 的 `answer_status` 都是 `complete`**——截断没有造成判缺。

所以这是个**潜在**不对称，不是已发生的故障：

```
门禁    task_fulfillment 看 answer_spec 全集（71 条）
composer 只看 grounded_claim_registry_block(max_chars=12_000)（54 条）
```

→ **建议只做最便宜的那一半**：在 registry 末尾补一行「另有 N 条 claim 未纳入本次窗口」。
马书 ch28「不足四」正是讲这个——CC 大结果截断时会告诉模型「Full output saved to…」，
但作者指出**告知 ≠ 模型会去读**。我们现在连告知都没有，补上是零成本；
上 LLM 选择（Yuker 那条「小模型选≤5 条，精确度优先于召回率」）**不划算**，
它会再加一次串行调用去解决一个还没发生的问题。

> 复现命令在 §8。注意我是从 `answer_spec.json` 重建 registry 量的（`AnswerSpec` 没有
> `from_dict`），排序里少了 query 词加分，所以**丢弃的具体是哪 17 条**可能有出入；
> **总字符数 15,429 > 12,000 是准的**，跟排序无关。

## 5. 本次 session 做完的（11 个 commit）

```
e93b92a1  perf: 长输入在前、问题在最后（官方称最多 +30%）
460fd6f8  docs: 八条修复按两套 harness 原则归位盘点
3c832917  fix: 展开行改绑到自己的公司，而不是删掉
7ff05676  fix: judge 判定按引文定位，不按序号
cf002f25  fix: 通用 harness 不再拦领域层已放行的内容
e5d32e80  fix: gap 在它点名的缺陷解决后停止阻塞
13557fab  fix: 把契约给 composer 看；越界句号不作废整份判定
4abe34ca  fix: 前瞻情景绑定不再只在 agent loop 失败时执行
04ab9ad5  fix: 删句后不留悬空连接词
3e0ee177  fix: 前瞻三个必需输出可完成
```

效果：「你觉得a股明天会怎么走」从 `evidence_gap_fallback`（正文是「请补充数据源或稍后
重试」）变成 `validated_synthesis` / 0 degrades，六个必需输出全部 fulfilled。

## 6. 别重做这些

- **8792 还是旧代码**（028bab57）。本分支未合 main、未推 origin。要上线得走蓝绿切换，
  步骤在 agent 记忆 `workbench-runtime-cutover`。**合 main 必须等用户确认。**
- **美股日期不是 bug**（上一份 handoff §7 已说明，仍然有效）。
- **别削弱门禁换绿灯。** 本轮所有放宽都在通用层（标题措辞、公司名误报、judge 解析），
  领域层（数字/公司/日期是否有出处）一条没动——同一轮回答里 7 条「增加证据外数字」
  全是真的。判据见 agent 记忆 `harness-layer-split`。
- **别迁到 Agent SDK 或 Managed Agents。** 后者托管部署（我们数据在本机 DuckDB 和
  Obsidian vault）。我们在「手写循环 + 自己部署」象限，这个位置是合理的。理由见
  `10_knowledge/claude-code-architecture-manual.md`。

  > **「用 OpenAI Agents SDK 做通用层不是更省事吗」——问过，答案是分层看。**
  > SDK 的重试体系确实比我们强（`agents/retry.py`：`ModelRetryBackoffSettings`
  > 有 initial_delay/max_delay/multiplier/jitter，还有 `retry_policies.http_status()`、
  > `RetryDecision`、hard veto）。**但决定性的事实是：**
  >
  > ```
  > judge/composer/brief 在哪？  ask_synthesis.py → llm_refine.py（裸 urlopen）
  > openai_agents_runtime.py 引用 llm_refine 几次？  0
  > ```
  >
  > 合成层**整个在 agent loop 之外**，换 `AGENT_RUNTIME_BACKEND` 对它零影响，
  > 而本轮九个 bug 全在合成层。SDK 只能补 agent loop 那一半的韧性。
  > 结论：`sdk_glm` 留着（1,732 行适配层已在），将来 loop 层要加韧性再转正；
  > 合成层的韧性必须自己写。app server 同理——FastAPI 本身就是开源框架，
  > 没有「再换一个」的收益。

- **线上跑的不是 OpenAI 任何东西。** 8792 进程无 `AGENT_RUNTIME_BACKEND`
  → 默认 `continuous_glm` → `continuous_turn_adapter.py`（import 里零 `agents`）；
  模型调用是 `urllib.request.urlopen` 打智谱，**连 `openai` python SDK 都没用**。
  `openai-agents==0.18.3` 装了但只在 `sdk_glm`/`sdk_gpt` 下走；`codex_headless`
  被 `benchmark_only=True` + `AGENT_RUNTIME_BENCHMARK_ENABLE=1` 双重关着。

## 7. 参考资料库（遇到难点先检索它）

全部冷存在 `/Users/a77/agent-memory/10_knowledge/`，无需联网。总索引见 agent 记忆
`harness-reference-library`。四类，按证据等级：

> 📌 马书**全 36 章已抓全**（`_sources/harness-engineering/chapters/`，1.2M，无需联网）。
> 按需查的对照表：P1 拒绝可恢复 → ch16（权限六模式/三层管线）、ch27 模式二（拒绝追踪）、
> ch04 模式三（**分层错误级联**：Bash 出错只取消同级 Bash，不动 Read/Grep——
> 这就是「一个输出判缺不该作废整份答案」的通用形式）；
> P2 → ch06b 全章；P3 → ch12（预算三态分区）+ ch28 不足四；
> 提示词措辞 → ch06（六种引导模式）、ch08（工具提示词=行为契约）；
> **ch28 是唯一记录这套设计在哪失败的一章**，动手前先读它对应的那一节。

1. **官方文档**：`_sources/claude-code-docs/`（loop / permissions / hooks / sdk / overview）、
   `_sources/prompt-engineering/claude-prompting-best-practices.md`（59K，`## Agentic systems`
   和 `### Long context prompting` 两节最相关）
2. **设计哲学**：`_sources/harness-engineering/`（马书六原则 + harness-books 十原则）
3. **源码解读（二手）**：`_sources/claude-code-source-reads/`
4. **我们自己的实测**：agent 记忆 `harness-layer-split` 等

**三条纪律**：③ 与马书同源（同一份 v2.1.88 泄露），一致 ≠ 交叉验证；③ 与官方冲突时
以官方为准；引用前确认那一页是否真读过（每份笔记都标了精读范围）。

## 8. 两条值得带走的经验

**先加观测再迭代。** 本轮所有诊断都靠离线复现台（从真实 run 目录重建 claim + 正文
直接喂门禁），一次 LLM 调用都不花，而且能逐字复现线上的 gap 文案。八个 bug 里有六个
是这样定位的。

**测试要能抓住 bug，不只是通过。** 本轮每个修复都做了「回退代码验证测试确实失败」这一步，
抓到两次问题：一次是 fixture 断言错了（前件带未绑定数字、本来就该被删，剥离连接词是对的），
一次是发现 `isinstance(True, int)` 为真导致 `[true]` 一直被当成第 1 句。上一轮的教训
（测试断言了界面显示值而不是生产者写入值）在本轮没有重演。
