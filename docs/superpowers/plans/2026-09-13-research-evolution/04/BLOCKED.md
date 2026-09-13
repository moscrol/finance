# 04 · 阻塞与公共依赖（换会话先读 PROGRESS.md）

## 阻塞项

**无。** 规格允许的每个缺证路径都已落成 unknown + gap 或 excluded + reason，没有用假数据过门。

## 接线依赖清单（不阻塞 04，但决定 04 报告能报出多少 issue）

04 是纯函数，输入由 06 注入。存量台账（`checkpoints.jsonl` / `verdicts.jsonl` / `judgments.jsonl` /
`observation_scripts.jsonl` / `scenario_trees.jsonl`）经 `adapters.load_legacy_inputs` 进来时，下面这些
输入天然缺席，对应检查只能出 unknown。补齐责任与最小输入形状如下（字段合同见 `contracts.py`）：

| 缺什么 | 影响的检查 | 现状（存量） | 责任 | 最小输入 |
|---|---|---|---|---|
| `coverage` 收据（回检台账完整性声明） | 到期未回检 | 一律 `coverage_unknown`，不能判「漏检」 | 06 单 writer 在夜跑 / 手动回检收口后写 `{"ledger":"verdicts","complete_from":D1,"complete_through":D2}` | 一条 `ProcessReceipt(kind="coverage")` |
| `revision` 收据 + `version_chain_complete=true` | 条件修改 | 存量对象无版本链，一律无机会 | 06 的绑定 / 管理动作 writer；原判断变更走原写入者，04 只读收据 | `versions[]` ≥ 2 或 `ProcessReceipt(kind="revision", payload={from_version,to_version,reason,disclosed,linked_refs})` |
| `evidence_use` 收据（实际投影 / 引用了哪个证据版本） | 过期证据沿用 | 无使用记录，无机会 | 06 从 run / 投影收据派生；带 `evidence_ref` 与 `version_or_hash` | `ProcessReceipt(kind="evidence_use")` |
| 01 `judgment-maintenance/v1` 报告 | 过期证据沿用 | 无报告 → `evidence_validity_unknown` | 01 产出、06 注入；04 只接这一版 | `maintenance_reports=[report]` |
| `stage_use` 收据 + 策略里的适用表 | 阶段不适用 | 无收据无机会；无适用表 → `applicability_table_missing` | 收据由 06 从方法调用点派生；适用表由方法 owner 提供、进 policy | `ProcessReceipt(kind="stage_use")` + `ApplicabilityTable` |
| `declared_deadline` | 迟登 | 只有观察剧本能算出（`default_next_open`）；checkpoint / 树 → `deadline_missing` | 若要对 checkpoint 判迟登，需在登记时写下预先声明的截止，或在 policy 定义确定性截止规则 | 记录字段 `declared_deadline` |
| `exposure` / `exercise_seen` / `learner_declaration` / `model_exposure` 收据 | 分组、练习分档 | 存量无曝光日志 | 06 记录（规格 §6「06 记录选题 / 重复次数」；03 的 record_exposure 同一身份） | 对应 kind 的收据 |
| 生产策略 `research-diagnostics-policy/v1` | 全部 | 夹具策略 `effective_from=2026-08-01` 只作工程验收 | 规则真实生效日由 06 / 方法 owner 定：观察剧本迟登规则随模块 2026-09-06 上线（`6594a872`） | `DiagnosticPolicy` |

## 给 01 的备注

- 04 只读 01 报告里的 `items[].object_ref / before / current / change_type / reason_code / pit_grade`；
  `EvidenceVersion` 需要 `expired_at` 或 `supersedes_ref + recorded_at` 才能判「当时已知失效」，
  只有 `hash_changed` 一律 unknown（`change_not_invalidating`）。
- 04 夹具 `intelligence/tests/fixtures/research_evolution/04/maintenance_report_01.json` 是按 01 规格 §3
  手写的合成件；01 定稿若改字段名，先改总合同，再同步这份夹具与 `contracts.parse_maintenance_reports`。

## 续跑步骤

1. 06 接线时先用 `adapters.load_legacy_inputs` 拿存量输入，看 `LegacyInputs.gaps`，再逐项补上表中的收据。
2. 每补一类收据，用 `intelligence/tests/test_research_diagnostics_rules.py` 里对应的反向证伪测试形状
   （删掉该收据 → 对应 issue 必须退回 unknown）在真实数据上复核一次。
