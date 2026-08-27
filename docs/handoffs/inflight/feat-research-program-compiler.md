# feat/research-program-compiler

## 这个分支做什么

P0-B：输入侧 `ResearchProgram`。`compile_research_program` 是 operators 唯一写入点。market_watch 仍走四袋 pack，字段逐字节回归。不新开第四套 planner，不把 `synthesis_reserve` 做成 program 字段。

## 当前状态

树 `/Users/a77/fwp-wt-research-program-compiler` @ `feat/research-program-compiler`，基线 `gitea/main@e8ed9e11`（含 #354 P0-A）。**未合 main、未切端口。**

| 切片 | 落点 |
|---|---|
| B1 | `research_contract.ResearchProgram` + `compile_research_program` |
| B2 | `bind_research_program`；编排器 market_watch 改调它 |
| B3 | `query_understanding.surface_research_signals` 词面；旧 `_research_operators` 未并词表 |
| B4 | `run_strict_signal_pack` 复用四袋查询，不新写 SQL |
| B5 | prefetch / episode 槽位改读 operators；发酵题时间轴仍要 fermentation 信号 |
| B6 | `program.research-program` 只登 eval 表；生产不 import `capability_switchboard` |

## 未验证 / 已知边界

- 离线夹具绿 ≠ `R-20260824-15`/`-16` confirmed。矿重放 / 改写组未跑。
- 发酵时间轴仍要 `SIGNAL_FERMENTATION`：同一 operator 还承担 forecast 的双红个数序列，不能单靠 operator 开时间轴，否则普通 forecast 会多出「未锚定」袋。
- `question_class` 已是 `market_forecast` 等非盘面题型时，不再用「目前市场结构如何」这种盘面词面补 `catalog.preflight`。否则 adapter 夹具和预测契约会被多塞两个 advisory 槽。
- `required_fact_slots` 并进 episode 契约时是 **advisory**（`required=False`），避免发酵题因新槽变 partial。
- 非 market_watch 且命中 operator 时，`bind_research_program` 会把信号包写入 `supplemental_evidence`。market_watch 路径不写第二份。
- spec v2 全文在另一棵 docs 树，没有并进本支。

## 下一步

1. 定向测 + 棘轮后开 Gitea PR。合 main / 切端口等用户。
2. 不要切 8792/8796，除非用户另说。
3. P1（`theme.research_packet`、ReAct 工具缝）先不动。

## 踩过的坑

- 这支 worktree 跟踪着 `gitea/main`。推送必须 `git push -u gitea feat/research-program-compiler:feat/research-program-compiler`，禁止 `push HEAD`。
- 词面正则放 compiler 会和第二份 operators 并排。词面只许住在 `query_understanding`。

## 已验证

`test_research_program_compiler.py`（唯一写入点 + market_watch 逐字节 + 信号≠operator id + pack + advisory 槽 + 生产不读开关板）+ 既有 dual_red / market_watch / switchboard 回归。全仓 **6292 passed / 13 skipped**（收据 `~/.finance-runtime/test-receipts/20260824T042123Z-e8ed9e11.json`）。
