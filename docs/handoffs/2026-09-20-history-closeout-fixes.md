# 2026-09-20 · 历史窗口与代码地图收尾

## 背景

固定基线 `c9bd82ff2e25fe2727347329706f7aeb98444ee8` 已经实现历史原件读取、逐边谱系验证、窗口绑定、授权扩窗、观察终点互斥、并发预占与失败释放。本轮只处理两个已证实的剩余断点，不吸收较新的 main，也不重做已有合同。

第一个断点的真实链是：rank 的排名窗为 2026-01-17..01-22；用户授权 sector trace 把观察终点扩到 01-29；读取该 trace 后，用它作为直接父件继续 stock trace 01-17..01-29。根候选和原始排名窗都未改变，但旧 `WindowSelection.reserve` 把直接父件的 `source_start/source_end` 放进稳定键，因父件从 rank 变成扩窗 trace 而误报 `history_window_selection_conflict`。改回引用旧 rank 原件则成功，证明失败来自稳定身份选错层级。

第二个断点是固定基线全量的唯一失败 `tests/test_code_map.py::test_structure_probe_daily_full`。环境层缺 `uvx` 时，旧 `search_graph` 吞掉 `UvxMissing` 返回空列表；即使补齐 PATH，CRG 对命令词 `daily-full` 只命中 skill 路径，而 Python 实现以 `daily_full` 命名。只补 PATH、删除断言或 skip 都不能修复召回契约。

## 发现与实施顺序

1. 在独占树 `fix/history-closeout-0920` 从固定 c9 创建分支；主树和 `/Users/a77/fwp-wt-history-market-anatomy` 均未写。
2. 复制历史设计探针到外部证据目录，只把 `SOURCE` 从旧只读树改成新树。原件 SHA256=`565abab164323fd671f5c9b0c6e4a59dd1a8f01b9a323b7f8ec188f8dc0e8779`，副本 SHA256=`0e8fc367a1105e26352dcba24f690523103f9f67d1ec505f4e1a665f6b0ff735`；diff 只有这一行。
3. 基线探针复现：`same_root_stock_via_extended_original.error=history_window_selection_conflict`，而 `same_root_stock_via_original_rank.status=success`。
4. 测试先红：加入真实混合父件续查、根/排名窗/观察终点拒绝、合法并发兄弟；3F。把稳定键改成 `root_query_id/root_sample_id/ranking_start/ranking_end` 后转绿。临时撤回该键再次得到 3F，恢复后相邻三组 78P。
5. 代码地图测试先红：4F 分别钉原词+别名派发、稳定去重与总上限、普通查询单派发、`uvx_missing` 与合法零命中分账。
6. 实现保留原词查询，并只对 ASCII 命令式连字符 token 生成一个下划线别名；最多两次 CRG 查询，跨查询按相对 path+symbol 首次命中去重，总命中上限20。没有硬编码任何业务路径或命中。
7. `search_graph` 返回命中和不可用原因；`collect_query` 将缺 `uvx` 标成 `structure.state=unavailable, reason=uvx_missing`，合法空结果仍是 `missing, reason=null`。doors 与 narrative 继续独立呈现。
8. 在提交 `7e5f2ccd` 上用实际 `/Users/a77/.local/bin/uvx` 执行 `code_map.py build --full`，得到 `ready n=30246`；原始结构探针独立执行通过，CLI `query daily-full` 返回 `market_feature_store/cli.py::cmd_daily_full` 等真实 CRG 符号。

## 方案对比

| 问题 | 方案 | 评价 | 结果 |
|---|---|---|---|
| 窗口稳定身份 | 继续用直接父件来源窗 | 合法扩窗后父件窗必变 | 否 |
| 窗口稳定身份 | 从显示文本推断日期 | 绕开已保存谱系且不可审计 | 否 |
| 窗口稳定身份 | 根候选 + 原始排名窗 | 跨父件稳定；直接边与授权仍由既有门验证 | 选定 |
| `daily-full` 召回 | 只给 PATH 加 uvx | 后端可用但仍漏 Python 符号 | 否 |
| `daily-full` 召回 | 特判 market_feature_store | 把预期答案写进查询层，无法迁移 | 否 |
| `daily-full` 召回 | 原词 + 一个机械下划线别名 | 保留原命中，查询和返回均有界 | 选定 |
| 缺后端 | 当作零命中 | 会形成错误的“没有实现”结论 | 否 |
| 缺后端 | 显式 unavailable/reason | 与 doors/narrative 分层一致 | 选定 |

## 验证与收据

证据根：`/Users/a77/.finance-runtime/reviews/research-closeout-20260920/history-closeout-fix/`。

- `probe-baseline-red.log` / `probe-after-fix.log`：同一探针前后结果。
- `history-mutation-red.log`：撤回稳定键后的 3F；最终历史收据 `receipts/final-history/20260920T050817Z-7e5f2ccd.json` 为 78P。
- 代码地图 TDD：`code-map-tests-red.log` 为 4F，`code-map-tests-green.log` 为定向 4P。
- 最终代码地图收据 `receipts/final-code-map/20260920T050831Z-7e5f2ccd.json` 为 42P/3S；三个 skip 是依赖本机图状态的互斥夹具，不包括原始结构探针。
- 实际结构探针收据 `receipts/code-map-actual/20260920T050744Z-7e5f2ccd.json` 为 1P；`code-map-actual-query.json` 保存真实三层查询结果。
- Ruff：四个改动文件通过。未跑整仓和前端，不能外推全叶。

## 后续与禁止事项

先由主协调独立执行 Spec review，再执行 Quality review；只有两关都通过后才进入 PR/集成/main 全叶。禁止直接合 main，禁止调用真实模型或写生产事实。

旧真实四题失败记录属于 `fbd8f2a6`。本枝没有重跑真实四题，因此不能宣称当前真实回答已通过。#791 的成员并集/相似排名正文忠实与独立启动对照组也不属于这两个补丁；窗口绑定测试通过不能替代这些验收。
