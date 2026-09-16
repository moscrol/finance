# 05｜用户价值测量与四周试点材料

状态：待执行；本轮只产出规格。负责人：05 agent。共享入口与持久化集成：06 agent。

## 1. 目标、起点与边界

交付离线测量模块与四周试点包：核对同等任务省时且质量不降、主动复用/回检、全部服务成本和真实续费。没有外部参与者时，真实效果为 `pending`，商业为 `unstarted`。

`self_use_maturity.py` 已有真实 run 绑定、失败/降级入账与去重；自用 `useful` 不等于产品效果。`RunStore` 有 run/trace/stream 和哈希产物；`context_growth.py` 区分逐调用/运行/子任务汇总。额度不是账单，总 tokens 不证明完整费用。

BP 版本差异遵循总规格说明；不改 BP 或用户已授权的大盘/板块研究能力。商业依据见 [调研笔记](/Users/a77/agent-memory/00_inbox/2026-09-13-time-river-commercial-research.md)。

准备材料不构成外发授权；邀请、收费、招募、访问第三方私有资料须执行人另获用户相应授权。首版不建团队系统或数据/API 销售。

## 2. 任务 0 与独占范围

按项目要求读取分支/脏文件、session facts、交接与代码地图；复核读取面，留下文件/函数索引，不迁入别人的未提交改动。

- 只读：上述三模块、`intelligence/runtime/agent_episode.py` usage/预算、run 协议、BP/相关规格。
- 独占写入：`intelligence/services/product_value/`、`intelligence/eval/product_value/`、`intelligence/tests/test_product_value_*.py`、`docs/research-pilots/research-evolution/`，以及总合同指定的本轨夹具/进度目录。
- 06 独占：UI/API、服务端钩子、userspace、公共 schema/注册表、`docs/learning/ledger-map.md`；注入事件/收据存储端口。

先交 06 合同，再用临时目录完成算法。白名单外需求交 06。进度统一写 `docs/superpowers/plans/2026-09-13-research-evolution/05/PROGRESS.md`，记 revision/完成项/检查/下一步；同目录 `BLOCKED.md` 区分工程依赖与真人试点未开展，继续独立工作。

## 3. 数据与集成合同 v1

05 定义合同、验证、汇总和离线 CLI；06 唯一写 canonical 原事件并管理身份/授权/生产存储。归属统一 `owner_user_id`，参与者假名化；原文、凭据、联系表不入代码仓。模块只接受显式参数。

### ProductValueEvent

字段均必填；未知用 `null + reason`。

| 字段 | 合同 |
|---|---|
| `schema_version,event_id,event_type` | `product-value-event/v1`；稳定事件 ID；同 ID 同内容幂等，不同内容拒收并记冲突 |
| `owner_user_id,pilot_id,participant_id` | 归属及假名；跨 owner 引用拒绝 |
| `task_id,case_id,case_version,case_pair_id` | 一个任务可有多次 run；配对标识不能靠相同问题文本猜 |
| `run_ids[],object_refs[]` | 真 run 引用及 `{kind,id,namespace,version_or_hash,scope}`；scope 保留 conversation_id/run_id。原流程可无 run，但需人工计时/产物依据 |
| `assistance_condition` | `original|assisted`；原流程保留参与者平常合法使用的工具，列工具版本与实际辅助 |
| `event_at,recorded_at` | 发生和登记时间均带时区；补录保留两者，不回填成实时事件 |
| `source_version` | `code_sha,protocol_version,artifact_hash` |
| `provenance` | `observed|imported|synthetic`，另含 `source_ref,source_hash`；仿真不能进入真人分母 |
| `payload` | 按类型验证，含 `initiator,assistance_source`，不能推断主动 |

允许迟到/乱序，按发生时间与版本排序；修订带 `supersedes_event_id`。事件可信来源由 06 按接收入口/凭据判定，客户端不能自选 `observed` 或升级身份。所有 payload 均有 `initiator,assistance_source`，另有下表最低字段；F=前端动作上报，S=服务端事实/计算，M=经权限校验的人工导入（带 `importer_id,evidence_ref,evidence_hash`）。

