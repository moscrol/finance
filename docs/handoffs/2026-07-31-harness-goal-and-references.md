# Start Here — harness 优化的目标、进展与参考资料库

> 按冷启动写。**§1 目标**决定后面所有取舍，先读。§2 是环境和会浪费你时间的坑，
> §3 是已经做完的（别重做），§4 是待办，§5 是参考资料库和**怎么对照用**。
>
> 这份取代 `2026-07-31-harness-optimization-start-here.md` 作为总入口；
> 那一份里 §3（P1）和 §4（P2 蓝图）的原始分析仍有价值，改代码前值得回看。

---

## 1. 目标

**把通用 harness 补齐到「不拖领域 harness 后腿」，领域 harness 保持严格。**

这条来自用户自己的判断，是本项目所有 harness 改动的第一原则：

> 通用 harness 要可用，领域 harness 是放大 LLM 能力的那一层。

拆成可判定的两句：

- **通用层（宽容）**：标题措辞、句子编号、解析格式、重试、路由、截断——
  它**无法知道内容对不对**，只能保证没有夹带未绑定的东西。这一层拦错了就是纯损失。
- **领域层（严格）**：数字/公司/日期有没有出处、必需输出有没有覆盖、证据够不够硬——
  这一层是产品价值所在，**一条都不能为了绿灯而放宽**。

判断某个改动该往哪边归：问「这条规则需要理解 A 股才能写吗？」需要就是领域层。

### 为什么这条成立（有实测支撑）

- 本分支所有放宽都在通用层，领域层一条没动；同一轮回答里 7 条「增加证据外数字」
  的告警**全是真的**——领域层不是太严，是通用层没长齐。
- 数据结构里也能看到：`ToolSpec` 的字段是 `capability / cost / freshness /
  query_scope`（全是**证据语义**），而 Claude Code 的 `TOOL_DEFAULTS` 是
  `isReadOnly / isConcurrencySafe / isDestructive`（全是**执行语义**）。
  两边几乎不重叠——我们的领域层比 CC 细，通用层一个字段都没有。

### 不做什么

- **不为了过门禁而放宽门禁。** 这是本项目最容易犯且最贵的错。
- **不迁 Agent SDK / Managed Agents。** 已经查过实据，别再重新论证：

  ```
  线上跑的是什么？   8792 无 AGENT_RUNTIME_BACKEND → 默认 continuous_glm
                    → continuous_turn_adapter.py（import 里零 `agents`）
                    → 模型调用是 urllib.request.urlopen 打智谱
                       （连 openai python SDK 都没用）
  openai-agents 呢？ 装了 0.18.3，有 1,732 行适配层 openai_agents_runtime.py，
                    但要显式 AGENT_RUNTIME_BACKEND=sdk_glm|sdk_gpt 才走
  ```

  **「用 Agents SDK 做通用层不是更省事吗」——分层看。** SDK 的重试体系确实比我们强
  （`agents/retry.py` 有 `ModelRetryBackoffSettings`、`retry_policies.http_status()`、
  `RetryDecision`、hard veto）。但决定性的事实是：

  ```
  judge / composer / brief 在哪？        ask_synthesis.py → llm_refine.py
  openai_agents_runtime.py 引用 llm_refine 几次？   0
  ```

  **合成层整个在 agent loop 之外**，换 backend 对它零影响——而本轮九个 bug 全在合成层。
  SDK 只能补 agent loop 那一半的韧性。结论：`sdk_glm` 留着（适配层已在），
  将来 loop 层要加韧性再转正；合成层的韧性必须自己写。
  app server 同理——FastAPI 本身就是开源框架，没有「再换一个」的收益。

  四象限的完整论证见 `10_knowledge/claude-code-architecture-manual.md`。

---

## 2. 环境与会浪费你时间的坑

