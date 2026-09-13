# 04 · 个人研究流程诊断 · 进度（换会话先读这里）

规格：`docs/superpowers/specs/2026-09-13-research-evolution/04-personal-diagnostics.md`（总合同 `README.md` 同目录）。
本文件只记「做到哪、怎么验、下一步」；设计理由在规格、模块 docstring 与日期快照
`docs/handoffs/2026-09-13-research-diagnostics-04.md`。

## 状态一句话

**engineering_complete**（2026-09-13，代码提交 `4d457d7a` = `fea6ef98` 主体 + pit_grade 对齐修补）：模块真实计算，
合同 / 负例 / 边界测试通过，可由 06 调用。未 product_verified（无 UI / API，归 06）；未 field_evidence（无真人数据）。

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

## 收据（绑定代码提交 `4d457d7a3cc6304c2ce714da795d37e527d19523`）

原始输出：`/Users/a77/.finance-runtime/test-receipts/rd04-4d457d7a/`（`EXIT_CODES.txt` 汇总；上一版 `rd04-fea6ef98/` 保留）；
pytest 插件收据 `/Users/a77/.finance-runtime/test-receipts/20260913T065249Z-4d457d7a.json`——**按 revision 取时间戳文件，不读 `latest.json`**
（六棵树并发跑 pytest 会互相覆盖它）。解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，在实现工作树根执行。

| 命令 | 结果 | exit |
|---|---|---|
| `pytest intelligence/tests --collect-only -q -k research_diagnostics` | 51 selected / 8411 collected | 0 |
| `pytest intelligence/tests -q -k research_diagnostics` | 51 passed | 0 |
| `pytest intelligence/tests/test_checkpoints.py intelligence/tests/test_judgments.py intelligence/tests/test_scenario_trees.py -q` | 78 passed | 0 |
| `ruff check intelligence/services/research_diagnostics intelligence/tests/test_research_diagnostics_*.py` | All checks passed | 0 |
| 额外回归 `pytest intelligence/tests/test_observation_script.py intelligence/tests/test_research_project.py -q` | 60 passed | 0 |
| pre-commit 11 道（层级审计 / 路径字面量 / 未读字段 / 工具可达性 / 目录保鲜 …） | 提交 `fea6ef98`、`4d457d7a` 时全部通过 | 0 |

输入摘要：复合场景 15 records / 4 verdicts / 13 receipts / 4 maintenance items / 6 cases；报告 id `rd-…` 对乱序、三倍重复输入稳定。
未知项：全仓 `pytest -q` 未在本树跑（本轨只新增文件，旧读取器与相邻模块回归已跑）；合并前按 AGENTS.md 跑等价 CI。

## diff 白名单

`git diff --name-only 31ddec51..4d457d7a`（代码提交）只含：`intelligence/services/research_diagnostics/**`、
`intelligence/tests/test_research_diagnostics_*.py`、`intelligence/tests/fixtures/research_evolution/04/**`。
本目录 `PROGRESS.md` / `BLOCKED.md` 与交接文档另行提交。未改 API / UI / userspace / ledger-map / 注册表 / 原台账。

## 2026-09-13 · 对用户核对意见的补核

用户逐条核过总合同事实层后补发三条意见与几条门禁提醒，对 04 的影响与处置：