| `event_type` | payload 最低字段 | 可信来源 |
|---|---|---|
| `assignment_created` | `protocol_hash,assigned_at,condition,case_pair_id,completion_condition,deadline` | M；S 校验冻结协议后登记 |
| `task_exposed,task_selected,task_started` | `task_id,policy_version,view_id,client_at` | F；S 补接收时间与有效任务范围 |
| `run_started,run_finished` | `run_id,attempt_id,status,error_ref` | S 读取真实 run；失败重试逐次保留 |
| `task_completed,task_failed,task_abandoned` | `task_id,completion_evidence_refs,terminal_reason` | S 核对完成条件或 M 裁决；F 可表达放弃意图，不能自报成功 |
| `time_interval` | `interval_id,start,end,activity,clock_source,pause_reason,visibility` | F 仅报客户端区间；S 给 run/接收时钟；M 补原流程或外部查阅 |
| `quality_reviewed` | `rubric_version,reviewer_id,blinded,artifact_refs,dimensions,severe_error_count` | M 独立评审，非前端自评分 |
| `manual_assistance` | `helper_id,task_id,start,end,help_kind` | M；保留实际/估算标识 |
| `reuse_observed` | `first_task_id,new_task_id,activation_at,reminder_refs,observation_window` | S 按启动和提醒事件推导，缺来源为 unknown |
| `recheck_viewed,recheck_completed` | `object_ref,verdict_ref,action_id,evidence_refs` | viewed 可 F；completed 由 S 核对确认/修订动作，打开不算完成 |
| `cost_recorded` | `cost_item`（见下文完整结构） | S 用量/费用证据，或 M 账单/费率/人工数据；前端不得自报金额 |
| `consent_changed` | `consent_version,scopes,effective_at,action,terms_hash` | F 表达本人选择；S 保存生效记录，M 需同意凭据 |
| `payment_recorded` | `payment_ref,amount,currency,service_period,status,verified_by` | 仅 M 凭据导入；退款单列关联原付款，不触发支付 |
| `exercise_submitted` | `exercise_id,exercise_version,submission_ref,submitted_at` | F 提交；S 保存并记录后续答案揭示时间，不冒充学习效果 |

`task_*` 计逻辑任务，`run_*` 计执行尝试；多次失败后完成仍是一个分配任务，尝试成本全部保留。F 的计时和完成意图不能覆盖 S/M 证据；无 run 的原流程通过 M 入账，不伪造 Workbench run。

### MeasurementReceipt

`schema_version=measurement-receipt/v1, receipt_id, owner_user_id, pilot_id, case_pair_id, protocol_version, generated_at, input_event_ids[], input_hash, source_versions, status(valid|incomplete|invalid), limitations[]`。

测量主体包含：

- `timing`：两流程起止、用户主动/等待/人工救援分钟、来源和暂停理由。重叠区间求并集，救援工时另计；端到端耗时只扣预登记暂停。
- `quality`：`rubric_version, reviewer_id, blinded, artifact_refs, dimensions, severe_error_count, adjudication_ref`；没有评审即未知，不用模型自评分补齐。
- `cost_items[]`：`cost_id, component, run_id, attempt_id, span_id, coverage_scope, quantity, unit, amount, currency, certainty(known|estimated|unknown), evidence_ref, rate_version, allocation_rule`。费用类别覆盖写手、自审/其他模型、工具、失败重试、人工导入/救援/维护、数据授权、托管及获客分摊。
- `known_cost_by_currency, estimated_cost_by_currency, unknown_cost_components[]`：原币种并列，无可靠汇率不合并；估算不冒充实付，未知不归零。
- `numerator_ids, denominator_ids, exclusions[{id,reason,rule_version}]`：每项指标能追到原事件；排除必须命中事前规则，失败/放弃/退出不能为了改善读数删除。

费用按覆盖集合去重，逐 span/运行汇总选一层，已包含子任务不再加；覆盖不明为 `incomplete`。失败重试全纳入；缺账单/费率保留用量与未知。人工估时为 `estimated`，预算及未观察到调用均不作零费用依据。

### PilotSummary

`schema_version=pilot-summary/v1, summary_id, owner_user_id, pilot_id, generated_at, protocol_hash, cohort_window, source_receipt_ids[], source_versions, metrics[], criteria_results[], engineering_status, field_status(pending|collecting|observed|inconclusive), commercial_status(unstarted|observed), limitations[]`。

metric 带数值/`null`、分子/分母 ID、排除、未知和覆盖率。夹具只改变工程状态；样本不足、漏审、缺同意时判据为 `unknown`。`observed` 表示有真实读数，不表示效果成立。

接口：`validate_event(event)`、`measure_pair(events,protocol,evidence_reader)`、`summarize(receipts,assignments,protocol)`。纯函数返回合同；注入的只读解析器返回缺失/篡改/跨用户原因。CLI 显式输入/输出目录，生产保存交 06。旧输入若已有 version/hash，由 06 显式适配为 version_or_hash 并保留来源；缺命名空间或版本不能靠文本猜。

## 4. 四周试点与预登记判据