```
代码（在这里干活）  /Users/a77/finance-workspace-private/tmp/agent-runtime-seam-fix-69f9cf17
                   ⚠️ 这是独立 clone，不是数据仓的 worktree，且**没有 origin**
分支               fix/foresight-required-outputs（26 commit）→ 已合本地 main = 610feb21
数据根             /Users/a77/finance-workspace-private   ← 有 origin(GitHub)，但在别的分支上
Python             /Users/a77/finance-workspace-private/.venv-workbench/bin/python
线上运行时         8792 → /Users/a77/finance-workspace-runtime → 610feb21（2026-07-31 已切）
run 落盘           ~/.local/share/finance-workbench/users/default/runs/
```

**三个 main 是分叉的，别当成一条线：** 共同祖先是 `origin/main` = `0430d544`；
本 clone 的 main 在它之上有本轮 26 个 commit（现 610feb21），数据仓的 main 另有
自己的 `901dcd7b`。切换用的是本地 fetch，**不需要也没有推 GitHub**。要推之前
先想清楚数据仓那条线怎么并，它还压着 137 个未提交改动。

两种配置都要跑：

```bash
FINANCE_WS=/Users/a77/finance-workspace-private $PY -m pytest -q -p no:randomly
$PY -m pytest -q -p no:randomly
```

**基线：3,875 passed / 3 skipped / 11 个既有环境失败**（`test_subconscious` ×8、
`test_userspace` ×3）。ruff 在 worktree 根跑 `ruff check .` 是 **165 个 error**，
全部既有（`git stash` 对比过 HEAD，数字一模一样）。

> ⚠️ 看到 **12 failed** 先重跑一次——看板 #14 的 flaky episode-citations test。
> 看到 **12 以上**大概率是真回归，先看是哪一条再动手。

### 六个具体的坑

0. **决定加载哪份代码的是进程 cwd，不是 PYTHONPATH。**（2026-07-31 新增，代价最大的一条）
   `python -m uvicorn` 让 `sys.path[0]=''`（cwd）排在 PYTHONPATH 前面，而数据根
   `/Users/a77/finance-workspace-private` 下**就有一个 `intelligence/` 包**。在数据根里
   `cd` 着起 server，加载的是数据仓工作树（当时压着 137 个未提交改动），你指的快照被完全
   无视——**而且下面第 2 条的两条检查全绿**。所以第三条检查是必须的：
   ```bash
   lsof -a -p <pid> -d cwd -Fn | grep '^n' | sed 's/^n//'   # 必须是你的快照
   ```
   同一条机制的推论：cwd 在**启动时**解析符号链接，所以**只切指针不重启完全无效**。
   线上此前一直跑 `30d6471a` 而不是指针指的 `028bab57`，就是这么来的。
1. **LLM 是 5 小时滚动配额**，约 15 次 canary 跑光。优先用离线复现台（从 run 目录
   重建 claim + 正文直接喂门禁），一次 LLM 调用都不花。本轮八个 bug 有六个这样定位。
   判断某个 degraded 是不是自己引入的，别猜——**跑 A/B**：同一问题同一 env，分别打
   合并前后两个快照的旁路 server，比 `trace.jsonl` 里 `synthesize` 那步的 output_summary。
2. **旁路 server 端口被占会静默测成别人的代码。** uvicorn 只写一行
   `address already in use` 就退出，但那个端口原有的进程照常返 200。起完必须验三件事
   （**`/api/health` 不能用来判断跑的是哪份代码**，它的 `source_revision` 报的是数据仓）：
   ```bash
   grep -c "address already in use" <log>          # 必须 0
   ps eww <pid> | tr ' ' '\n' | grep ^PYTHONPATH=  # 必须是你的 worktree
   lsof -a -p <pid> -d cwd -Fn                     # 必须是你的 worktree ← 真正决定的那条
   ```
   8792 的属主是 **launchd 作业 `com.a77.finance-workbench`（KeepAlive）**，
   手工 `kill` + `nohup` 会被它抢走端口、你的进程 bind 失败静默退出。重启要用
   `launchctl kickstart -k "gui/$(id -u)/com.a77.finance-workbench"`。
