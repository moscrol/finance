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

基线：**3,794 passed / 3 skipped / 11 个既有环境失败**（`test_subconscious` ×8、
`test_userspace` ×3）。ruff 树内 31 个 error 全是既有的。

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
| P2 | **重试/降级体系**：judge 挂了降级而不是罚被审对象、流卡住转非流式 | 源码解读：Opus 3×529 自动降 Sonnet、90s 空闲看门狗、persistent 模式无限重试 |
| P3 | **registry 选择而非截断** | 见下，这条被新读到的材料改写了 |
| P4 | **告知模型上下文会被压缩**，别提前收尾 | 官方 PE 给了现成模板，见 `_sources/prompt-engineering/` |

### P3 被改写了，注意

原方案是「大 registry 落盘 + 8KB 预览」（抄 Claude Code 的大工具结果处理）。
但 Yuker 那篇揭示了一个**更贴切的做法**：Claude Code 的记忆检索**不是截断，是选择**
—— 用另一个小模型扫所有记忆文件的标题和描述，选出**最多 5 条**，再把完整内容注入，
策略明写「**精确度优先于召回率**，宁可漏掉一个可能有用的，也不塞进一个不相关的污染上下文」。

我们现在是 `_grounded_registry_priority()` 排序 + 12,000 字符预算截断——**排序后截断**，
不是选择。要不要改成 LLM 选择需要权衡：它会**再加一次串行 LLM 调用**，而 P2 正在
解决「串行调用过多」。**建议先做 P2，再回头判断 P3。**

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
- **别迁到 Agent SDK 或 Managed Agents。** 前者绑 Claude 模型 + Node/Python 运行时
  （我们跑 GLM），后者托管部署（我们数据在本机 DuckDB 和 Obsidian vault）。
  我们在「手写循环 + 自己部署」象限，这个位置是合理的。理由见
  `10_knowledge/claude-code-architecture-manual.md`。

## 7. 参考资料库（遇到难点先检索它）

全部冷存在 `/Users/a77/agent-memory/10_knowledge/`，无需联网。总索引见 agent 记忆
`harness-reference-library`。四类，按证据等级：

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
