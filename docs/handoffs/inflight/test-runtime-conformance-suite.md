# 在途交接 · test/runtime-conformance-suite

> **2026-08-29 已合入 main**（PR #504，merge `e7a9a0bd`；独立验收 session 复算读数一致：43p/3s/1xf @`9b49ac0a`，INV-5 codex 阳性对照 strict-xfail 在位，5 后端全进参数表，merge-tree 干净）。
> 批次门禁 @`85e4b1fd`（与 #505 合账）：ruff 绿 + webapp 四连（vitest 70）+ e2e 15P + 全量 7032P/1F/15S/1xf（收据 `20260829T074556Z-85e4b1fd`，checker exit 0）。1F=`test_frozen_thirty` A3，隔离证明非本批（详见台账 2026-08-29 行与占位工单 `2026-08-29-frozen-thirty-kb-state-workorder.md`）。8792 未切（tests+docs 零运行时行为变化），待裁决。

- **工单**：`docs/superpowers/specs/2026-08-29-runtime-conformance-suite-workorder.md`（主树 untracked，随 main 由用户处理）
- **分支状态**：套件已建成并全绿，待验收合并。基线 main@c3514529。
- **交付物**：`intelligence/tests/conformance/`（backends/fixtures/baseline + test_inv1..8 + README）。
- **读数**：`43 passed, 3 skipped, 1 xfailed`（`.venv-workbench/bin/python -m pytest intelligence/tests/conformance/ -q`，2026-08-29，本分支干净树）。ruff 对套件目录全过。
- **验收对照**：
  - 四后端 + dsh_stub 全进参数表，8 个 INV 各一文件 ✅
  - continuous_glm 全绿 ✅
  - INV-5 codex 如预期红、以 strict xfail 入 baseline（阳性对照）✅
  - baseline 唯一条目带原因/出处/日期 ✅
  - 零网络零 LLM；`git status` 仅新增 tests/conformance 与本文档，零生产代码 diff ✅
  - 全量叶子检查未跑：主树有他人在途改动，按 AGENTS.md 约定只跑了 pathspec 范围（套件目录 pytest + ruff）；全量对账留给验收 session 在干净基线上做。
- **执行中校准的两处事实**（已写进测试注释，验收时可对照）：
  1. 预算收工的收据词表后端不同：continuous/sdk 用 `tool_budget_exhausted`/`root_budget_exhausted`，codex/stub 网关用 `research_stage_closed` + finalization 事件——语义同、词表异，是差异不是缺口。
  2. continuous 的 followup 规划轮会向 reserve 借到 20s 合成地板（`_followup_planning_timeout`），INV-3 按「烧穿拿全部剩余 + 残窗借到地板但保住 20s」两个子场景断言，比工单原表述更贴机制。
- **KIT.md 回写**：已在 `~/harness-reference/KIT.md` 审计节追加一行指针（该树当时有他人在途改动 BUILD/PLAYBOOK/TOOLKIT，本次只动 KIT.md 一处、未提交，随该仓下次收口一并入库）。TOOLKIT.md 三问条目按缝普查工单（`2026-08-29-conformance-seam-census-workorder.md`）的资产沉淀节回写，不在本单重复。
- **红线遵守**：pathspec 提交、未合 main、未改生产代码（INV-5 静默跳过登记为 finding 留在 baseline，未顺手修）。
