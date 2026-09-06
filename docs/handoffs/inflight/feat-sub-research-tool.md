# 在途交接 · feat/sub-research-tool

## 这个分支做什么
把既有 `SubResearchCoordinator` 包成模型可点的工具 `sub_research`（spec `2026-09-03-subagent-tool-design.md` §2–§6）：抄 dsh `tool-subagent` 的形状（前台同步、深度 1、失败保留部分产物），账本用我们的——分支证据经父账本 `branch_sink` 进账、hash 由父账本铸，结论只能绑证据不能绑分支总结。前置「deep 不可达」已被 sol@57244 + max 档（#608）解掉。

## 决策与被否方案
- runner 在 `runtime` 层按 episode 绑、`build_episode_registry` 没 runner 不挂 / 否占位 runner 运行时报错 / 没源不挂（spec §5）；审计脚本把它与 `memory_lookup` 同列条件装配。
- 分支 deadline 收进本批工具窗 ×0.9 / 否用 episode deadline / 批执行器等的是窗，超了记 `tool_timeout` 线程照跑。
- 分支事件在 runner 线程里记（`_EpisodeLedger` 有 RLock），带 `origin=tool` / 否只进 telemetry。
- `_ContextRef` 让 runner 读升档后的 context / 否闭包捕获起步 context / 升 deep 后再点会拿旧档位被拒。
- 协调器档位门 `== deep` → `∈ {deep, max}` / 否则 max 起步永远 `deep_mode_required`。
- 不做后台 / 可续接 / 嵌套。

## 当前状态
commit `9332d495` + docs；13 新测试 + 3 变异各击杀 1；pre-commit 11 道过；可达性审计 14 声明 / 12 无条件 / 2 条件。**未跑全量门禁、未开 PR**——等 8792 上 D 组 max 形状批跑（`~/.finance-runtime/max-shape-20260907/`）结束再跑，免得全量测试拖慢耗时读数。

## 未验证 / 已知边界
- spec §6 第 7 条 live（工具被点、分支证据进 bindings）要等切流。
- sol 会不会主动点它未知：两轮探针都没交 PLAN 也没点过；长期零调用先量 `tool_hunger` 与菜单可见性，不加规则强推。
- 分支 ×3 与全局 8 worker 的争用在 max 档每批帽 8 下未量。

## 下一步
1. 批跑结束 → `run_main_gate.sh --baseline <main 最新收据>` → PR → 合 → 快照 → 切 8792 → 三项验证。
2. live：挑一道天然可拆的题（两家封测厂先进封装对比）看 `sub_research` 被点否。

## 踩过的坑
- 参数 schema 经 `_freeze_json` 后 list 变 tuple，测试用 `tuple(...)` 比。
- 无 env 保险丝时 standard 派生工具窗 70s ≥ 60，不会藏 `sub_research`；藏的对照用 quick 档。
- 插类别插在 `@dataclass` 与原类之间。

## 已验证
`test_sub_research_tool.py` 13 绿；相关十个测试文件合计 288 绿。