提供 `protocol.yaml`、等价任务卡、评分/邀请/访谈/同意/时间费用/总结模板。采集前冻结协议哈希及任务/评分版本；改判据另开分组。以下为经营判据，不证明统计显著或策略有效。

两类任务：事实/计算核对；旧判断变化/回检。A/B 案例匹配难度、来源规模、截止时点和交付；原/辅助流程交叉、顺序预分配，同人不重复同案。保留常用工具、熟悉程度和人工帮助。

| 周期 | 动作和产物 |
|---|---|
| 第 1 周 | 执行人取得授权后招募 3–10 人；明确同意与退出方式，登记常用工具，完成首组配对任务；另计首次配置时间 |
| 第 2 周 | 完成另一类配对任务；独立盲审产物；收集改错、帮助、等待和失败全链记录 |
| 第 3 周 | 提供到期回检入口，观察无人工催促的主动复用；正常系统提醒与人工提醒分别标记 |
| 第 4 周 | 回检与访谈，核对费用与遗漏，按冻结标准产出总结；付款/续费只有已授权且实际发生才登记 |

邀请说明任务/四周安排/耗时/数据用途/退出及无收益承诺，不索取交易账号。同意分研究、日志、盲审、团队共享、外部展示，默认不含后两项；记录有效期、撤回/删除和哈希，退出计数保留、明细依同意处理。

盲审四维各 0–2：事实出处、计算、假设缺口、任务完成，总分 8。关键事实/计算错误为严重错误；争议留裁决，无法盲审列偏差。

| 指标 | 固定判据与分母 |
|---|---|
| 完成与质量 | 分母全部已分配任务含失败/放弃；辅助完成率不低于原流程、严重错误 0、每个有效配对总分不低；漏审 unknown |
| 省时 | ≥3 人、6 完整配对、两类任务；配对 `(原耗时−辅助耗时)/原耗时` 中位数 ≥20%；原耗时 0 排除比例并列明；同时显示全部分配任务的超时/未完成率 |
| 主动复用 | 分母为激活后进入完整观察周者，至少 3 人；≥50% 另一周本人启动核心任务且前 72 小时无人工催促；系统提醒单列，来源未知不计主动 |
| 回检 | 分母为截止时到期且可访问的判断，未到期单列；核对事实并确认/修订才算完成，展示比率 |
| 成本 | 纳入全部任务/重试/帮助；已知/估算/未知/人工工时并列，缺项时完整成本/毛利 unknown |
| 续费 | 分母为真实首付后到期进入续费窗口者；分子须第二期实付/权益期/凭据，退款冲回；意愿/免费延长不算，零分母 null/unstarted |

省时/质量/主动复用达标只建议继续验证；质量红暂停扩招，缺测继续观察。四周未到续费期则保留待测。未见案例的独立解释/迁移仅作探索指标。

小团队材料：“周会证据包＋交接”访谈/样例；问研究员/负责人交接的重做、审阅、预算和样本；样例列冻结依据、变化、分歧、负责人/复核日期。测准备时间/遗漏/依据还原；私有判断不默认共享，意愿不算订单。

## 5. 工程执行与验收

顺序：任务 0 → 合同/纯函数 → 离线入口/反例 → 材料 → 06 接线。按本仓解释器跑新增测试及改动范围 ruff，记 revision/命令/退出码；不部署或合并。

离线验收必须自动覆盖：

1. 同输入反复汇总语义内容相同（`generated_at` 单列），乱序与重复不改分母；同 ID 改内容拒绝。
2. 失败 run 无报告仍能计失败与已知费用；降级如实入账，不能被成功绑定规则剔除。
3. 总 tokens 缺费率、自审缺用量、重试未知、人工未计、混币种均保留缺口；父子汇总不重算。
4. 助手快但质量下降、严重错误、只保留成功样本、缺盲审分别阻止效果通过。
5. 重复案例、辅助条件错配、版本/截止时点不符、负时间或时区缺失，拒绝/标无效并留理由。
6. 无用户、无到期对象、无真实首付时分母为 0、值为 null；仿真夹具不能变真人成功或收入。
7. 人工催促复用不算主动；自动回检未经用户核对不算用户完成；聊天长度/访问量不进入效果指标。
8. 跨 owner 引用、产物哈希不符、撤回同意超范围、付款凭据缺失均不进入有效测量。

夹具含完整配对、失败重试、费用缺失、空真人队列，均标 `synthetic`。`README.md` 给命令/预期状态，输出 JSON 与 Markdown。完成：反例通过、材料齐全、06 收到接线清单、工程/真人/商业状态分离；真实试点未开展不影响工程交付。
