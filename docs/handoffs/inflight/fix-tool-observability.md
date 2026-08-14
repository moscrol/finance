# fix/tool-observability — 逐工具可观测性（分支事件 / 工具名 / 耗时）

日期：2026-08-14 ｜ worktree：`/Users/a77/fwp-wt-tool-observability` ｜ 状态：**已提交，未合 main**

## 这个分支做什么

修「没有任何数据源能回答『某个工具成功率多少』」。三个源各瞎一半：
`metrics.tool_calls` 只有总数；事件流丢掉整条分支路径；`traces` 在成功路上
把工具真名藏进 `provider`、把 `capability` 改写成 `agent_loop`。

## 当前状态

- 已提交 `67d5ee6f`（运行时三处）+ `62b1f15c`（审计脚本），工作区干净，未 push、未合 main。
- ① `consume_sub_research` 补发 `branch_tool` 事件（此前分支里的工具一条事件都不发）。
- ② `provider_observability.provider_trace_tool_name()` 做**单一归一化口径**，
  运行时与审计脚本共用，不另立第二份映射。
- ③ `ToolCallResult` 加 `queued_ms` / `elapsed_ms`，**分开记**：前者要调并发度、
  后者要调工具。没测到写 None 不写 0（派发前被拒的调用压根没进线程池）。
  耗时只进 ledger 不进喂模型的 messages。
- `scripts/audit_episode_tool_outcomes.py`：0 档只读审计，按真名出成功率 + 证据消费率。

## 已验证

- 全量 `intelligence/tests + tests` **4819 passed / 4 skipped**；ruff check 通过。
- 新增 6 条测试，含 2 条变异测试（把归一化换回 `trace.capability`、把未测到的耗时
  写成 0，都必须变红）。
- **现场验证 ③**：8801 canary（cwd 指本 worktree）真实跑一题，读出
  `kb_search 排队0.1ms/执行5523ms`、`finance_query 排队2.2ms/执行107ms`；
  `tool_budget_exhausted` 四条如实为 `None/None`。
- 审计脚本复现生产读数：evidence_search 23 次 0%、kb_search 20 次 0%、l3_lookup 100%，
  证据 266→58（22%）。

## 未验证 / 已知边界

- **① `branch_tool` 只有单测，没有现场验证**：验证那一跑没走分支路径
  （`branch_started` 事件数 0）。带分支的多是公司题。
- 未在生产 8792 上验证（它加载 `.finance-runtime/finance-workspace-07af9160a677`）。
- 计时用 `monotonic()`，跨进程不可比；只用于同一 episode 内部归因。

## 下一步

1. **挑一道会触发分支的题（公司题）跑 8801**，确认 `branch_tool` 事件真出得来——
   这是三条里唯一没被现场验证的。
2. 用新埋点结掉悬案：生产 evidence_search 23 次 / kb_search 20 次全 `tool_timeout`，
   但排队实测仅 0.1–2.2ms、kb_search 执行仅 ~5s。**排队饿死与工具慢两个假设都已排除**，
   剩下指向那个实例特有状态——它 10:53 启动、RAG worker 直到 13:53 才出现。
   生产下次重启后用 `elapsed_ms` 复核。

## 踩过的坑

- 我先断言「events 被截断」，**证伪了**：sequence 连续 1..N 一条没丢，是分支路径不埋点。
- 又断言「工具错误率算不出来」，**也证伪了**：traces 里有，只是按 capability 分组时
  成功全被扫进 `agent_loop`。**这类错位比字段缺失更难发现——缺失会露出 None，
  错位会给你一个看着合理的错数。**