| 意见 | 对 04 的核对 | 处置 |
|---|---|---|
| 执行者读到的 spec 缺 09-06 之后的设计段（主树未提交，gitea/main 无） | 只读主树 `docs/superpowers/specs/2026-09-06-personal-research-calibration-endstate-design.md`（未提交 +222 行）中与 04 相关的行：L124 晚于次日开盘登记标 late、不进校准（与适配器截止规则一致）；L186 缺 `recorded_at` 的历史对象标 `trade_date_only`、`hindsight` 不进任何统计（前者与 04 原实现**不一致**，后者一致）；L188 日频粒度、不补假盘中时刻（与 `known_by` 退到按日比一致） | 修补 `4d457d7a`：剧本 / 树缺登记时刻但 as_of 已知 → `trade_date_only`，只有两者都缺才 `unverifiable`；补测试。其余无冲突。设计文本本身仍待改它的会话提交 |
| README §3「不荐股」只约束对外渲染，维护 / 排序 / 诊断对象不过滤个股 | `grep scope` 全包：`ObjectRef.scope` 只存储与序列化，无任何按 scope / 个股的过滤；04 无对外渲染，未碰观察剧本硬门与 `compliance_gate` | 无需改动；已符合 |
| spec 目录先合进 main（待用户确认） | `git merge-tree --write-tree gitea/docs/river-next-specs feat/research-diagnostics-04` exit 0（无冲突）；七份 spec 的 blob 与规格分支逐个相同 | 两种顺序对 04 都干净；若先合规格分支，本分支的 `31ddec51` 会自然去重 |
| 门禁提醒：layer_audit / 路径字面量棘轮 / 收据别读 latest.json / 分支命名 | 层级审计与路径字面量门禁在两次提交均通过；收据按 revision 取时间戳文件；分支名 `feat/research-diagnostics-04` 带编号，未取工单号 | 无需改动 |

## 下一步

- 06：按 `BLOCKED.md` 的接线依赖清单注入收据（coverage / revision / evidence_use / stage_use / exposure），用 `adapters.load_legacy_inputs` 起步。
- 01：定稿后同步 `maintenance_report_01.json` 夹具与 `contracts.parse_maintenance_reports`（字段先改总合同）。
- 合并 main 与部署等用户确认。

## 2026-09-13 返修（评审 D1/D2/S3）

来源：`/Users/a77/.finance-runtime/reviews/research-evolution-20260913/review.md` 判本轨三条缺陷。
返修提交 `5df2e7ad`（代码 + 测试），最终 SHA 见本节末。每条缺陷先写调用真实 `diagnose` 的反例、
证明现版红，再修，再证明绿；每条另配负控，防止「把检查关掉」式的假修复。

新测试文件 `intelligence/tests/test_research_diagnostics_review_20260913.py`（14 例，含 6 条负控）。

### D1 [P1] 后来才记录的追溯失效被当成用户当时已知

- 根因：`rules.py::evidence_status_at` 里 `expired_at` 只与使用时刻比、`valid_to` 只与使用日比，
  两条都不核验**断言失效的那条记录**的 `recorded_at` 是否晚于行为。9/7 补记「9/3 起失效」于是
  反过来追责 9/4 的引用。同文件的 `supersedes_ref` 分支本来就用了 `known_by(recorded_at, used_at)`，
  只有这两条漏了——所以缺陷形状是「一家人里有的有、有的没有」，比两个都没有更难看出来。
- 修法：判 `invalid` 要同时成立「当时已生效」与「当时已记录」。只满足前者 → `later_correction`（context）；
  `recorded_at` 缺失 → `unknown_time`（unknown），缺证不是反证。同一 ref 上若另有明确晚于使用时刻的
  更正，取有正面证据的 `later_correction`，不退回 unknown。
- 新测试：`test_d1_backdated_valid_to_does_not_blame_earlier_use`、
  `test_d1_backdated_expired_at_does_not_blame_earlier_use`、
  `test_d1_missing_recorded_at_on_ended_version_is_unknown_not_issue`、
  `test_d1_definite_later_correction_outranks_missing_record_time`；
  负控 `test_d1_negative_control_expiry_recorded_before_use_is_still_issue`、
  `test_d1_negative_control_backdating_only_moves_the_one_use`。
- 修前红：`AssertionError: 'issue' == 'issue'`（期望非 issue）、`'issue' != 'unknown'`。
- 修后绿：评审探针 `probe_01_02_04.py 04` 的 `later_record_of_backdated_valid_to` 由 `issue`
  变为 `context / ann:004 的更正记录晚于使用时刻…后知更正，不追责`，与 `expected` 一致。

### D2 [P2] 无责任系统故障进 evaluated 分母而非 excluded

- 根因：`rules.py::check_overdue_unreviewed` 的「系统失败窗口重叠」与「回检责任在系统」两条分支都置
  `context`，而 `denominators.py::build_denominators` 把 context 计进 `eligible/evaluated`，
  于是「用户根本没拿到的机会」被算成已评估覆盖，夸大诊断分母。
