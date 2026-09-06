# 在途交接 · feat/sub-research-tool

## 这个分支做什么
把既有 `SubResearchCoordinator` 包成模型可点的工具 `sub_research`（spec `2026-09-03-subagent-tool-design.md` §2–§6）：抄 dsh `tool-subagent` 的形状（前台同步、深度 1、失败保留部分产物），账本用我们的——分支证据经父账本 `branch_sink` 进账、hash 由父账本铸，模型拿到带 E 号的证据条目，结论只能绑证据不能绑分支总结。前置「deep 不可达」已被 sol@57244 + max 档（#608）解掉。

## 决策与被否方案
- runner 在 `runtime` 层按 episode 绑、`services` 的 `build_episode_registry` 没 runner 不挂 / 否装配层放占位 runner 运行时报错 / 没源不挂（spec §5）；审计脚本把它与 `memory_lookup` 同列条件装配。
- 分支 deadline 收进本批工具窗 ×0.9 / 否用 episode deadline / 批执行器等的是窗，超了记 `tool_timeout` 线程照跑，分支会在父臂走掉后还往账本写。
- 分支事件在 runner 线程里记（`_EpisodeLedger` 有 RLock），带 `origin=tool` / 否只进 telemetry / 事件流消费者不该区分分支是 PLAN 批的还是模型点的。
- `_ContextRef` 让 runner 读升档后的 context / 否闭包捕获起步 context / standard 起步→PLAN 升 deep 后再点工具会拿到旧档位被拒。
- 协调器档位门 `== deep` → `∈ {deep, max}` / 否让 max 也叫 deep / max 起步的 run 会永远 `deep_mode_required`。
- 不做后台 / 可续接 / 嵌套（spec §2 表）。

## 当前状态
commit `9332d495`，13 新测试 + 3 变异各击杀 1；pre-commit 11 道过；工具可达性审计 14 声明 / 12 无条件 / 2 条件。**未跑全量门禁、未开 PR**——等 8792 上的 D 组 max 形状批跑（`~/.finance-runtime/max-shape-20260907/`）结束再跑，避免全量测试拖慢批跑的耗时读数。

## 未验证 / 已知边界
- spec §6 第 7 条 live（deep/max 档一题两臂、`sub_research` 被点、分支证据进 bindings）未跑，要等切流。
- sol 会不会主动点这个工具未知：两轮探针都没交 PLAN，也没点过它；若长期零调用，考虑在契约里写清「什么题型该拆」，不是加规则强推。
- 分支并发 ×3 与批执行器全局 8 worker 的争用（`episode_tool_batch.py:131` 注释）在 max 档每批帽 8 下未量。
- `on_result` 在 runner 线程记事件：与主线程的 durable 序号交错是 RLock 保证的，事件顺序是 `model_turn → branch_* → tool_request → tool_result`（测试已按此断言）。

## 下一步
1. 批跑结束 → `run_main_gate.sh --baseline 20260906T162018Z-0b9a115d.json`（或更新的 main 收据）→ PR → 合 → 快照 → 切 8792 → 三项验证。
2. live：挑一道天然可拆的题（如「长电科技 vs 通富微电 先进封装进展对比」）跑一次，看 `sub_research` 被点否、分支证据进 bindings 否。
3. 若 sol 不点：先量 `tool_hunger` 与菜单可见性，再谈提示词。

## 踩过的坑
- 参数 schema 经 `_freeze_json` 后 list 变 tuple，测试比较用 `tuple(...)`。
- 无 env 保险丝时 standard 档派生工具窗 70s ≥ 60，`sub_research` 不会被藏——藏的对照要用 quick 档。
- 装饰器与新插入的类之间：把 `@dataclass` 留给原来的类，别让它落到新类头上。

## 已验证
`test_sub_research_tool.py` 13 绿；`test_sub_research` / `test_agent_episode` / `test_episode_tool_batch` / `test_tool_contract_gate` / `test_episode_projection` / `test_harness_reference_loop` / `test_research_harness` / `test_episode_factory` / `test_capability_max_tier` / `test_tier_promotion` 合计 288 绿。
