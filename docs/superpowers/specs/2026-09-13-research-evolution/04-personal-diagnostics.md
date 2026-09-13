# 04 · 个人研究流程诊断与一题历史练习

日期：2026-09-13。状态：设计，未上线；基线 `5fb13a8c`。与 01 用合同夹具并行，授权、路径与展示归 06。

## 1. 目标、默认假设与非目标

检查私有记录的迟登、条件修改、过期证据沿用、阶段不适用、未回检五类流程，交证据、分母、不能归因项及一题历史练习。修改不自动等于犯错，结果落空不等于过程错误。

选择确定性规则、显式缺口，交可证伪诊断。非目标：心理/能力画像、认证、收益归因、排行榜、课程体系、模型评分、新源抓取、自动改框架/画像/方法库。

默认日频、显式区间/cutoff。actor 来源须有记录，不把用户目录内 agent 判断算用户原判断。缺原版本/时间/使用证据为 unknown，不伪造旧台账字段。

## 2. 当前精确符号与权威输入

| 文件与符号 | 复用方式与限制 |
|---|---|
| `intelligence/services/checkpoints.py::load_checkpoints/load_verdicts/object_type_of/due_checkpoints` | 保留 unknown_legacy；到期不等于怠惰，数据降级不判用户漏检 |
| 同文件 `register_checkpoint/record_verdict/calibrate` | 只读；hit/partial/miss 不映射流程优劣 |
| `intelligence/services/judgments.py::load_judgments/record_validated_judgment` | 读已确认判断，不调用晋升 writer |
| `intelligence/services/scenario_trees.py::load/current_state/recheck` | 持久化原条件/路径；otherwise 不是错误 |
| `intelligence/services/scenario_tree.py::ScenarioTreeArtifact` | 表达产物不能替代持久化树 |
| `intelligence/services/judgment_delta.py::classify_material/judgment_delta_receipt` | 材料分类不是用户忽略反证的行为证明 |
| `intelligence/services/foresight.py::_compose_system_prompt`；`intelligence/userspace.py::user_space` | 06 管先验/用户态，不自动注入诊断 |
| `intelligence/services/research_project.py::load_project/prior_for_turn` | 复用对象绑定，不造新研究任务 |

旧 checkpoint 缺完整 ref、版本链和曝光日志。01 的“变化待审”不证明用户看到变化后沿用旧证据；今天新增 DependencyBinding 也不证明旧行为。逐项检查可观测性。

本单深化旧终局 spec 的修正/迁移评估，不新造回测或训练入口。

## 3. 纯输入与报告合同

```text
diagnose(*, owner_user_id, start, end, knowledge_cutoff,
         records, verdicts, maintenance_reports,
         process_receipts, exercise_cases, policy) -> DiagnosticReport
evaluate_exercise_response(*, exercise, response, answer_key) -> ExerciseFeedback

DiagnosticReport
  schema_version = "research-diagnostics/v1"
  id, owner_user_id, start, end, knowledge_cutoff, input_digest
  generated_at                 # 不参与内容 id/hash
  pit_grade, gaps[], findings[], denominators[], exclusions[]
  uncertainty, non_attributable[], exercise

DiagnosticFinding
  id, kind, classification, actor_group
  object_refs[], evidence_refs[], maintenance_item_ids[]
  rule_id, rule_version, observed, expected, occurred_at
  knowledge_cutoff, pit_grade, gaps[], limitation

Denominator
  kind, actor_group, eligible, evaluated, issue, context, unknown, excluded
  unit = "original_object_check_opportunity"
  sample_refs[], exclusion_reasons[], rate = null

HistoricalExercise
  id, target_finding_id, case_ref, as_of, knowledge_cutoff
  prompt, visible_evidence_refs[], projection_hash
  data_pit_grade, model_exposure_grade, learner_exposure_grade
  exercise_status, answer_key_ref, limitation

ExerciseFeedback
  exercise_id, status, checks[], missing_evidence_refs[], explanation_ref
```

06 注入验权冻结输入，原 ref/id/version 复用 01 object_ref；maintenance_reports 接 `judgment-maintenance/v1`，04 用版本化夹具，不复制 01 判定器。跨 owner 输入拒绝。

actor_group=`user_original/agent_generated/user_after_agent/unknown_origin`。按作者/曝光收据分组；看后采纳/修改均保留原 agent 引用，文本相似不证明看过。未知来源不算独立用户能力。

classification=`issue/context/unknown`：issue 要证明违反当时适用的显式规则；context=合规或不应归错，unknown=不可判。kind=`late_registration/condition_revision/stale_evidence_reuse/stage_mismatch/overdue_unreviewed`；缺规则版本不能事后定标准。

## 4. 五类检查及不能推出的结论

| 检查 | 可以判 issue 的最小证据 | 应转 context/unknown 的情况 |
|---|---|---|
| 迟登 | 原登记晚于预先声明截止，且应为事前对象 | 历史补录排除；缺截止/只有日期为 unknown |
| 条件修改 | 前后确认版本违反当时冻结/变更规则，完整日志证明未披露 | 带时间/理由/关联为 context；仅文本变化不足 |
| 过期证据沿用 | 实际投影/引用用了当时已知失效版本，规则要求有效证据 | 01 hash changed 无使用记录为 unknown；后知更正不追责 |
| 阶段不适用 | 当时适用表、实际使用收据、确定性阶段标签明确冲突 | 后来换阶段、当时 gap/模糊标签不足 |
| 到期未回检 | 到期应检、窗口结束、覆盖完整且无回检/延期、责任明确 | 未到期排除；数据/系统失败非用户归因；无覆盖 unknown |

