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