3. **run 目录不在数据根里**，在 `~/.local/share/finance-workbench/`。
   `run.json` 的 `query` 是 `None`（问题原文在 `stream.jsonl`）；
   `AnswerSpec` **没有 `from_dict`**，`answer_spec.json` 只能当普通 dict 读；
   **fail-closed 之后存下来的 `answer_spec.json` 是投影后的**，registry 里只剩缺口
   通知本身——想回放真实输入要挑 `answer_status=complete` 的 run。
4. **界面会把内部 id 中文化**——`scenario_tree`→`情景树`、`registry`→`工具目录`。
   用户贴回来的报错要先反译。而且**存盘的 report 里也是中文化的**，不只是 UI。
5. **`.finance-runtime/` 已堆了约 180 个快照 × 73M ≈ 13G。** 清理前先
   `git worktree list`，别直接 `rm`。

---

## 3. 已经做完的（26 个 commit + 一个 merge，别重做）

### 第一批：前瞻路径修复（10 个）

`3e0ee177` → `e93b92a1`。效果：「你觉得a股明天会怎么走」从 `evidence_gap_fallback`
（正文是「请补充数据源或稍后重试」）变成 `validated_synthesis` / 0 degrades，
六个必需输出全部 fulfilled，**零模型配置改动**。

最值得记的一条：**评分表从没给模型看过**——`required_outputs` 从未进入 brief/compose
的 prompt，而 `task_fulfillment` 逐条按它打分。这类「信息在系统里但没送到该去的地方」
的 bug，本轮一共抓到**四个**（见下）。

### 第二批：按 harness 六层补通用层（15 个）

| commit | 改动 | 依据 |
|---|---|---|
| `ee6e2d80` | judge 因瞬时故障缺席时降级放行，不再罚被审对象 | ch06b 前台/后台减载 |
| `3a2cb19d` | HTTP 按状态码分类，400 不再当瞬时故障放行 | ch06b 三层漏斗 |
| `77483e89` | 记录相邻 delta 最大间隔（stall 观测，**不设阈值**） | ch06b 双看门狗 |
| `e67c5cad` | **门禁判缺先补写一轮再 fail-closed** | ch04 分层错误级联 |
| `f1485ec2` | registry 超预算时告知模型，不再静默丢弃 | ch28 不足四 |
| `f11d8903` | 工具提示词补行为契约（4 条） | ch08 + ch27 模式六 |
| `3d36c268` | 重试退避改指数+抖动，**次数不变** | ch06b |
| `85a0ec89` | **controller 挂掉时的检索地板漏掉了「A股」** | canary 实测 + ch28 |
| `2ed27ca9` | controller 降级留证：reason 枚举 + 原文进 trace（待办 A） | ch06b 错误漏斗 |
| `3cd94bbd` | 流式已输出后不再回退非流式（待办 D，核实后钉闸） | ch06b inc-4258 |

### 六层现状（ch30 的框架）

| 层 | 差距 | 状态 |
|---|---|---|
| L1 提示词 | 工具只有描述没有契约 | 机制已补，**7 个工具的契约还空着**（见 §4） |
| L2 上下文 | 单轮问答，压缩大部分 N/A；静默截断 | ✅ 已补告知 |
| L3 工具 | 全串行，无并发分区 | 未做（性能非正确性） |
| L4 闸门 | 二态（过／整份换缺口模板） | ✅ 已改成可恢复 |
| L5 韧性 | 只有 `for attempt in range(2)` | ✅ 减载/分类/退避/stall 观测已做 |
| L6 可观测 | **我们比 CC 强**（离线复现台 CC 没有） | 只差 controller 那条（见 §4） |

### 四条「信息在系统里但没送到该去的地方」

这是本轮反复出现的同一个形状，值得当成排查模板：

| # | 信息在哪 | 该送到哪 | commit |
|---|---|---|---|
| 1 | `required_outputs`（门禁逐条按它打分） | brief / compose 的 prompt | `13557fab` |
| 2 | `FulfillmentItem.gap`（四种「为什么没绑上」的诊断） | 回灌给 composer 补写 | `e67c5cad` |
| 3 | `evidence_capabilities` 的工具路由表 | 工具描述里的行为契约 | `f11d8903` |
| 4 | `required_outputs`（frame 点名了 `scenario_tree`） | 检索地板的谓词 | `85a0ec89` |