问题存在与责任归属分开：执行者不明归 unknown_origin，系统/数据限制列 non_attributable。miss 配完备流程允许零 issue，hit 配违规迟登仍检出；树分支、命中、主动放弃不自带奖惩。

## 5. 分母、时间与不确定性

按 `(owner_user_id, 原对象, 检查类别, 机会窗口)` 去重，多源/修订/重复扫描不增加样本。不同到期可算不同机会，但保留原对象聚类身份，不称独立市场实验。

`eligible=evaluated+unknown`，`evaluated=issue+context`。不适用/历史补录/未到期/无责任系统故障 excluded 并列原因；一机会一桶。issue 同时展示 eligible、unknown、actor_group，未知不算成功。

首版只报计数/覆盖，不出错误率、胜率、置信分或能力进步。uncertainty 说明 `small_sample/selection_bias/source_coverage/actor_coverage/correlated_observations`；主动登记不代表全部任务，方法统计留旧门。

按本次 cutoff 过滤证据，再按**行为当时 cutoff**判断可知性；后知更正只作背景，不改旧 issue。trade_date_only 不判精确迟登，未来 verdict 不改过去报告。同输入同内容 id/hash，generated_at 另记。

## 6. 只交一题的历史练习

从完整冻结题包按 issue/训练目标稳定选一题。只有 unknown 或无适配题：exercise=null+gap。首版人工题包、确定性选择/模板，无 LLM 调用。

只练一件事，如“截至当日哪份材料过期、该补什么”。题包带 case_ref、当日材料、隐藏答案、规则版本/解答证据；按过程评分不猜涨跌，不将结果选题说成随机。06 记录选题/重复次数。

三轴独立记录：

- data_pit_grade=`strict/trade_date_only/unverifiable`：未来材料/时间不明不能进严格题包。
- model_exposure_grade=`deterministic_only/model_exposure_unknown/known_exposed`：首版无模型；使用模型而训练/上下文曝光不明则 unknown，已给结局为 exposed。改名去日期不洗掉泄漏；严格数据 PIT 不证明模型未见历史。
- learner_exposure_grade=`not_declared/declared_unseen/seen_or_repeated`：自报未见不是盲测证明；重复题分列，不作能力认证。

学习者投影仅含 prompt/visible refs；answer_key_ref 为内部引用，06 提交前不下发答案/后续结果/可下载答案链接，答题后解锁解释。可交题 exercise_status=ready，无题 null；反馈 status=checked/manual_review，只比较结构化选择/引用，散文理由待人工，不用模型评分。不建判断/改画像。

## 7. 文件白名单与执行顺序

可写：`intelligence/services/research_diagnostics/**`、`intelligence/tests/test_research_diagnostics_*.py`、`intelligence/tests/fixtures/research_evolution/04/**`、本规格、`docs/superpowers/plans/2026-09-13-research-evolution/04/{PROGRESS.md,BLOCKED.md}`。01/旧实现只读；API/UI、userspace、ledger-map、注册表、配置、原台账/规则/框架不改，公共接线归 06。

0. 核对树/解释器/地图/符号；完成：五类最小证据与缺证路径明确，旧读取器产生临时输入。
1. 合同/分组/分母；完成：01 夹具离线可读，未知版本拒绝，恒等式成立。
2. 五类规则；完成：各有 issue/context/unknown 样例，重复不膨胀。
3. 一题与泄漏分档；完成：有证据 issue 配一题，空题/重复明确降级。
4. 集成/回归；完成：finding 可追原证据，旧文件未变，交收据和 diff 白名单。学习有效性另做真人验证。

## 8. 验收、反向证伪与续跑

1. miss 配完备流程零 issue；hit 配违规迟登仍检出。
2. 合规改条件为 context；缺版本链 unknown，不判“事后改口”。
3. 01 只 hash 变不能判沿用；补当时失效且实际引用收据才可判。
4. 后来换阶段不判当时错；当时适用表/标签冲突能检出。
5. 无数据/系统失败不算用户漏检，unverifiable 不当错误。
6. 四来源组不混，看后修改不成为独立用户判断。
7. 多源/节点/扫描/修订不扩大分母，恒等式成立，unknown 不算成功。
8. 未来 verdict/更正不改旧 cutoff；日期不判精确迟登。
9. 跨用户/伪造 owner/越权 ref 拒绝，原判断/画像/方法字节不变。
10. 提交前无答案/结果；模型知结局降档，脱敏不升级；无题 gap。
11. 三条记录只出计数，不出能力/人格结论或百分比。

以下命令供未来实现后在实现工作树根执行；本规格不声明新测试已存在或已通过：

```bash
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests --collect-only -q -k research_diagnostics
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests -q -k research_diagnostics
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest intelligence/tests/test_checkpoints.py intelligence/tests/test_judgments.py intelligence/tests/test_scenario_trees.py -q
/Users/a77/finance-workspace-private/.venv-workbench/bin/python -m ruff check intelligence/services/research_diagnostics intelligence/tests/test_research_diagnostics_*.py
```

先检查 collect-only **选中测试数大于零且 exit code 为 0**，零收集、非零退出或只有旧测试不能算通过，再执行测试。离线、临时用户目录；收据含 revision、命令、收集数、exit code、输入摘要及未知项。

`docs/superpowers/plans/2026-09-13-research-evolution/04/PROGRESS.md` 写步骤、合同版本、夹具、收据及下一步。缺公共依赖先做 unknown/空题；同目录 `BLOCKED.md` 附最小输入、预期/实得、缺字段/适配器、01/06 责任单与续跑步骤，不用假数据过门。
