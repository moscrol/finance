# 04 · 个人研究流程诊断 · 进度（换会话先读这里）

规格：`docs/superpowers/specs/2026-09-13-research-evolution/04-personal-diagnostics.md`（总合同 `README.md` 同目录）。
本文件只记「做到哪、怎么验、下一步」；设计理由在规格、模块 docstring 与日期快照
`docs/handoffs/2026-09-13-research-diagnostics-04.md`。

## 状态一句话

**engineering_complete**（2026-09-13，代码提交 `fea6ef98`）：模块真实计算，合同 / 负例 / 边界测试通过，可由 06 调用。
未 product_verified（无 UI / API，归 06）；未 field_evidence（无真人数据）。

## 任务 0 · 基线登记（2026-09-13）

| 项 | 值 |
|---|---|
| 开工基线 | `gitea/main` = `5fb13a8c2698`（重新 fetch 后与 README 所记一致） |
| 规格来源 | 分支 `docs/river-next-specs` 提交 `194241dd`（七份规格），cherry-pick 进本树为 `31ddec51`，内容逐字节相同 |
| 工作树 / 分支 | `/Users/a77/fwp-wt-research-diagnostics-04` · `feat/research-diagnostics-04` |
| 解释器 | 主树 `.venv-workbench/bin/python`（Python 3.12.13）；ruff 规则 `E4/E7/E9/F`，target py39 |
| 实际用户态根 | 本轨不读生产用户目录；测试一律 `tempfile` 临时目录，`FORESIGHT_USERS_DIR` 不设。适配器只收显式路径 |
| 代码地图 | SessionStart 事实：`ready n=22076 @b4a35fa`；本轨按精确符号定位，未依赖地图断言缺失 |

### 现有实现映射（只读，任务 0 核对结果）

| 符号 | 核对结果 | 对本轨的含义 |
|---|---|---|
| `checkpoints.py::load_checkpoints/load_verdicts/object_type_of/due_checkpoints` | 行有 `id/ts/due/object_type/source/hindsight/projection_hash/metric`；`ts` 为带时区 ISO 秒；无版本链、无曝光日志 | 迟登缺「预先声明截止」→ unknown；到期回检的责任由 `metric` 类型分：`manual`/无 metric 归用户，机检类归系统 |
| `checkpoints.py::register_checkpoint/record_verdict/calibrate` | 只读不调用；`unverifiable` 非终态，带 `degradation` | hit/partial/miss 不映射流程优劣；`unverifiable`+degradation 列 non_attributable |
| `judgments.py::load_judgments` | `window=0` 取全部；已过 `memory_status` 覆盖；`record_type=foresight_judgment` 表示 agent 提议后用户 accept | 该类映射 `user_after_agent`；带 `promotion` 的晋升行作者未记 → `unknown_origin` |
| `observation_script.py::default_next_open/is_late/load` | 截止 = as_of 后首个非周末日 09:30(+08:00)，规则随模块 2026-09-06 上线（`6594a872`）；台账行带 `recorded_at/as_of/late/status` | 唯一有显式截止的对象；适配器重算截止并保留台账 `late` 旗标，不一致记 gap |
| `scenario_trees.py::load/current_state/recheck` | 树行 `as_of=knowledge_cutoff`、`recorded_at`（+08:00）；无登记截止 | 迟登 → `deadline_missing` unknown；otherwise 不是错误 |
| `scenario_tree.py::ScenarioTreeArtifact` | 问答表达产物 | 不当持久化树用；本轨不消费 |
| `judgment_delta.py::classify_material` | 材料角色分类 | 不作行为证明；本轨不消费 |
| `research_project.py::load_project/prior_for_turn` | 会话投影、触发点 | 对象绑定归 06；本轨不造研究任务 |
| `userspace.py::user_space` | `root/checkpoints_path/verdicts_path/judgments_path`；`observation_scripts_path` 为 property | 本包不解析用户根，只收注入路径/对象 |
| `teaching_framework/stage_rules.py::STAGES` | 七段粗阶段词表 | `stage_mismatch` 的阶段标签词表来源；适用表本身由 policy 注入 |

### 五类最小证据与缺证路径