**下次遇到「模型怎么这么笨」，先查它到底看没看到那份信息。**

### 切换（2026-07-31 已完成，用户明确批准）

```
合并          fix/foresight-required-outputs → 本地 main = 610feb21（--no-ff）
promote ref   refs/runtime/promote-2026-07-31b  ← 新 ref，旧的留作回滚参照
新快照        /Users/a77/.finance-runtime/finance-workspace-610feb21…（74M）
canary        8816 验过（三条检查都过）；8817 跑合并前 31af5663 做 A/B
指针          已切 → 610feb21，launchctl kickstart 重启，cwd 已确认是新快照
线上验收      smoke completed，secret_scan 0 命中，controller 新字段已进 trace
```

**回滚**：`ln -sfn /Users/a77/.finance-runtime/finance-workspace-028bab57… \
/Users/a77/finance-workspace-runtime && launchctl kickstart -k \
"gui/$(id -u)/com.a77.finance-workbench"`。旧快照不要删。
（注：切换前**实际在跑**的是 `30d6471a`，不是指针指的 `028bab57`——见坑 0。）

**未做：推 GitHub。** 本 clone 没有 origin；有 origin 的数据仓在
`fix/degrade-disclosure` 上、压着 137 个未提交改动，且它的 main 和本 clone 的 main
已从 `origin/main` 分叉。推上去数据仓那条线会变成 diverged，得先决定怎么并。
切换不依赖它。

步骤细节见 agent 记忆 `workbench-runtime-cutover`，旁路验证见
`workbench-canary-side-server`（两份都已按本轮实测改写）。

---

## 4. 待办（按性价比排序）

### ~~A. controller 失败的 reason 被丢弃~~ —— ✅ 已做（2ed27ca9）

`TurnDecision` 加了 `llm_failure_reason`（枚举）+ `llm_failure_detail`（原文截断 200），
解析失败单独给 `unparsable_response`；分类器下沉到 `llm_refine.stable_llm_fallback_reason`
（它解析的字符串就是那边产出的）。**没有**顺手补分类器盲区——它同时是 judge 的
fail-closed 闸门，多认一个瞬时原因等于为观测放宽严格层。线上 trace 已确认有这两个字段。

<details><summary>原始问题描述</summary>

`turn_controller.py:1015`：

```python
content, _provider, _reason = complete(...)   # ← 诊断在 _reason 里，被丢进下划线
except Exception:
    content = None                            # ← 裸 except，日志零输出
```

线上 canary 实测：controller 失败 → 兜底成 chat 车道 → 用户拿到「我没办法预测」，
而 trace 里只有一句「Controller 不可用」。**至今说不出那次是超时、限流还是 HTTP 错。**

修法照抄本轮给 judge 做的：`_stable_llm_fallback_reason()` 已经能把 reason 变成枚举
（`timeout` / `provider_rate_limited` / `provider_overloaded` /
`provider_request_rejected` / `call_budget_exhausted` / …），落进 trace 即可。
零行为变化，改动很小。

</details>

### G. synthesize 报降级却说不出原因 —— 新增，和 A 同一个形状

线上实测（2026-07-31，合并前后 A/B 一致，**不是本轮引入的**）：同一次 run 里

```
llm_budget  : 本轮 LLM 调用 4 次（失败 0 次），其中 caller=synthesis 成功 6435ms
synthesize  : status=fallback, fallback_reason=None, stream={}
smoke model : used=False, provider=None
```

`status` 的定义是 `"validated" if result.synthesis is not None else "fallback"`
（`conversation_orchestrator.py:2637`）——所以它说的是「synthesis 是 None」，
但**为什么是 None 没人记**。LLM 明明成功了，答案元数据却丢了 provider/model。

先查 `result.prepared_synthesis_messages` 为空时是不是整段被跳过（跳过和失败是两回事，
现在混成同一个 `fallback`）。修法同 A：给「跳过」和「失败」各自的枚举，别共用一个 None。

### B. 剩下 7 个工具的行为契约 —— 等实测依据

