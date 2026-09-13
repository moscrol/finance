# 01 · 判断持续维护 · 进度（换会话先读这里）

> 总合同 `docs/superpowers/specs/2026-09-13-research-evolution/README.md`，本轨 spec 同目录 `01-judgment-maintenance.md`。
> 两份都在分支 `docs/river-next-specs`（工作树 `/Users/a77/fwp-wt-river-next-specs-0913`，spec 来源 SHA `28804505`），**尚未合入 main**——
> 主树里找不到它们不是丢了。

## 开工登记

| 项 | 值 |
|---|---|
| 工作树 / 分支 | `/Users/a77/fwp-wt-judgment-maintenance-01` · `feat/judgment-maintenance-01` |
| 开工基线 | `gitea/main` = `5fb13a8c26986e6a0a24eb2687a2635131426694`（重新 fetch 后与总合同一致） |
| spec 来源 | `docs/river-next-specs` @ `288045054341403338a2e6d6fe2fa652d9d9f6ff` |
| 解释器 | 主树 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（3.12.13；新工作树无 venv，按 AGENTS.md 用主树绝对路径） |
| 实际用户态根 | `FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users`（只做过键名形状统计，未读正文；测试全部走 tmp + monkeypatch 该变量） |
| 代码地图 | 主树 `ready n=22076 @b4a35fa`；本轮按能力图谱 + 精确符号定位，未以地图无结果断言缺失 |
| 计划修改路径（= 实际） | `intelligence/services/judgment_maintenance/**`、`intelligence/tests/test_judgment_maintenance_{contracts,assess,actions,adapters}.py`、`intelligence/tests/fixtures/research_evolution/01/**`、本目录 `PROGRESS.md` / `BLOCKED.md`、`docs/handoffs/inflight/feat-judgment-maintenance-01.md` |
| 白名单外改动 | **无**（§2 只读符号一行未动；API / UI / userspace / ledger-map / 注册表 / 旧台账未碰） |

## 任务 0 · 现有实现映射（核对于 5fb13a8c，[实测]）

| spec §2 符号 | 状态 | 本包如何用 |
|---|---|---|
| `checkpoints.register_checkpoint / load_checkpoints / object_type_of / due_checkpoints / record_verdict / load_verdicts` | 全部存在；记录形状 `id/ts/claim/due/category/source/themes/stocks/object_type/hindsight/metric?/projection_hash/...` | 只读；`adapters.object_ref_from_checkpoint` 复用 `id` 与 `object_type_of`；行内**没有任何证据 ref/hash**（真实用户态 84 行 checkpoint 亦然）→ 只能 gap `dependency_unbound` |
| `judgments.record_judgment / load_judgments / record_validated_judgment` | 存在；基础行 `ts/id/memo/themes/stocks`；foresight 类行另有 `evidence:[{ref,hash}] / invalidation(散文) / context_snapshot` | `adapters.candidate_binding_from_judgment`：`evidence` 可造 `verified_structured_output` 候选绑定；`invalidation` 是自然语言→ gap `condition_not_deterministic`，不编译 |
| `scenario_trees.ScenarioTree / load / current_state / compile_condition / eval_predicate` | 存在；树记录 `realized_path[].evidence_refs` 只有 ref 无 hash；`compile_condition` 只收 `SLICE_EVALUABLE_LABELS`（dual_red_strict / volume_surge / market_stage / limit_heat_rank） | `conditions.compile_binding_condition` 复用编译器与 `eval_predicate`；不调 `register / resolve / append_step` |
| `scenario_tree.ScenarioTreeArtifact` | 存在，是问答路由的表达产物 | 不用；绑定对象只认持久化树 |
| `judgment_delta.classify_material / judgment_delta_receipt` | 存在 | 不用作依赖绑定或证伪证明（spec 明写） |
| `research_project.load_project / prior_for_turn` | 存在（读 checkpoints/verdicts 路径） | 06 接线时沿用其范围筛选；本包不造研究项目 |
| `foresight._judgments_path / _checkpoint_paths`；`userspace.user_space / users_dir / resolve_user_id` | 存在 | 本包只用 `resolve_user_id` 的判据校验 owner（`contracts.validate_owner` 再过一次现役实现防漂移） |
| `river.RiverObject / RiverSlice.pit_grade` | `PitGrade = strict | trade_date_only`；strict 判据「全部对象 recorded_at 存在且 ≤ C」，空片 / hindsight fail closed | `EvidenceVersion` 字段与 `RiverObject.to_dict()` 同名；本包在其上加最弱档 `unverifiable`，判据同源 |

