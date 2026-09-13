# feat/judgment-maintenance-01 · 2026-09-13 · 研究进化批次 01「判断持续维护」engineering_complete

**一句话**：spec 01 的四步（合同与夹具 / 差分与条件 / 动作归约 / 只读集成）全部落在 `intelligence/services/judgment_maintenance/`（纯函数、无 IO），
86 例新测试 + 119 例旧读取器回归全绿，7 处突变全红；持久化 / API / UI 归 06，本轨没有白名单外改动。

**读什么**：进度与决定 `docs/superpowers/plans/2026-09-13-research-evolution/01/PROGRESS.md`；交 06 的接线诉求 `…/01/BLOCKED.md`；
spec 与总合同在分支 `docs/river-next-specs`（工作树 `/Users/a77/fwp-wt-river-next-specs-0913`），**未合入 main**。

**三个入口**（`from intelligence.services import judgment_maintenance as jm`）：
`jm.assess(owner_user_id, as_of, knowledge_cutoff, bindings, evidence_versions, condition_observations, policy)` → 报告；
`jm.validate_action(item, command, owner_user_id, now)` → 拟追加事件（不写）；`jm.reduce_actions(report, events, now)` → 折叠管理状态。
旧对象 → 合同：`jm.adapters.candidate_binding_from_{judgment,scenario_tree,checkpoint}`（checkpoint 行无证据引用，只给 gap）。

**别踩**：
- 报告 id / 项 id 全由内容派生，`generated_at` 不进摘要；改判定规则必须同时 `JM_FIXTURES_UPDATE=1` 重生成夹具并把 diff 一起送审。
- 输入侧未知字段会被拒绝（不是忽略）；06 造 `EvidenceVersion` 时 `source_hash` 必填，缺 `recorded_at` 会降档而不是报错。
- `~/.finance-runtime/test-receipts/latest.json` 正被并行的 03 工作树覆盖，取收据按 revision 时间戳文件并核对 `tree`。
- 工作树没有 venv：解释器用主树 `.venv-workbench/bin/python`。

**未做 / 归他人**：合并 main（等用户确认，先跑全仓等价 CI）；06 的 Workbench 接线与 ledger-map 登记；能力图谱回写由 06 统一申请。