`research_tool_registry._TOOL_CONTRACTS` 已填 4 个（`market_data` / `l3_lookup` /
`web_search` / `news_search`），全部有实测依据或复述 CLAUDE.md 红线。
剩下 7 个（`finance_query` / `evidence_search` / `kb_search` / `graph_lookup` /
`evidence_lookup` / `financial_data` / `mainline_context`）**空着是对的**——
用户已决定「先跑一阵再说」，等这 4 条在线上验证有效、并积累新的失败模式再补。

写的时候每条回答三个问题：何时该用它 / 结果怎么读容易错 / 何时该换别的工具。
**没依据宁可留空，编一句比不写更糟。**

### C. stall 阈值 —— 阻塞在跑量

`llm_stream_telemetry.max_delta_gap_ms` 已在采集但还没数据。攒够样本看分布再定阈值，
以及要不要做 idle 中断型那半。

> ch06b 的 `STALL_THRESHOLD_MS = 30_000` **不要照抄**：那来自 Anthropic 的生产数据，
> 我们单个 phase 预算才 31–45 秒，抄了等于永不触发——比不做更糟，因为会让人以为
> 已经有 stall 检测了。测试里钉了一条 `test_no_threshold_is_hardcoded` 防这件事。
> 另注：**CC 自己的 idle 看门狗也还在灰度**（要 `CLAUDE_ENABLE_STREAM_WATCHDOG`）。

### ~~D. 流式转非流式~~ —— ✅ 已核实并钉闸（3cd94bbd）

ch06b 记录了真实事故 **inc-4258**：流式已经开始执行工具、回退到非流式重试后
**同一个工具执行了两次**。CC 为此加了开关可禁用整条回退路径。

**核实结论：那个形状在我们这儿不成立**（三条实据）：

1. 全仓只有一处 `"stream": True`（`llm_refine._post_chat_stream_raw`），它是合成调用、
   **不带工具**；带工具的 `chat_with_tools` 走非流式的 `_post_chat_message`。
2. 两条回退非流式的路径触发条件都在首个 delta 之前：`LLMStreamingUnsupported` 只在
   chunks 为空时抛，`HTTPError` 只由 `urlopen` 在响应头阶段抛。
3. 流开起来之后 urllib 抛的是 IncompleteRead 那一类，落到通用 except 直接降级，
   根本不进回退分支。

既然当前触发不了就把不变量钉住而不是留在脑子里：回退前先看 `streamed_chars`，非零
就降级为模板（`_STREAM_FALLBACK_BLOCKED`）。零行为变化，防的是以后有人在流循环里
加重试。测试摘掉闸门就红、装上就绿（验证过）。

### E. 工具并发分区 —— 可延后

工具执行全串行（`continuous_turn_adapter` / `research_tool_registry` 里零
`ThreadPool`/`gather`）。ch04 的贪心合并分区：连续同类合并成并发批次，
`isConcurrencySafe` 默认 `false`（fail-closed）。
**前置**：`ToolSpec` 目前没有任何执行语义字段，要先补才谈得上分区。

### F. 运维

- ~~蓝绿切换~~ ✅ 2026-07-31 已切到 610feb21（见 §3「切换」）
- 推 GitHub：**未做**，三个 main 已分叉 + 数据仓 137 个未提交改动，需先定并法（见 §2）
- 清理 `.finance-runtime` 约 13G（现 106 个快照）：**未做，属删除操作没动**。
  清理前先 `git worktree list`，别直接 `rm`；线上在用的和回滚要用的两个快照必须留

---

## 5. 参考资料库：七份信息源

**全部冷存在本地，无需联网。** 总索引也在 agent 记忆 `harness-reference-library`。

根目录：`/Users/a77/agent-memory/10_knowledge/`

### 清单与地址

