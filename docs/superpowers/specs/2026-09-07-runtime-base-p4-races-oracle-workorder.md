# 工单 #31 · 运行底座 P4：竞态目录 + 写序 oracle 正式化 + 防御模式（预立单）

> 母单：#27 `2026-09-07-runtime-base-endstate-design.md` §6.5。前置：P2（#29）合入（`step()` 可单步驱动与 store 是竞态测试的地基）；P3 可并行。
> 分支：`feat/runtime-base-p4-races-oracle`。状态：⏳ 预立单。
> 判据：INV-R6 成立；G10 抛 / 返回总规则落文档并有夹具。

## 范围

1. loop 拆出 `step()` 单步驱动（manual drive）；`intelligence/tests/conformance/races/` 目录表 v1 ≥ 8 条，每条两序、两种合法历史都断言：`cancel vs model_turn 结算`、`cancel vs tool_result 结算`、`cancel vs finish`、`steer vs 模型停下`、`close vs 结算`、`两个 begin_work 同 Handle`、`store.append 失败 vs 内存 ledger`、`restore vs 仍在飞的驱动`。
2. 写序 oracle 从 P2 测试工具升为 `conformance/oracle.py` 公共件（包住 `store.append` 的 spy，与 fake provider / fake tool 的开始事件交错记录）。
3. `docs/runtime/defensive-patterns.md`：从 `docs/prediction-ledger.md` 的 R-* 与 handoff「踩过的坑」提炼「坑 → 规则」，含 G10 总规则：**`runtime/` 内部用异常，跨 `services` 契约边界只返回结构化结果；hooks / sink / 投影一律不抛。**
4. `test_runtime_catalog_fresh` 进 pre-commit（第 12 道）。

## 验收

每条竞态两序各一夹具且断言不同的合法终态；oracle 在 P2 的 Tier A 套件里复用；防御模式文档每条带本仓实例（不抄 dsh 六条）。

## 不做

不引入并发框架；不做 SQLite；不为竞态测试改生产控制流（只暴露 `step()`）。