- 修法：两条分支改走 `_exclude` 并列原因（`system_failure_window` / `system_recheck_missing`），
  `non_attributable` 清单仍保留该对象——排除出分母不等于从责任归属里消失。
- **刻意保留的边界**：窗口内确有回检动作、只是结果 `unverifiable` 的（`ck-unverifiable`）仍按 context
  计入已评估。机会已被用户履行，规格 §4「到期未回检」那一行本就把它归 context/unknown 列；
  §5 的 excluded 针对的是「无责任系统故障」，即机会压根没落到用户头上的情形。评审点名的行号
  （`rules.py:705–728`）也正是这两条、不含 unverifiable 那条。负控测试钉住这个边界。
- 新测试：`test_d2_system_responsibility_without_recheck_is_excluded`、
  `test_d2_system_failure_window_is_excluded_not_issue`；
  负控 `test_d2_negative_control_real_recheck_stays_evaluated_context`、
  `test_d2_negative_control_plain_overdue_is_still_issue`。
- 修前红：`ck-agent` 仍以 `classification='context'` 出现在 findings 里（断言要求它不在 findings）。
- 修后绿：探针 `04_system_failure_counts_as_evaluated` 的 `agent_generated` 分母
  由 `eligible=1, evaluated=1, context=1, excluded=0` 变为
  `eligible=0, evaluated=0, issue=0, context=0, unknown=0, excluded=1`，
  `exclusion_reasons={"system_recheck_missing": 1}`，与评审验收钉一致。

### S3 [P1] 合成维护报告混入真实诊断被标 observed

- 根因：`report.py` 算 `provenance` 时只看 records / verdicts / receipts / cases，漏了
  `maintenance_reports`；`contracts.py::parse_maintenance_reports` 又把报告的 `provenance` 字段整个
  丢掉。合成维护证据因此被其他 observed 输入洗白成真实诊断依据。
- 修法：`MaintenanceItemView` 带上 `provenance`（报告级声明，项可覆盖），参与判定（过 cutoff 过滤后）
  的项计入报告级 `provenance`。
- **缺声明时的默认值与理由**：`PROVENANCES` 只有 `observed / synthetic` 两档，没有「未知」档。
  `observed` 是一句「这是真实用户效果」的断言，必须被证明而不是被默认，所以**失败关闭成 synthetic**，
  同时置 `provenance_declared=False`，由 `diagnose` 出 `maintenance_provenance_undeclared` gap，
  让「默认」与「认证」区分得开——否则报告会静默读作 synthetic，没人知道为什么。
- 已核实：真实 01 产物（`jm.assess(...).to_dict()`）报告级与项级**都没有** `provenance` 键，
  所以这条默认路径就是接真实 01 时要走的路径。喂真实 01 输出给修后的适配器：
  5 项全部解析（与 01 的 5 项一致，跨模块 parse 断言不掉），provenance=synthetic、declared=False。
- 新测试：`test_s3_synthetic_maintenance_report_taints_report_provenance`、
  `test_s3_undeclared_maintenance_provenance_fails_closed`；
  负控 `test_s3_negative_control_all_observed_inputs_stay_observed`（证明不是写死 synthetic）、
  `test_s3_negative_control_synthetic_exercise_case_still_taints`。
- 修前红：`AssertionError: 'observed' != 'synthetic'`（两例）。
- 修后绿：规范轴探针 `standards_04_probe.py` 的 `actual_report_provenance` 由 `observed`
  变为 `synthetic`，与 `expected_report_provenance` 一致；同报告里由该合成维护项产生的
  `stale_evidence_reuse` issue（jd-memo / ann:001）仍在——那条失效 8/20 就已记录、9/5 生效、
  9/6 才被引用，是当时确实可知的违规，D1 的修法没有把它一并关掉。

### 黄金夹具期望更新（两条旧断言编码的正是 D2 的缺陷行为）