| # | 来源 | 落盘位置 | 体量 |
|---|---|---|---|
| ① | **马书**《驾驭工程：从 Claude Code 到 AI Coding》<br>`zhanghandong.github.io/harness-engineering-from-cc-to-ai-coding` | `_sources/harness-engineering/chapters/`（**全 36 章**）<br>+ `mashu-ch25-six-principles.md`、`mashu-toc-and-preface.md` | 1.3M |
| ② | **harness-books**（十原则）<br>`github.com/wquguru/harness-books` | `_sources/harness-engineering/harness-books-ch9-ten-principles.md`<br>`harness-books-readme-and-toc.md` | — |
| ③ | **Claude Code / Agent SDK 官方文档** | `_sources/claude-code-docs/`<br>`loop.md` `permissions.md` `hooks.md` `sdk.md` `overview.md` | 92K |
| ④ | **官方 Prompt Engineering** | `_sources/prompt-engineering/claude-prompting-best-practices.md`（59K）<br>`overview.md` | 64K |
| ⑤ | mal_shaik 源码解读 9 条 | `_sources/claude-code-source-reads/mal_shaik-9-takeaways.md` | |
| ⑥ | 陈成：sourcemap 泄露始末 | `_sources/claude-code-source-reads/chencheng-sourcemap-leak.md` | 28K |
| ⑦ | YukerX 源码走读（**全文**，用户粘贴提供） | `_sources/claude-code-source-reads/yuker-source-walkthrough.md` | |

自己整理的两份手册（读这两份比读原文快）：

- `claude-code-architecture-manual.md` — harness/deployment 四象限 + 与自研 workbench 的差距表
- `harness-engineering-principles.md` — 马书六原则 + harness-books 十原则

### 怎么对照用：按问题查，不要通读

**遇到难点先检索这里，看有没有现成解法，再自己想。** 对照表：

| 你在解决的问题 | 去看 |
|---|---|
| 重试 / 降级 / 超时 / 流卡住 | ①`chapters/ch06b.md` **全章**，最实用的一章 |
| 门禁太硬、一个错误作废整份产出 | ①`ch04.md` 模式三分层错误级联、`ch27.md` 模式二渐进式自主 |
| 权限 / 拒绝该怎么回灌 | ③`permissions.md`、①`ch16.md`（六模式+三层管线）、`ch17.md`（分类器） |
| 上下文预算 / 大结果怎么处理 | ①`ch12.md`（两级预算+三态分区）、`ch10.md`、`ch28.md` 不足四 |
| 提示词措辞怎么写才被遵守 | ①`ch06.md`（六种引导模式）、`ch08.md`（工具提示词=行为契约） |
| 长上下文 / 输入顺序 | ④`claude-prompting-best-practices.md` → `### Long context prompting` |
| 压缩 / 长会话 | ①`ch09.md`（阈值推导+熔断）、`ch10.md`（压缩后文件恢复） |
| 记忆系统 | ①`ch24.md`、⑦（**用小模型选记忆，≤5 条，精确度优先于召回率**） |
| 多 agent / 子代理 | ①`ch20.md` `ch20b.md` `ch20c.md`、⑦（反递归提示词） |
| 缓存 / 成本 | ①`ch13.md` `ch14.md` `ch15.md`、`ch05.md`（缓存边界） |
| 技能 / 插件 | ①`ch22.md` `ch22b.md` |
| 安全 / 提示注入 | ①`ch17b.md`、`ch18b.md`（沙箱） |
| **这套设计在哪失败** | ①`ch28.md` — **动手前先读它对应的那一节** |
| 想把模式搬到自己的 agent | ①`ch30.md`（六层框架，本文 §3 的表就用它） |

### 检索命令（章节页带 75 行全书目录，已剥掉；正文里代码块很长）

```bash
K=/Users/a77/agent-memory/10_knowledge/_sources/harness-engineering/chapters

# 1. 按关键词定位在哪一章（最常用的入口）
grep -ln "熔断\|circuit" $K/*.md
grep -n "thundering herd\|雷群" $K/*.md | head

# 2. 看某章骨架，决定要不要读全文
grep -E "^#{2,3} \[" $K/ch06b.md | sed 's/\](.*//; s/^#* \[//'

# 3. 读正文但把长代码块压掉（不然一章 40K 字符全是 TS 源码）
cat > /tmp/cond.awk <<'AWK'
/^```/ { infence = !infence; if (infence) { n=0 }; print; next }
infence { n++; if (n<=8) print; else if (n==9) print "    …（代码略）"; next }
{ print }
AWK
awk -f /tmp/cond.awk $K/ch06b.md | grep -v "^$" | sed 's|(http[^)]*)||g'