样本：用真实写入者在临时目录写出 judgment / checkpoint / verdict / 情景树各一份并逐字段核对（见 `test_judgment_maintenance_adapters.py` 的 fixture）。

## 步骤状态

| 步 | 内容 | 状态 | 证据 |
|---|---|---|---|
| 0 | 核对树 / 解释器 / 代码地图 / 符号，取样本，明确 ref/hash 可绑定性 | 完成 | 上表；结论：checkpoint 不可自动绑定，foresight 判断行可绑（部分 hash 为 null），树可绑 ref 但全 null hash |
| 1 | 合同与夹具（完整 / 缺源 / legacy，可序列化供 04/06） | 完成 | `contracts.py`（`judgment-maintenance/v1` + policy/binding/evidence/observation/command/event/action-result 子版本）；夹具 `fixtures/research_evolution/01/{complete,missing_source,legacy,actions}`，`expected.json` 由真实函数生成后冻结，全部 `synthetic: true` |
| 2 | 差分与条件（§8 前八项反向验收，未知带原因） | 完成 | `assess.py` / `conditions.py`；`test_judgment_maintenance_assess.py` 37 例 + `test_judgment_maintenance_contracts.py` 26 例 |
| 3 | 动作归约（重复请求不重做，冲突 / 失败不误关闭） | 完成 | `actions.py`；`test_judgment_maintenance_actions.py` 15 例（含 actions 夹具回放） |
| 4 | 只读集成（旧读取器接临时对象产报告，旧文件字节不变） | 完成 | `adapters.py`；`test_judgment_maintenance_adapters.py` 3 例：四本台账 sha256 前后一致，报告不含 memo/claim 正文 |

## 合同版本与关键设计决定

- `schema_version`：报告/项 `judgment-maintenance/v1`；输入侧 `judgment-maintenance-binding/v1`（必填）、`-policy/v1`（必填）、`-evidence/v1` / `-observation/v1`（可选、给了必须对）；动作侧 `-command/v1` / `-event/v1` / `-action-result/v1`。未知版本 / 枚举 / **字段**一律 `MaintenanceContractError(code, where)`。
- 时钟：`as_of`、`knowledge_cutoff`、`baseline_cutoff` 只收 `YYYY-MM-DD`（带时分秒直接拒）；`recorded_at / created_at / acted_at` 原样保留 ISO；`cutoff < as_of` 拒绝；`cutoff > as_of` 标 `hindsight`，pit 永不 strict。
- 版本放置：有 `recorded_at` 按其日期放置（strict）；只有 `valid_from` 按交易日放置并降 `trade_date_only`；两者都缺 → 不参与判定 + gap `time_metadata_missing`。先按 C 过滤再选 as_of 有效版本（`valid_from` 最晚 → `recorded_at` 最晚 → 哈希序兜底，同序不同哈希记 gap `ambiguous_version_order`）。
- 项链：每条依赖沿知识日（绑定生效日、各版本记录日、各撤回生效日、C）走状态序列，状态变化才出项；早先的项 `status=superseded`，后项 `supersedes_item_id` 回指；`first_known_day` 记该状态最早可知日，`knowledge_cutoff` 一律是报告的 C。恢复 / 更正因此天然「关联旧项」而不需要跨次存储。
- `dedup_key` = owner + 对象身份 + binding 身份/版本 + 依赖 ref + 前后哈希 + change/reason（条件项另加 condition_id + 表达式摘要 + 观测窗口 = as_of），不含扫描时间；`id = jmi-sha256(dedup_key)[:16]`。`item_version` = 前后版本 + 绑定版本 + 变化类型（条件项 = 表达式 + 观测读数）的哈希，不含管理状态；`management_revision` 每个被接受的动作 +1，时间推导的 snooze 唤醒不动它。
- 合取三值：任一 false → false；否则任一 unknown → unknown。与 `scenario_trees.resolve` 「遇第一个缺原料即停」不同，两处语义各自成立（那里答「树往哪走」），未改旧模块。
- 条件触发后的动作按 role：upgrade / downgrade / abandon → `rejudge`，review → `review_evidence`；false / unknown → `none`。`items_open` 只数 `status ∈ {open, claimed, rejudgment_requested}` 且 `action != none` 的项。
- 未变的依赖只计 `dependencies_checked` 不出项（`policy.emit_unchanged=true` 才出 `unchanged/no_change` 项）。
- 幂等：`payload_digest` 不含 `command_id` 与 `acted_at`；同 `command_id` 同摘要 → `replayed`，异摘要 → `conflict(command_payload_mismatch)`。snooze 的「不能 snooze 到过去」只在 `validate_action` 按 `now` 拦，重放台账时只比 `event.at`（否则晚重放会改判历史事件）。
- spec §3 之外的补充字段（都在 `contracts` 有注释）：项上 `dependency_ref / condition_evaluation / first_known_day / management{applied_commands, snooze_until, claimed_at, closed_at, closure, rejudgment}`；报告上 `management_log`。

