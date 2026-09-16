# 01 · 判断持续维护 · 阻塞与跨轨诉求

更新：2026-09-13。状态：**无阻塞项**。本轨白名单内的四步（合同与夹具 / 差分与条件 / 动作归约 / 只读集成）全部在本包完成，
以下是交给 06 的公共依赖——都不是本轨能改、也不该改的东西（spec 01 §6：API / UI、userspace、ledger-map、旧对象、公共配置不改）。

## 交 06 的接线诉求（不阻塞本轨 engineering_complete）

| # | 诉求 | 为什么归 06 | 最小复现 / 续跑步骤 |
|---|---|---|---|
| 1 | 持久化 `dependency_bindings` 与 `maintenance_actions`（事件日志）：单 writer、原子比较 `expected_management_revision`、追加不覆盖 | 本包无 writer（spec 01 §5 末句）；台账要先在 ledger-map 登记（总合同 §5 第 6 条） | 事件形状见 `contracts.ManagementEvent`；`validate_action` 返回的 `event` 直接落盘，落盘后用 `reduce_actions(report, events, now)` 重建视图 |
| 2 | 把河上对象解析成 `EvidenceVersion`：`RiverObject.to_dict()` 的 `ref / source_hash / valid_from / valid_to / recorded_at / derivation` 与合同字段同名；撤回需另填 `expired_at`，换 ref 需填 `supersedes_ref` | 取数是 IO，本包不做 | 输入侧 `source_hash` 必填；缺 `recorded_at` 的对象照样可传（本包按 `valid_from` 放置并降档为 trade_date_only），两者都缺会进 gap `time_metadata_missing` |
| 3 | 条件观测：用 `river_derive.bind(label, slice)` 在 `as_of` 切片上取值，填 `ConditionObservation{label, entity_id, as_of, value, recorded_at, label_version=LABEL_VERSION, source_ref}` | 同上 | 只有 `SLICE_EVALUABLE_LABELS`（dual_red_strict / volume_surge / market_stage / limit_heat_rank）能编译；其它标签的条件会被 `compile_binding_condition` 拒绝，别在 UI 里让用户选到 |
| 4 | 「从现在开始跟踪」流程：用户选择自己有权读的引用 → 06 解析真实 hash → 造 `DependencyBinding(binding_origin=user_confirmed, created_at=真实确认时刻, baseline_cutoff=解析时的截止)`；`adapters.candidate_binding_from_*` 给的是**草稿**，仍需用户确认 | 授权与用户态归 06（spec 01 §1、§6） | 绑定校验用 `contracts.parse_binding`，出错码稀疏可直接映射到 UI 业务码（`binding_without_refs / hash_not_declared / foreign_user_ref …`） |
| 5 | checkpoint 行没有证据引用（实测真实用户态 84 行 checkpoint 全无 ref/hash）：面板只能显示「原记录没有完整依据」并提供从现在跟踪；已有回检可用 `adapters.verdict_evidence_versions` 转成可绑定版本 | 旧写入者不改 | 见 `test_judgment_maintenance_adapters.py::test_old_readers_to_report_leaves_ledgers_byte_identical` |

## 供 04 的说明

- 04 直接读 `intelligence/tests/fixtures/research_evolution/01/*/expected.json`（`schema_version = judgment-maintenance/v1`，`synthetic: true`）。
- `change_type=content_changed` 的项**只**说明依据的哈希变了；04 的「过期证据沿用」若没有实际引用收据仍应判 unknown（04 spec §4 第 3 行已写）。

## 已知限制（记录，不算阻塞）

- 合取判定用 Kleene 三值（任一 false 即 false），与 `scenario_trees.resolve` 「遇第一个缺原料即停」不同——那里回答「树往哪走」，这里回答「条件触发没有」；两处语义各自成立，未改旧模块。
- 报告里的 `first_known_day` / `dependency_ref` / `condition_evaluation` / `management` 是 spec §3 之外的补充字段，都在 `contracts` 里有说明；06 若不需要可不展示，但反序列化时不能剔掉（未知字段会被拒绝，缺字段用默认值即可）。