| 测试 | 旧期望 | 为什么旧期望是错的 |
|---|---|---|
| `test_research_diagnostics_rules.py::test_a5_data_or_system_limits_are_not_user_issues` | `ck-agent` 为 `context` | 回检责任在系统，这不是用户的机会，按规格 §5 应 `excluded` 并列原因；当 context 就进了 evaluated 分母 |
| `test_research_diagnostics_adapters.py::test_coverage_declaration_from_06_unlocks_overdue_judgement_by_responsibility` | `tree_ck` 为 `context` | 同上（树由系统逐日解析） |

两处的 `non_attributable` 断言原样保留，并补上对应的 `exclusions.reason` 断言。
夹具 JSON 本身未改动；改的是测试里的期望值。

### 收据与命令

```
cd /Users/a77/fwp-wt-research-diagnostics-04
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q -p no:cacheprovider \
  intelligence/tests/test_research_diagnostics_*.py
```

- 结果：**65 passed, 0 failed, 0 skipped**，exit 0（基线 51 + 新增 14）。
- `ruff check` 六个改动文件全绿。pre-commit 11 道门禁在 `5df2e7ad` 全过。
- 跨轨接缝：`cross_module_probe.py` 三场景（complete / missing_source / legacy）全部 PASS，
  `parsed_items04` 与 `items01` 逐一相等（5/5、2/2、2/2）。
- 收据按 revision 取时间戳文件，未读 `latest.json`（该目录被多棵树共用）。

### 最终 SHA

代码与测试：`5df2e7ad`。本节文档提交见其后一条。

## 2026-09-13 QC 第二轮（扩大边界复审）

QC（`~/.finance-runtime/reviews/research-evolution-repair-qc-20260913/`）结论：原 13 项固定反例转绿，扩大边界确证 8 项，本轨 3 项。

- **S4[P1] 合成洗白**：项级 provenance 覆盖报告级，synthetic 报告 + observed 项输出 observed。修复：报告级 provenance 为天花板（项级只能持平/降档，冲突压回 synthetic），父子来源独立校验（未知枚举拒绝），新增 `maintenance_provenance_conflicts` 辅助函数；report.py 出 `maintenance_provenance_conflict` gap。
- **D3[P1] 未生效替代追责过去**：`evidence_status_at` 的 supersedes 分支只看 recorded_at。修复：加 valid_from 生效条件（缺省退回记录日）。
- **D4[P2] 后知更正压过记录时间缺口**：later 压过 time_unknown，本应 unknown 却变 context 进已评估分母。修复：final 优先级改为 time_unknown 压过 later；上轮锁错期待的 `test_d1_definite_later_correction_outranks_missing_record_time` 已改正为 unknown + 双向负控。
- 修复提交 **`1679d154`**；新增/改正共 7 条测试先红后绿；模块 72 passed；ruff 干净；QC 探针 S4/D3/D4 组复跑转绿（边界探针第 5 组 unrecognized 现按设计抛 DiagnosticsInputError）。
- **06 联测请用 `1679d154`**。口径纠偏：上轮「13 项已修复」实为「原 13 项固定反例转绿」。

## 2026-09-13 QC 第三轮（D5）

- 独立复核（`~/.finance-runtime/reviews/research-evolution-round3-qc-20260913/`）：原 8 项固定反例通过，扩大边界确证 5 项新问题，本轨占 1 项：D5[P2]（`used_is_current → valid` 提前返回发生在 time_unknown 判断之前，缺登记时间的失效事实被使用后才生效/登记的 current 洗成 context）。
- 修复 `8db4bbd9`：提前返回加 `not time_unknown` 守卫——「用的那一版现在仍有效」不能证明使用时刻失效是否已知；合法当前版本对照保留（fill_late 仍 context）。
- 验证：新增 2 条回归测试（主例 unknown + 双向补全 issue/context 负控）先红后绿；模块 74 passed；全量 9614 passed / 77 skipped（干净树 @8db4bbd9）；ruff 干净；QC 第三轮探针 04 组复跑 actual=unknown / fill_early=issue / fill_late=context / baseline=unknown；归档探针 D3/D4/S4 组复跑不回归。
- 06 联测请用 `8db4bbd9`。旧版曾推 gitea（远端停在 `b5cee17a`），第二/三轮修复均未 push。