## §8 反向验收对照

| # | 反例 | 测试 |
|---|---|---|
| 1 | 只改版式 hash 变 → requires_review，不写失效/miss | `test_format_only_hash_change_is_requires_review_not_falsification` |
| 2 | 同名主题不自动绑；今天绑定只向前维护 | `test_same_theme_announcement_is_not_bound_automatically`、`test_binding_today_maintains_forward_only` |
| 3 | 同 ref 更正：当前看新、历史 cutoff 看旧 | `test_correction_visible_now_but_not_at_historical_cutoff`、`test_fixture_complete_shape` |
| 4 | 一依赖缺、其余利好 → 仍 unknown | `test_missing_dependency_stays_unknown_even_when_others_are_fine`、`test_fixture_missing_source_shape` |
| 5 | 条件真/假/缺值；散文被拒 | `test_condition_true_false_unknown`、`test_prose_or_otherwise_condition_rejected`、`test_conjunction_uses_three_valued_logic`、`test_observation_after_cutoff_is_not_known_yet` |
| 6 | 连扫两次 / 乱序 / 重复三份 → id 与待办稳定 | `test_stable_ids_under_reorder_and_duplicates`、`test_generated_at_is_metadata_only` |
| 7 | 同 id 异 owner；伪造 owner / 路径穿越 / 未授权 ref | `test_same_ids_under_different_owners_do_not_collide`、`test_foreign_binding_in_input_is_rejected`、`test_forged_owner_rejected`、`test_unauthorized_ref_rejected_without_leaking_other_user`、contracts 的 `TestOwnerAndRefs` |
| 8 | 旧记录缺 ref/hash/时间/版本 → coverage/gap | `test_fixture_legacy_shape`、`test_legacy_checkpoint_without_evidence_only_yields_gaps`、`test_time_metadata_missing_*`、`test_missing_recorded_at_downgrades_to_trade_date_only`、`test_baseline_unknown_to_version_set_is_a_gap_not_a_guess` |
| 9 | snooze 到期同项恢复；新更正关联新项；重判失败不关闭 | `test_snooze_expires_back_to_same_open_item`、`test_new_correction_creates_linked_new_item_without_inheriting_snooze`、`test_rejudge_failure_keeps_item_open_and_link_needs_same_owner` |
| 10 | 重复 command_id / 并发同 revision / 异载荷重放 → 至多一份有效 | `test_duplicate_command_id_is_replayed_once`、`test_concurrent_commands_on_same_revision_only_one_wins`、`test_same_command_id_with_different_payload_is_conflict` |

**突变检查（证明测试会咬人，[实测] 2026-09-13）**：对已提交代码逐个植入 7 处错误实现，各跑对应用例，全部变红后 `git checkout` 复原并确认与 HEAD 无差：
M1 合取先看 unknown、M2 去掉知识截止过滤、M3 dedup_key 去掉 owner、M4 重放不比载荷摘要、M5 哈希变按未变、M6 条件 unknown 强转 false、M7 旧 revision 照单全收 → 7/7 red。

## 收据