| 检查 | 可判 issue 的最小输入 | 缺证时的落点 |
|---|---|---|
| 迟登 | 记录带时区精确 `recorded_at` + `declared_deadline` + 当时在效规则 | 缺截止 `deadline_missing`、只有日期 `recorded_at_date_only`、补录 / 事后视角 excluded |
| 条件修改 | `revision` 收据或 ≥2 节版本链（时间/理由/关联）+ `version_chain_complete=true` + 当时在效变更规则 | 链不完整 `version_chain_incomplete`、无时间 `revision_time_unknown` |
| 过期证据沿用 | `evidence_use` 收据（ref+hash）+ 01 报告里该 ref 的失效/更正版本且其记录时间 ≤ 使用时刻 | 仅 `hash_changed` → `change_not_invalidating`；无维护信息 `evidence_validity_unknown`；无哈希 `used_version_unknown`；更正晚于使用 → context（后知不追责） |
| 阶段不适用 | `stage_use` 收据（确定性标签、标签 cutoff ≤ 使用时刻）+ 当时在效适用表 | 标签 gap/模糊 `stage_label_unknown`、事后标签 `stage_label_hindsight`、无适用表 `applicability_table_missing` |
| 到期未回检 | `due` + 窗口已结束 + `coverage` 声明覆盖窗口 + 责任归用户 + 无 verdict/延期 | 无覆盖 `coverage_unknown`、责任不明 `responsibility_unknown`；unverifiable / 系统失败 / 机检缺回检 → context + non_attributable |

## 步骤状态

| 步 | 内容 | 状态 |
|---|---|---|
| 0 | 核对树/解释器/地图/符号；五类最小证据与缺证路径；旧读取器产生临时输入 | 完成（`adapters.load_legacy_inputs`，真实写入者造台账的测试通过） |
| 1 | 合同/分组/分母 | 完成：01 夹具离线可读；未知版本拒绝；恒等式每行自检（`denominator_identity_broken` gap） |
| 2 | 五类规则 | 完成：每类都有 issue / context / unknown 样例；重复收据 ×3 分母与 finding id 不变 |
| 3 | 一题与泄漏分档 | 完成：有证据 issue 配一题；无题 / 只 unknown → `exercise=null` + gap；三轴分档独立 |
| 4 | 集成/回归、收据、diff 白名单 | 完成：旧读取器回归绿；台账字节不变；diff 只在白名单路径 |

## 合同版本与夹具

- 报告 `research-diagnostics/v1`；策略 `research-diagnostics-policy/v1`；题包 `research-diagnostics-exercise-pack/v1`。
- 只接 01 的 `judgment-maintenance/v1`；其他版本 `UnsupportedSchema`。
- 夹具 `intelligence/tests/fixtures/research_evolution/04/`（全部 `provenance=synthetic`，sha256 前 16 位）：
  `policy.json` ff729aa4c639c38e · `maintenance_report_01.json` 2da6db9f031b4bdd · `exercise_pack.json` effd5310709f6a4a · `scenario_full.json` 88d67d8a30ab8979。

## 收据（绑定代码提交 `fea6ef98ebc53a0329def2f414e68a787ea743bf`）

原始输出：`/Users/a77/.finance-runtime/test-receipts/rd04-fea6ef98/`（`EXIT_CODES.txt` 汇总）；
pytest 插件收据 `/Users/a77/.finance-runtime/test-receipts/20260913T064327Z-fea6ef98.json`。
解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，在实现工作树根执行。

| 命令 | 结果 | exit |
|---|---|---|
| `pytest intelligence/tests --collect-only -q -k research_diagnostics` | 50 selected / 8410 collected | 0 |
| `pytest intelligence/tests -q -k research_diagnostics` | 50 passed | 0 |
| `pytest intelligence/tests/test_checkpoints.py intelligence/tests/test_judgments.py intelligence/tests/test_scenario_trees.py -q` | 78 passed | 0 |
| `ruff check intelligence/services/research_diagnostics intelligence/tests/test_research_diagnostics_*.py` | All checks passed | 0 |
| 额外回归 `pytest intelligence/tests/test_observation_script.py intelligence/tests/test_research_project.py -q` | 60 passed | 0 |
| pre-commit 11 道（层级审计 / 路径字面量 / 未读字段 / 工具可达性 / 目录保鲜 …） | 提交 `fea6ef98` 时全部通过 | 0 |

输入摘要：复合场景 15 records / 4 verdicts / 13 receipts / 4 maintenance items / 6 cases；报告 id `rd-…` 对乱序、三倍重复输入稳定。
未知项：全仓 `pytest -q` 未在本树跑（本轨只新增文件，旧读取器与相邻模块回归已跑）；合并前按 AGENTS.md 跑等价 CI。

## diff 白名单

`git diff --stat 31ddec51..fea6ef98` 只含：`intelligence/services/research_diagnostics/**`、
`intelligence/tests/test_research_diagnostics_*.py`、`intelligence/tests/fixtures/research_evolution/04/**`。
本目录 `PROGRESS.md` / `BLOCKED.md` 与交接文档另一提交。未改 API / UI / userspace / ledger-map / 注册表 / 原台账。

## 下一步

- 06：按 `BLOCKED.md` 的接线依赖清单注入收据（coverage / revision / evidence_use / stage_use / exposure），用 `adapters.load_legacy_inputs` 起步。
- 01：定稿后同步 `maintenance_report_01.json` 夹具与 `contracts.parse_maintenance_reports`（字段先改总合同）。
- 合并 main 与部署等用户确认。