# 4. 只要「模式提炼」那一节（每章末尾的可复用结论）
#    注意小节号不统一：有的是「## 模式提炼」，有的是「## 4.8 模式提炼」，
#    还有的叫「小结」——所以按关键词截而不是按标题层级。
awk '/模式提炼|本章小结|[0-9] 小结/,0' $K/ch04.md | awk -f /tmp/cond.awk | head -40
```

> ⚠️ 章节页正文里的标题带 markdown 链接（`## [4.8 模式提炼](…)`），
> 按 `^## 模式提炼` 这种精确前缀匹配会**静默匹配不到**。用 `grep -n "模式提炼"`
> 先看一眼实际长什么样再截。

### 用它的正确姿势：先查再想，但**先算量纲**

本轮四次真正用上资料库，形状都一样——**它给形状，我们给量纲**：

| 从资料拿到的 | 我们自己算的 | 结果 |
|---|---|---|
| 「分类器失败该减载不该重试」 | judge 就是分类器 | 直接抄 → `ee6e2d80` |
| 「诊断细决策粗，三层漏斗」 | 我们的 reason 是中文文案，HTTP 全塌成一类 | 抄形状，发现真 bug → `3a2cb19d` |
| 「stall 阈值 30s」 | 我们单 phase 才 31–45 秒 | **不抄常量**，只采数据 → `77483e89` |
| 「10 次重试预算」 | 我们是 5 小时滚动配额 | **只抄退避不抄次数** → `3d36c268` |

### 五条纪律（血的教训）

1. **⑤⑥⑦ 和马书是同一份泄露源码（v2.1.88）被读了两遍**，不是独立信源。
   两者一致 **≠** 交叉验证。
2. **二手与官方冲突时以官方为准。** 已发现一处：mal_shaik 说「5 个 subagent ≈ 1 个
   成本，都命中 prompt cache」——官方 prompt-caching 文档明确写「缓存要等第一个响应
   开始流式输出后才可读，N 个前缀相同的并行请求全部全价」。只在**错开发起**时成立。
3. **常量不要照抄，先算我们自己的量纲。** 已踩两次：
   - ch06b 的 stall 阈值 30s vs 我们单 phase 预算 31–45 秒 → 抄了永不触发
   - ch06b 的 10 次重试预算（CLI 场景）vs 我们 5 小时滚动配额 → 只抄退避不抄次数
4. **同名不同题，别照抄结论。** ch06b 的 `shouldRetry` 问「该不该重试」（401 该重试，
   可能是别的进程刷新了 token）；我们的门禁问「被审对象是不是无辜的」（401 之后每次
   都会失败，放行会从例外变成常态）。**同一个状态码，相反的答案。**
5. **引用前确认那一页是否真读过。** 每份笔记都标了精读范围。

---

## 6. 三条方法论（本轮反复被验证）

**先加观测再迭代。** 本轮所有诊断都靠离线复现台，一次 LLM 调用都不花，而且能逐字
复现线上的 gap 文案。八个 bug 有六个是这样定位的。没有观测就别急着定阈值——
stall 那条就是「先采数据、不设阈值」。

**测试要能抓住 bug，不只是通过。** 每个修复都做「回退代码验证测试确实失败」这一步。
本轮它抓到的不只是功能 bug，还有一次**无法被测试区分的冗余**（两道守卫守同一件事，
去掉任一道测试都还是绿的——删掉冗余那道之后回退才能被抓住）。

**边界值要单独想一遍。** 本轮两次被**既有测试**抓住，两次都是边界：
一次是 registry 预算刚好等于一行（告知行挤掉了最后一条证据），
一次是把「所有 frame 都有的默认值」当成了信号（「给我讲个笑话」被拖进研究车道）。
自己写的测试全绿，因为只测了中间值。
