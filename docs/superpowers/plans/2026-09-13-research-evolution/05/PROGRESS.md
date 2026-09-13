# 05｜用户价值测量与四周试点材料 · 进度

规格来源：`docs/superpowers/specs/2026-09-13-research-evolution/05-product-value-pilot.md`（分支 `docs/river-next-specs`，提交 `194241dd`）。总合同同目录 `README.md`。

## 任务 0（2026-09-13）

| 项 | 值 |
|---|---|
| 开工基线 | `gitea/main` = `5fb13a8c`（与总合同一致；fetch 后重新核对无新提交） |
| 工作树 / 分支 | `/Users/a77/fwp-wt-research-evolution-05` · `feat/research-evolution-05-product-value`，起步 0 个脏文件 |
| 解释器 | `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（主树 venv，Python 3.12.13，pyyaml 6.0.3 可用） |
| 实际用户态根 | `FORESIGHT_USERS_DIR=/Users/a77/.local/share/finance-workbench/users`；`userspace.users_dir()` 解析一致。**本轨代码不读它**，只接显式参数 |
| 主工作区脏改动 | 30 个他人未提交代码改动（river/moneyflow/mfs 等），未迁入 |
| 代码地图 | 主树 `ready n=22076 @b4a35fa`；本轮按精确文件与符号定位，未依赖地图 |

### 现有实现映射（只读，实测读过）

| 基线符号 | 位置 | 本轨如何用 |
|---|---|---|
| `RunStore.load_run / run_dir`，`Run.status / error / degrades / artifacts[].sha256 / user` | `intelligence/services/run_store.py:231-300, 578-615` | `RunStoreEvidenceReader` 只读解析真实 run：失败 run 无 report.json 仍可计失败；`run.user != owner` 判跨用户 |
| `verify_run_binding` 三档 | `intelligence/services/self_use_maturity.py:426-577` | **不复用其成功门**：失败 / 降级 run 必须入分母；只借「真实性 ≠ 成功性」的判据思想 |
| `SelfUseEvent.validated` 时区校验、`dedupe_events` 幂等 | 同上 `:103-199` | 事件时间必须带时区、同键去重的写法对齐 |
| `_token_usage_from_events` / `AgentUsage.input_tokens` | `intelligence/runtime/agent_episode.py:122-160` | 用量 ≠ 账单：`cost_item` 以 `quantity/unit` 记用量，缺 `rate_version` 时 `certainty=unknown` |
| `summarize_context_growth` 的 provenance 分层 | `intelligence/services/context_growth.py` | 「逐调用 / 运行 / 子任务」只选一层 → `coverage_scope` 最粗层去重 |
| `userspace.user_space(user).root` | `intelligence/userspace.py:120-143` | 生产落盘由 06 在 `root/research_evolution/` 做；本轨 CLI 只写显式 `--out-dir` |
| 门禁 | `scripts/layer_audit.py`、`check_unread_fields.py`、`check_path_literals.py` | 新模块全部落 `services/` + `eval/`，结构化 JSON 用字符串键 |

## 完成项（revision：基线 5fb13a8c + 本分支首个提交）

| 日期 | 单元 | 文件 | 检查 | 退出码 |
|---|---|---|---|---|
| 09-13 | 06 接线合同（先交） | `docs/research-pilots/research-evolution/06-integration-contract.md` | 人工核对 spec §3 表与 `contracts.EVENT_TYPES` 一致 | — |
| 09-13 | 合同常量 + 协议冻结 | `intelligence/services/product_value/{contracts,hashing,protocol}.py` | `test_product_value_cli.py::test_cli_freeze_template_then_reject_edits` | 0 |
| 09-13 | 事件校验 / 幂等 / 排序 | `intelligence/services/product_value/events.py` | `test_product_value_events.py`（27 条：时区、负区间、渠道白名单、跨 owner、同 ID 冲突、修订、乱序） | 0 |
| 09-13 | 只读证据解析器 | `intelligence/services/product_value/evidence.py` | `test_product_value_evidence.py`（真实 `RunStore`：失败无报告、跨 owner 不泄漏、产物哈希、状态冲突） | 0 |
| 09-13 | `measure_pair` | `intelligence/services/product_value/measure.py` | `test_product_value_measure.py`（32 条：暂停只扣预登记、并集、前端不覆盖、失败 / 降级入账、费用去重与缺口、同意、无效判定） | 0 |
| 09-13 | `summarize` | `intelligence/services/product_value/summarize.py` | `test_product_value_summarize.py`（22 条：确定性、synthetic 隔离、六对配对达标 / 变慢 / 质量降 / 严重错误 / 漏审 / 只留成功样本、主动复用、回检、续费与退款、成本、曝光不进指标） | 0 |
| 09-13 | 离线 CLI + Markdown | `intelligence/eval/product_value/{cli,render,__main__}.py` | `test_product_value_cli.py`（8 条，含夹具漂移守卫） | 0 |
| 09-13 | 夹具（synthetic）与 README | `intelligence/tests/product_value_fixtures.py` → `intelligence/tests/fixtures/research_evolution/05/` | `validate` accepted 69；`summarize` → pair-01 valid / pair-02 incomplete / pair-03 incomplete；engineering_complete / pending / unstarted | 0 |
| 09-13 | 四周试点材料 | `docs/research-pilots/research-evolution/`（协议模板、任务卡、评分表、邀请、同意、时间费用、访谈、团队证据包、总结模板） | 协议模板可被 `freeze` 冻结（测试覆盖） | 0 |
| 09-13 | 协调方补发件对齐 | 邀请 / README / 访谈提纲：「不荐股」只约束对外输出，试点与维护对象 scope 不过滤个股；CLI 测试改用 `__file__` 定位仓根 | `test_product_value_cli.py` 8 passed；ruff 0 | 0 |

### 协调方补发件（2026-09-13）逐条对 05

| 条 | 对 05 的影响 | 处置 |
|---|---|---|
| 1. 主树未提交的 09-06 / 09-05 设计段 | 主树 09-06 spec 相对 gitea/main 多 222 行，其中与 05 相关只有一句「周活、留存和付费转化是经营指标，不能替代学习效果」，与本轨三态分离一致；05 不消费 pit_grade / 投影契约 | 无需改码；等改动方提交到 main 后无追加依赖 |
| 2. 「不荐股」措辞 | 邀请模板原写「工具只做大盘、板块、题材研判」，比补发件口径更窄 | 已改三处措辞（见上表） |
| 3. spec 目录先合 main | 本分支树里没有 spec 目录（只读了 `docs/river-next-specs`） | 等用户确认合入；合入后本分支无需变更 |
| 工程提醒 | layer_audit / 路径字面量 / 收据按 revision 取时间戳文件 三条已满足；Brier 属 03；分支名映射：05 = `feat/research-evolution-05-product-value` | 无需变更 |

### 收据

- 本轨 5 个测试文件：`100 passed in 1.50s`（`.venv-workbench/bin/python -m pytest -q intelligence/tests/test_product_value_*.py`）
- 全量：`9640 passed, 77 skipped, 2 xfailed`，exit 0，583 s；收据 `~/.finance-runtime/test-receipts/20260913T065932Z-5fb13a8c.json`
- `ruff check .` 0；`scripts/layer_audit.py` 0；`scripts/check_unread_fields.py` 0（无新增未读字段）；`scripts/check_path_literals.py` 0
- 前端 / e2e / registry 未跑（本轨未改前端与注册表；合并前由集成人跑等价 CI）

### 三态自报

- engineering_complete：模块真实计算，合同 / 负例 / 边界通过，可由 06 调用。
- product_verified：**否**，需 06 接真实 UI/API。
- field_evidence：**pending**；commercial：**unstarted**（无外部参与者、无付款）。

## 下一步

1. 06：按 `06-integration-contract.md` 接 writer / 来源盖章 / `RunStoreEvidenceReader` 注入 / `due_rechecks` 供给；先在 ledger-map 登记四类台账。
2. 用户授权后：`freeze` 协议 → 招募 → 按 README 四周表执行；付款只在实际发生后按 `manual_import` 导入。
3. 合并前跑现役等价 CI（含 `intelligence/webapp` 的 lint/typecheck/test/build 与 e2e），合并 main 等用户确认。

---

## 2026-09-13 返修（评审 PV1 / PV2 / PV3）

独立评审在 `f2a12fa3` 那轮的五轨报告里给本轨记了三条 P1（[review.md](/Users/a77/.finance-runtime/reviews/research-evolution-20260913/review.md)）：
本轨 100 个测试全绿，却漏掉了这三个反例——三条都是「缺记录被当成好消息」的同一个形状。
每条都先写调用真实 `measure_pair` / `summarize` 的回归测试、证明现版红，再改实现。

| 编号 | 根因 | 修法 |
|---|---|---|
| PV1 | `measure._quality_for_task` 只在「有 scopes 但不含 blind_review」时排除评审，`scopes is None`（根本没有同意记录）被当成已同意；`summarize` 又只排除 `invalid` 收据，于是缺同意只留一条 limitation，判据照常 pass | 未知同意范围与明确未授权同样不进质量读数（`exclusions.reason=blind_review_consent_unknown`，质量 `unknown`）；`summarize` 从收据的 `consent_unknown:*` 认出缺同意配对，`completion_quality` / `time_saving` 判据改 `unknown`，新增未知类型 `consent`（与 `gap` 同属缺口家族，`field_status` 因此进 `inconclusive`），受影响配对逐条进读数 `unknown` |
| PV2 | `summarize` 的完整成本只看收据**主动列出**的 unknown，没有对照「全部已分配任务」和合同要求的费用类别，于是只有 writer/review 两笔 CNY 0.46 也报 `full_cost_status=known` | 完整性现在检查两个集合：① 已分配但没有任何测量收据的任务 → `unmeasured_task:<task_id> / no_measurement_receipt_for_assigned_task`；② `contracts.COST_COMPONENTS` 里整份试点一条账都没有的类别 → `cost_category:<component> / cost_category_unobserved`。真的不存在的类别在冻结协议 `criteria.cost.not_applicable_components` 事前声明才豁免（进协议哈希，事后改不了）；毛利随 `full_cost_status != known` 保持 null |
| PV3 | `summarize` 的复用分母是 `sorted(reuse_rows)`，而 `reuse_rows` 只在处理 `reuse_observed` 时创建，没复用的人从不出现 → 六人一复用报 100% | 分母改为**激活队列**：可信 `task_started` 或复用记录自带的 `activation_at` 建激活时刻，观察周以声明的 `observation_window.end` 为准、没声明就按 `criteria.proactive_reuse.observation_weeks`（默认 1，激活当周之后再走完 1 个整周）推。窗口已完整的人全部进分母，没走完的进 `unknown(observation_window_incomplete)`，激活时刻不明的进 `unknown(activation_unknown)`；分母里没有复用观察记录的人**留在分母**（比率抬不高）并列 `unknown(reuse_observation_missing)`，同时让判据 `unknown(gap)` |

### 新增测试（修前红 → 修后绿）

| 测试 | 修前实得 |
|---|---|
| `test_missing_consent_record_blocks_blind_review_quality`（measure） | `quality.status == "reviewed"`，缺同意仍算出可比质量 |
| `test_missing_consent_makes_quality_and_time_saving_unknown` | `completion_quality.verdict == "pass"` |
| `test_consented_pairs_still_reach_a_verdict` | 反向钉，修前修后都绿：同意齐全的样本没被误伤 |
| `test_assigned_task_without_cost_evidence_blocks_full_cost` | `full_cost_status == "known"`（两条无测量无账目的任务照样入账） |
| `test_unobserved_cost_categories_are_unknown_not_zero` | `full_cost_status == "known"` |
| `test_declared_not_applicable_cost_categories_stop_being_gaps` | `KeyError: 'not_applicable_components'` |
| `test_reuse_denominator_counts_activated_participants_without_reuse` | `denominator_ids == ["p04"]`，六人只认一人 |
| `test_reuse_window_not_yet_complete_stays_out_of_denominator` | 窗口未完成的人既不在分母也不在 unknown，直接消失 |

### 改掉的旧期望（评审已判定旧值错误，不是为了让测试变绿）

- `test_synthetic_inputs_never_become_field_or_revenue`：`proactive_reuse` 由 `fail` 改 `unknown`，并补钉分母 `p01–p06` / 分子 `p04` / 0.1667。旧 `fail` 建立在「分母只有 p04–p06」之上，而 p01–p03 也已激活——旧值正是 PV3 那个漏掉非复用者的分母。
- `test_cost_unknown_blocks_gross_margin`：`unknown_component_count` 由 1 改 10，并逐条钉住是哪 9 个类别缺账。旧值只数收据自己列出的 1 项，等于默认「没观察到的类别 = 没花钱」，正是 PV2。

### 材料同步

`protocol.yaml`（两个新判据键与用法注释）、`summary-template.md`（`consent` 未知类型、复用分母、成本完整性口径）、`06-integration-contract.md`（新增第 8、9 条：`reuse_observed` 必须覆盖整个激活队列；试点级费用由 06 补 `cost_recorded`）、`README.md`（第 3 周动作）。

### 收据

- 本轨 5 个测试文件：**108 passed, 0 failed, 0 skipped**，exit 0
  `cd /Users/a77/fwp-wt-research-evolution-05 && /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest -q -p no:cacheprovider intelligence/tests/test_product_value_cli.py intelligence/tests/test_product_value_events.py intelligence/tests/test_product_value_evidence.py intelligence/tests/test_product_value_measure.py intelligence/tests/test_product_value_summarize.py`
  （基线 100；+8 新增。收据按 revision 取 `~/.finance-runtime/test-receipts/` 的时间戳文件，不读 `latest.json`——该目录多树共用。）
- `ruff check` 改动的四个 py 文件：All checks passed
- 评审探针 `probe_05.py` 五个场景修后实得：`base_cost.full_cost_status=unknown(unknown_components_present)`、`unmeasured_cost=unknown`、六对无同意 `completion_quality/time_saving = unknown(consent)`、单对 `quality.assisted={"status":"unknown","reason":"blind_review_consent_unknown"}` 且 `assisted_not_lower=None`、`reuse 0.1667 分母 p04–p09 分子 p04`
- 未跑：全仓 / 前端 / e2e / registry（本轨只动 product_value 与本轨材料，无其它模块引用；合并前由集成人跑等价 CI）

### 边界（本轮刻意没做）

- **没有**把队列级 `reuse_observed` / `recheck_*` 也挂上同意门。评审 PV1 针对的是配对测量与效果判据；队列级事件的同意门会把 PV3 的分母重新打散（缺同意记录的人被删掉），与 PV3 的验收钉冲突。要做得由 06 在写入端保证队列同意齐全，届时另开一条。
- **没有**把「有收据但没有任何费用条目的任务」判成缺口：原流程任务本来就没有模型费用，它的成本是人工工时（走 `timing`，不在 `COST_COMPONENTS` 里），一刀切会造假缺口。
- 三态不变：`engineering_complete`；`product_verified` 仍需 06；`field_evidence` 仍 pending。

## 2026-09-13 QC 第二轮（扩大边界复审）

QC（`~/.finance-runtime/reviews/research-evolution-repair-qc-20260913/`）结论：原 13 项固定反例转绿，扩大边界确证 8 项，本轨 2 项 P1。决策展开见 `docs/handoffs/2026-09-13-product-value-05-qc-round2.md`。

- **PV4[P1] 空壳收据核销缺口**：`measured_task_ids` 只查 task_id 存在性。修复：`_receipt_task_is_measured` 逐任务核验（终态 / 尝试 / 耗时至少观测一样），「无收据」与「收据在但没测」（`measurement_receipt_without_task_evidence`）分列。
- **PV5[P1] 后续窗口收缩分母**：分母取每人最晚 window.end，后续未结束窗把已完成观察周者移出分母（2/6 fail → 2/3 pass，本轮新回归）。修复：资格 = 任一完整窗（`completed_window_end`），后续窗另列 `later_observation_window_incomplete`。
- 修复提交 **`24bce5e8`**；新增 2 条回归测试先红后绿；本轨 110 passed；全仓 9650 passed / 77 skipped / 2 xfailed；ruff 干净；QC 探针 `probe_05_extra.py` 复跑双绿。
- **06 联测请用 `24bce5e8`**。口径纠偏：上轮「13 项已修复」实为「原 13 项固定反例转绿」；「41 条测试先红后绿」不准确（至少 `test_consented_pairs_still_reach_a_verdict` 修前修后都绿）。

## 2026-09-13 QC 第三轮（PV6/PV7）

- 独立复核（`~/.finance-runtime/reviews/research-evolution-round3-qc-20260913/`）：原 8 项固定反例通过，扩大边界确证 5 项新问题，本轨占 2 项 P1：PV6（PV4 相邻遗漏——`terminal_state != open` 直接当作已测量，放弃终态空壳把完整成本 unknown→known、缺口 2→0）、PV7（PV5 相邻遗漏——分母资格推导被 `participant not in declared_window_end` 阻断，追加未来窗把激活成熟者移出分母，3/6 unknown→3/3 pass）。
- 修复 `2f0d3410`：PV6 核销费用缺口只认任务级成本事实（attempts 或有锚点的耗时），终态证明任务状态不证明费用，原流程「无 run 但有人工计时」通路保留；PV7 无已完成声明窗时按激活时刻推导，推导窗成熟即取得资格，与是否存在未来声明窗无关，后续窗仍只增缺测标签。
- 验证：新增 2 条回归测试先红后绿（PV6 前端/服务端两种放弃输入；PV7 追加未来窗前后分母/比率/判据不变）；模块 112 passed；全量 9652 passed / 77 skipped / 2 xfailed（最终 SHA 干净树 @2f0d3410，回应 QC 对上轮脏树收据的意见）；ruff 干净；QC 第三轮探针 05 组复跑——PV6 两源 full_cost 仍 unknown、known 仍 CNY 0.46、缺口 2；PV7 分母保持 q1..q6、rate 0.5、verdict unknown；安全断言 test_new_boundaries.py 由 5 failed 转 5 passed；第二轮 probe_05_extra.py 复跑不回归。
- 06 联测请用 `2f0d3410`。

## 2026-09-13 QC 第四轮（PV8）

- 独立复核（`~/.finance-runtime/reviews/research-evolution-round4-qc-20260913/`）：本轨占 1 项：PV8[P1]（PV6 相邻遗漏——辅助任务只有开始/放弃时间戳、无 run/用量/费用事实时，计时证据仍核销其模型成本，完整成本 unknown→known）。
- 修复 `197133f2`：人工计时覆盖与辅助服务费用覆盖分开——核销辅助任务成本只认费用事实（attempts 非空，或 cost_items 里 selected 且 task_id 匹配的条目），否则列 `assisted_task_without_usage_or_cost_evidence`；原流程任务按设计不用模型，计时即覆盖（PV4 合法通路保留）；同任务被后续收据补上费用事实时解除阻断。
- 验证：新增回归测试先红后绿（计时仍被测量 end_to_end=20、attempts=[]、cost_items 空，负控同测）；模块 113 passed；全量 9653 passed / 77 skipped / 2 xfailed（干净树 @197133f2）；ruff 干净；QC 第四轮探针 05 组 before/after 均 unknown、known 仍 CNY 0.46，安全断言 4 passed；第一/二/三轮归档探针 05 组复跑不回归（PV7 分母 q1..q6、rate 0.5、verdict unknown 保持）。
  - **归因更正（第五轮 QC 指出）**：首跑唯一失败项经收据 `20260913T125455Z-197133f2.json` 的 failed_ids 核对是 `intelligence/tests/test_workbench_conversation_integration.py::test_real_conversation_round_trip_persists_skills_sse_and_three_turns`（10s 墙钟超时型已知 flaky，隔离 3/3 绿），不是本条原写的 test_pipeline_p0——当时 grep 输出匹配了名字里带 failed 的用例。「全量重跑通过」成立；「原失败项单跑通过」当时未验证，本轮已补上隔离 3/3 绿的证据。教训：列失败用 `-rf` 或读收据 failed_ids。
- 06 联测请用 `197133f2`。

## 第五轮（2026-09-13，QC round-5 复审：PV9）
- 状态：原四轮修复复核有效，但扩大边界确证 1 项新问题（PV9[P1]；01 另有 J8/J9/J10），整包暂不签收；同时更正第四轮失败归因（见第四轮条目内批注）。
- 修复（`340d3b26`，1 条新测试先红后绿）：PV9[P1]（PV8 相邻遗漏）——辅助任务无 run 时的费用核销改为按协议适用集 ∩ 固有模型组件 {writer_model, review_model} 逐个核验，一笔工具费或只有 writer 的账不再替缺失的模型费作证；合法对照（writer/review/tool 三件套）known CNY 0.93。
- 验证：模块 114 passed；QC 第五轮安全断言 test_round5.py 5 passed；全量 9654 passed / 77 skipped / 2 xfailed（干净树 @340d3b26，`-rf` 无 FAILED 行）；ruff 干净；第一至四轮归档探针 05 组复跑不回归（PV7 分母 q1..q6、rate 0.5、verdict unknown 保持）。

## 第六轮（2026-09-13，QC round-6 复审：PV10）
- 状态：第五轮修复复核有效，扩大边界确证 1 项（PV10[P1]，PV9 相邻遗漏；01 另有 J11/J12），整包暂不签收。
- 修复（`cf7e05a5`，1 条新测试先红后绿）：组件级核验贯穿有 run 分支——_assisted_task_uncovered_components 不再对 attempts 早退，费用关联认 task_id / run_id / attempt_id；阻断条目带 uncovered_components；有 run 阻断理由单列 assisted_task_model_cost_unbilled。全失败辅助任务不按固有组件拦（review 未发生，缺账由 retry 派生缺口表达）——failed_retry pin 10→11 并注明语义来源。
- 验证：模块 115 passed；QC 第六轮安全断言 6 passed（no_fees/tool_only/writer_tool unknown、三件套 known 0.93、receipt 零拒绝）；全量 9655 passed / 77 skipped / 2 xfailed（干净树 @cf7e05a5，`-rf` 无 FAILED 行）；ruff 干净；第一至五轮归档探针 05 组复跑不回归（probe_05_extra 输出与 QC 第六轮归档归一后逐字节一致）。

## 第七轮（2026-09-14，QC round-7 复审：PV11/PV12/PV13）
- 状态：第六轮修复复核有效（01 无新增阻断，02/04 保持候选），05 扩大边界确证 2 项 P1 + 1 项 P2，整包暂不签收。
- 修复（`72f562f2`，3 条新测试先红后绿）：
  - PV11[P1]：费用覆盖改「任务 × 执行实例 × 组件」——逐 attempt 核验，第一次执行的完整模型账不再为第二次作证（第二次仅工具费 0.01 修前 known 0.93 → 修后 unknown）；合法对照两次都齐 known CNY 1.39。
  - PV12[P1]：移除全失败早退——失败执行实例仍要 writer 账（失败不代表模型没调用；review 未发生不要求）；失败 run 挂工具费不再洗白；合法对照 writer+工具费 known。
  - PV13[P2]：uncovered_components 穿过公开投影层（unknown 条目条件携带），公开输出加断言。
- 验证：模块 118 passed；QC 第七轮安全断言 test_round7.py 8 passed（修前 4 failed / 4 passed）；全量 9658 passed / 77 skipped / 2 xfailed（干净树 @72f562f2，`-rf` 无 FAILED 行）；ruff 干净；第一至六轮归档探针 05 组复跑不回归。

## Round-8 附加条件（2026-09-14，QC：联合身份校验）
- 状态：第七轮 PV11/PV12/PV13 逐项通过；QC 确认 05 模块 118 passed、第七轮安全断言 8 passed、ruff 干净、dirty=0（全量收据视为已提供历史收据，未独立重跑）。附条件：attempt_id/run_id 联合身份校验仍有相邻 P1，修前 dd5d54aa 之前的实现可复现。
- 修复（`dd5d54aa`，1 条公开入口回归测试先红后绿）：逐 attempt 覆盖的 OR 匹配改为联合身份——条目带 attempt_id 就必须与 run_id 一致（错配组合：attempt_id 指第二次执行、run_id 是第一次的 run，三笔费用修前洗成 known 1.39 → 修后 unknown 且 uncovered_components=[review_model, writer_model]）；只带 run_id 的条目是该 run 共享账。合法对照：同一组费用联合一致（run2×attempt2）→ known CNY 1.39。
- 验证：模块 119 passed；第一至七轮安全断言复跑全绿（05extra exit=0、round3 exit=0、round4/5/6/7 = 4/5/6/8 passed）；全量 9659 passed / 77 skipped / 2 xfailed（干净树 @dd5d54aa，`-rf` 无 FAILED 行）；ruff 干净。

## Round-8 补遗（2026-09-14，QC：合并身份冲突 + 收据层联合身份）
- 状态：round-8 附加条件修复（dd5d54aa）原错配反例已修好，但扩大边界确证两个相邻 P1（均在父提交存在，非本次修复引入的回归），05 暂不签最终放行。
- 修复（`95a4efea`，2 条公开入口回归测试先红后绿）：
  1. **合并前不验身份**（measure.py 尝试合并循环）：`attempts.setdefault` 保留第一条 run_id，同 attempt 后续事件绑到不同 run 时静默丢弃——第二次执行连同缺账消失（QC 实测：run 冲突对 + 只给 run1 完整费用 → 修前收据 valid、known 0.93）。修复：合并前校验 run 身份冲突，显式留错（limitations `attempt_run_conflict:` 阻断前缀 + unknown_cost_components 显式条目 reason=attempt_run_conflict），收据降级 incomplete、完整成本阻断；不合并冲突事件的时间/状态。
  2. **收据层 OR 核销**（measure.py 派生缺口）：`run_id ∈ costed_runs or attempt_id ∈ costed_attempts`——错配费用在汇总层已拦（dd5d54aa）但收据自身仍 valid、缺口为空；06 独立保存展示收据，读收据的消费者看不到缺账。修复：联合身份谓词上移 `contracts.cost_item_covers_attempt`（公共合同），测量层核销与汇总层覆盖共用——错配费用不为任何执行作证，缺口留在收据并降级 incomplete（spec：覆盖不明为 incomplete，缺账保留未知）。
- 验证：模块 121 passed（119+2）；第一至七轮安全断言与归档探针复跑全绿（05extra exit=0、standards_01/02/04/04_boundary OK、original_probe_05 内容 OK、round4/5/6/7 = 4/5/6/8 passed）；全量 9660 passed / 1 已知 10s 墙钟 flaky（隔离 3/3 绿）/ 77 skipped @95a4efea；ruff 干净。
- 复跑教训：probe_05_extra 的 argv 是树路径不是 SHA——传错参数会报 ModuleNotFoundError 假「回归」，先读探针契约再下结论。