| 命令（在本工作树，解释器 = 主树 `.venv-workbench`） | revision | 结果 |
|---|---|---|
| `pytest -q intelligence/tests/test_judgment_maintenance_{contracts,assess,actions,adapters}.py` | 9735103c（工作树含未提交的本目录文档） | **86 passed** / 0 failed / 0 skipped |
| `pytest -q intelligence/tests/test_{checkpoints,judgments,scenario_trees,judgment_delta,research_project}.py`（旧读取器回归） | 同上 | **119 passed** / 0 failed |
| `ruff check intelligence/services/judgment_maintenance intelligence/tests/test_judgment_maintenance_*.py` | 同上 | All checks passed |
| `scripts/layer_audit.py` / `scripts/check_path_literals.py` / `scripts/check_unread_fields.py` | 同上 | 三道门全部通过；提交 9735103c 时 pre-commit 11 道 hook 全过 |
| 干净树全量收据（提交文档后重跑，绑定最终 SHA） | 见下节「最终收据」 | — |

收据文件在 `~/.finance-runtime/test-receipts/<stamp>-<rev8>.json`（conftest 自动写；`latest.json` 会被并行工作树覆盖，**按 revision 取时间戳文件**，且核对 `tree` 字段是本工作树）。

## 最终收据（干净树，dirty=false）

| 命令 | revision | exit | passed / failed / skipped | 收据 |
|---|---|---|---|---|
| `pytest -q -p no:cacheprovider intelligence/tests/test_judgment_maintenance_{contracts,assess,actions,adapters}.py intelligence/tests/test_{checkpoints,judgments,scenario_trees,judgment_delta,research_project}.py` | `dbaa3968e1802ede4f3002d7bdb5ae1df2822a62` | 0 | **205 / 0 / 0**（新 86 + 旧读取器回归 119） | `~/.finance-runtime/test-receipts/20260913T065345Z-dbaa3968.json`（`tree` = 本工作树，`dirty` = false） |
| `ruff check .`（全仓） | 同上 | 0 | All checks passed | `/tmp/jm-full-ruff.log`（临时） |
| `pytest -q -p no:cacheprovider`（全仓等价 CI，合并前置；9 分 29 秒） | 同上 | 0 | **9626 / 0 / 77**（另 2 xfailed） | `~/.finance-runtime/test-receipts/20260913T070317Z-dbaa3968.json`（`tree` = 本工作树，`dirty` = false，`failed_ids` = []） |

全仓跑的是 dbaa3968 的代码；运行期间工作树里唯一未提交的改动是本文件（docs），不影响被测代码。前端 / e2e / registry-check 叶子本轨未动，合并前由集成人按 AGENTS.md 一并跑。

输入摘要：夹具 `complete / missing_source / legacy / actions` 的 `input.json` 由测试直接读取，`expected.json` 冻结于提交 9735103c；本轮之后未再改判定规则。
本表所在提交只改文档，代码 SHA 仍是 9735103c（文档提交 dbaa3968 之上再叠一次「补收据」提交）。

## 公共依赖（交 06，详见 `BLOCKED.md`）

绑定与事件的持久化（单 writer + 原子 revision 比较）、河对象 → `EvidenceVersion` / 观测 → `ConditionObservation` 的取数适配、「从现在开始跟踪」的用户确认流程、ledger-map 登记。本轨没有任何需要改公共源模块的诉求。

## 完成状态自评

- **engineering_complete：是**——三入口真实计算；合同 / 负例 / 边界通过；04 可读夹具，06 可直接调用（输入均为 JSON 或本包类型）。
- product_verified：**否**，归 06（需隔离 Workbench 上真实 UI/API + 真实模块 + 临时用户态跑通 I01/I03/I05）。
- field_evidence：不适用于本轨。

## 下一步

1. 06：按 `BLOCKED.md` 五条接线；接线时把 06 侧 `EvidenceVersion` 构造与本包 `parse_evidence_version` 的拒绝码对齐成 UI 业务码。
2. 02 / 04：直接消费 `fixtures/research_evolution/01/*/expected.json`；02 注意 `condition_result=true` 且 `condition_role ∈ {abandon, downgrade}` 才是「明确登记的条件角色及已观测触发」，`content_changed` 最多是 review_changed_evidence。
3. 合并前（等用户确认）：在本工作树跑现役等价 CI（`ruff check . && pytest -q` 全仓）+ registry/e2e 门禁；本轨未动前端与注册表。
