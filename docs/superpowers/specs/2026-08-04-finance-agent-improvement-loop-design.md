# 金融 Agent Improvement Loop 集成设计

- 日期：2026-08-04
- 状态：待用户审阅
- 范围：把 OpenAI Cookbook `agent_improvement_loop.ipynb` 的改进闭环思想，接入现有金融 Agent 的 run trajectory、验收、学习和 Codex 交接流程
- 参考 notebook：[`agent_improvement_loop.ipynb`](https://github.com/openai/openai-cookbook/blob/05fe56240be4a27b1f6b3f424cb2e3c9bcf9980e/examples/agents_sdk/agent_improvement_loop.ipynb)，固定版本 commit `05fe56240be4a27b1f6b3f424cb2e3c9bcf9980e`
- 本文性质：设计文档，不包含本轮代码实现

## 1. 摘要

Cookbook notebook 展示的是一条外部改进循环：

```text
真实运行
  -> trace
  -> 人工/模型反馈
  -> feedback-derived eval
  -> eval gate
  -> 优化诊断
  -> Codex handoff
  -> 修改 harness
  -> 下一轮运行
```

金融 Agent 已经有其中的大部分零件，但这些零件分散在不同边界中：

- `run_store` 和 `trace-profile` 负责保存运行事实；
- `synthesis_health`、acceptance verdict、claim/evidence gate 负责验收；
- `corrections`、`experience_cards`、forecast reflection 负责用户和预测学习；
- handoff、verification report 和 Codex 分支负责工程修改。

本设计不引入 HALO 作为新的运行时，也不把 Promptfoo 回放旧答案当成生产发布门。设计的核心是增加一条**改进账本（Improvement Ledger）**，把以下对象绑定起来：

```text
run_id
  -> first_bad_step / finding_id
  -> fix_type
  -> eval_candidate_id
  -> approved_case_id
  -> implementation_revision
  -> verification_run_id
  -> prediction_outcome
```

目标不是让 LLM 自动修改金融 Agent，而是让每次已确认的问题都能变成可审核、可冻结、可验证的长期工程资产。

## 2. 参考内容：Cookbook 每章在做什么

| Notebook 章节 | 参考内容 | 对本设计的启发 | 不直接照搬的原因 |
| --- | --- | --- | --- |
| 开篇、What you will build（cells 0-1） | 把 prompt、工具、路由、输出和校验统称为 harness，并把 trace、反馈、eval、Codex 串成飞轮 | 改进对象必须是完整 harness，不只是 prompt | 金融 Agent 的事实、PIT、证据层和发布门比示例更严格 |
| Prerequisites（cell 2） | live Agents SDK、Promptfoo、HALO，多模型调用 | 明确每一环的运行成本和外部依赖 | 生产闭环不能依赖每轮 live LLM 才能判断结构性事实 |
| Step 1：synthetic data（cells 5-9） | 生成包含 ARR、NRR、客户集中度和 SOC 2 冲突的虚构 dataroom | 用受控冲突材料测试证据优先级和未知处理 | 金融 Agent 必须使用真实 PIT 数据和来源链，不能用合成材料替代验收 |
| Step 2：define analyst（cells 10-29） | 用 `AgentConfig`、工具政策、输出 artifact 和 SDK sandbox 明确 harness | 建立金融 run 的 harness manifest，并冻结版本、预算、路由、产物契约 | 当前实现跨多个模块，不能再造第二套路由或第二个输出契约 |
| Step 3：traced runs（cells 30-33） | 跑五个问题并保存答案、artifact、SDK span | 把每次真实 run 作为可追溯事实源 | 五题示例覆盖不足，金融验收必须区分自然 run、replay、canary、benchmark |
| Step 4：feedback（cells 34-35） | 人工反馈和 LLM insight 分开记录 | 保留用户纠偏、人工分诊和模型观察的来源区分 | notebook 的人工反馈是 mock，不能当作金融领域金标准 |
| Step 5：generated evals（cells 36-37） | LLM 从 trace 和反馈生成 rubric、字面断言和通过/失败示例 | 允许 LLM 生成候选 Eval，减少把经验写成测试的成本 | 生成结果不能直接进入正典或 CI，必须人工审核、证据绑定、版本化 |
| Step 6：Promptfoo gate（cells 38-42） | 对已有 trace output 运行 `contains`/`llm-rubric`，得到 gate 结果 | 将已确认反馈转成可重跑测试 | 当前 provider 只是回放旧答案，不能证明候选 revision 通过；确定性门禁仍优先 |
| Step 7：HALO（cells 43-51） | 汇总 harness、trace、反馈和 gate，输出排序后的 Codex handoff | 建立机器可读的 Finding、推荐、验证预测和 handoff | 不引入 HALO runtime；当前需要的是证据和预测账本，不是另一层 LLM optimizer |
| Step 8：Codex handoff（cells 52-53） | 将报告交给 Codex 或开发者修改 harness | 将 Finding、Eval 和验证标准作为 Codex 输入 | 不允许 handoff 自行改变正典、合并 main 或绕过发布门 |
| Step 9：close the loop（cells 54-56） | 修改后重新运行同一 eval，支持人工门或自动化门 | 把修复结果回填到同一条 lineage | notebook 只描述闭环，没有在 notebook 内真正执行下一轮 |

## 3. 当前系统对应关系

### 3.1 已有的事实层

`intelligence/services/run_store.py` 已将一次请求落成用户隔离的 run 目录：

```text
users/<user>/runs/<run_id>/
  run.json
  trace.jsonl
  answer.md / report.json / other artifacts
```

`trace.jsonl` 是 append-only，适合边跑边写、刷新后重放和崩溃定位。`docs/trace-profile.md` 已记录 trace 深度、语义 epoch、字段陷阱和跨 harness 映射规则。

这部分继续作为**不可变事实源**。改进流程不得重新解释或覆盖原始 trace；任何后处理都写 sidecar。

### 3.2 已有的执行与输出合同

当前执行路径分布在 TaskFrame、question router、skill router、owner DAG、AnswerSpec、DecisionBrief、composer、judge 和公开 artifact 中。

对应 Cookbook 的 `AgentConfig`，本项目需要新增的是一个只读的 run-level manifest 投影，而不是另造一套执行配置。manifest 至少要能指向：

- source revision 和 dirty 状态；
- user、run、task/case identity；
- route、skill、owner 和工具 registry 版本；
- model/provider identity；
- root、child、synthesis phase budget profile；
- AnswerSpec/DecisionBrief/claim registry schema；
- acceptance suite、overlay 和 fixture hash。

### 3.3 已有的验收层

当前验收已经分层：

1. `synthesis_health` 判断 full pass、released unverified、template fallback、not synthesized、unknown 等合成健康态；
2. acceptance verdict 判断逐题的确定性事实、可复现性、短语等价和声明绑定；
3. answer rubric 和 semantic verifier 判断表达、证据忠实度、数字和条件；
4. 独立 evaluator 只在输入满足公平比较条件时运行。

这些门禁不被新的改进循环替换。新的 Eval 必须选择已有 evaluator 的合适层级。

### 3.4 已有的学习层

用户侧已有：

- `corrections.jsonl`：用户明确纠偏；
- `experience_cards.jsonl`：低分回答对应的行为规则；
- forecast reflection/lesson/rule：事前预测失败后的复盘和审批；
- checkpoints/verdicts：可证伪判断的到期回检。

这些记录用于学习用户方法和回答行为，不能自动被解释成产品事实，也不能自动替换 acceptance 正典。

### 3.5 当前缺口

缺口集中在中间连接层：

```text
raw trace / user feedback / triage report
  -> 可审核的 Finding
  -> 可观察的 Eval candidate
  -> approved regression case
  -> implementation change
  -> verification outcome
```

目前同一问题可能同时出现在 run artifact、handoff、correction、经验卡和测试里，但缺少稳定 ID 证明它们是同一条修复链。

## 4. 目标与非目标

### 4.1 目标

1. 为每个已确认的 agent run 问题建立稳定的 `finding_id`。
2. 记录第一次有证据的错误 step/span，而不是只记录最终失败。
3. 将 Finding 转换成候选 Eval，保留原始证据、失败标准和修复预测。
4. 通过人工审批后，才把候选 Eval 加入长期回归集。
5. 将 Eval、Codex 修改和后续验证 run 串成一条 lineage。
6. 区分确定性结构门禁、确定性事实门禁、语义 judge 和人工判断。
7. 对修复预测记录 `confirmed`、`refuted` 或 `inconclusive`，支持未来架构升格判断。

### 4.2 非目标

- 不引入 HALO 作为生产 runtime 或自动合并器。
- 不使用 LLM judge 判断“某 JSON 字段是否存在”这类确定性问题。
- 不让 LLM 自动修改 acceptance 正典、sealed fixture 或生产配置。
- 不把旧答案回放结果称为候选 revision 的通过结果。
- 不从缺失 trace 或缺失 source 推断根因。
- 不把 corrections、experience cards 或 generated eval 当作事实知识库。
- 不在本设计中改变现有预算、路由、证据层和公开回答契约。

## 5. 设计原则与原因

### 原则 1：原始 trace 不可变，诊断结果另存

原因：同一份 trace 可能被多个 harness 分诊。若把模型解释写回原 trace，就无法区分运行时观察和事后推断，也无法重现当时的证据边界。

### 原则 2：先冻结 failure criterion，再做归因

原因：只有“回答不好”不能直接成为 Eval。必须先把它改写成可观察标准，例如“`synthesize` 前没有 prepared messages”“A8 的 date 不在 query 中”“正文出现未绑定数字”。

### 原则 3：确定性在前，语义在后

原因：阶段是否跑完、是否有 evidence binding、是否出现 template fallback，是结构事实；不能交给随机的 LLM judge。只有“是否真正回答了双红问题”这类语义问题才进入语义层。

### 原则 4：LLM 只能生成候选，不拥有晋升权

原因：Cookbook 将 LLM feedback、LLM eval generation、LLM rubric 和 HALO 串在同一链上，适合演示但存在同族模型自我确认。金融回归集必须由人确认题意、证据和边界。

### 原则 5：修复必须有可证伪预测

原因：没有预测就无法判断修复真的生效，容易出现“改了 prompt，下一次看起来不一样”这种伪闭环。

### 原则 6：用户学习和工程回归分账

原因：用户偏好的表达规则可以进入 experience card，但不能因为用户喜欢某种说法就改变事实 gate 或 acceptance truth。

## 6. 总体架构

```text
                ┌─────────────────────┐
                │  Immutable Run       │
                │  run.json/trace.jsonl│
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │ Deterministic Gates │
                │ health/fact/contract │
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │ Trace-first Triage   │
                │ Finding + evidence   │
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │ Improvement Ledger   │
                │ finding/fix/prediction│
                └───────┬───────┬──────┘
                        │       │
             ┌──────────▼─┐ ┌──▼───────────┐
             │ Eval candid.│ │ Codex handoff│
             │ LLM may help│ │ human review │
             └──────┬──────┘ └──────┬───────┘
                    │               │
             ┌──────▼───────────────▼──────┐
             │ Approved regression / change │
             │ case + revision + prediction │
             └──────────────┬──────────────┘
                            │
                    ┌───────▼────────┐
                    │ Replay/Canary   │
                    │ verify outcome  │
                    └────────────────┘
```

### 6.1 Immutable Run Adapter

输入：已有 run 目录、trace、artifact、manifest、acceptance case 或 user feedback。

输出：统一的只读引用，不复制大正文：

- run identity；
- source revision、dirty 状态和 PIT/cutoff；
- ordered trace steps；
- gate diagnostics；
- artifact SHA256；
- source references 和 redacted excerpts。

设计原因：减少不同 harness 之间直接读字段造成的语义误读，特别是 `completed`、`elapsed_ms`、phase 缺失和 post-hoc stop reason。

### 6.2 Trace-first Triage Adapter

该层消费 agent-run-triage 的方法：

```text
Triage -> Static expected path -> Dynamic actual trace -> Synthesis
```

输出必须包含：

- failure criterion；
- 至少三条可证伪假设及其状态；
- first bad step/span；
- Evidence -> Finding -> Path；
- PRIMARY/SECONDARY；
- `fix_type`；
- `verification_prediction`；
- residual uncertainty。

设计原因：不能让最终答案的措辞直接倒推根因。没有足够中间 trace 时，输出 `INSUFFICIENT_TRACE`，而不是生成一个看似精确的 PRIMARY。

### 6.3 Improvement Ledger

这是新增的中心连接层。它不替代原始 run、acceptance 或用户学习文件，而是保存工程改进对象之间的引用关系。

建议 canonical 路径：`intelligence/users/<user>/improvement/`，因为 run、用户反馈和具体问题都属于用户态；仓库只提交 schema、fixture 和脱敏 golden 样例。

建议文件：

```text
improvement/
  findings.jsonl
  eval_candidates.jsonl
  approvals.jsonl
  verifications.jsonl
  index.json
```

### 6.4 Eval Candidate Builder

输入可以包括：

- triage Finding；
- 用户 correction；
- experience card；
- forecast reflection；
- acceptance failure；
- semantic judge observation。

LLM 可以帮助生成：

- 候选 case 标题；
- 期望行为；
- pass/fail 示例；
- 可选的语义 rubric；
- 确定性 assertion 草稿。

但 builder 必须同时生成证据引用、failure criterion 和 `assertion_kind`。没有可观察依据的候选不得提交审核。

### 6.5 Approval Gate

审批人至少确认：

1. 失败标准是否真的对应用户抱怨；
2. 断言能否由 trace 或产物判断；
3. 是否属于产品问题、题目不可复现、环境问题或裁判问题；
4. 是否应该进入已有 case 的 additive overlay，而不是新增正典题；
5. 是否会引入时间泄漏、数据依赖或过拟合。

审批结果只能是 `approved`、`rejected`、`needs_evidence` 或 `superseded`。

### 6.6 Verification Closure

修复后验证必须引用：

- 原始 finding；
- approved eval/case；
- 代码 revision；
- 运行 artifact；
- gate 结果；
- prediction outcome。

修复未验证前不能把 Finding 标为 resolved；只有结果满足预注册的 verification prediction 才能标为 `confirmed`。

## 7. 数据契约

### 7.1 Finding

```json
{
  "finding_id": "finding-<stable-id>",
  "run_id": "run-...",
  "case_id": "A2",
  "failure_criterion": {
    "kind": "observable",
    "statement": "research route has evidence but no prepared synthesis messages",
    "source_refs": ["trace.jsonl#step-...", "report.json#/diagnostic"]
  },
  "first_bad_step": {
    "step_id": "...",
    "normalized_step": "synthesize",
    "source_ref": "trace.jsonl#..."
  },
  "evidence": [
    {"evidence_id": "E1", "source_ref": "...", "excerpt": "..."}
  ],
  "finding_type": "implementation_defect",
  "primary": true,
  "fix_type": "CONTROL_FLOW_FIX",
  "verification_prediction": "same route produces prepared_message_count > 0 and no fallback",
  "status": "triaged",
  "created_at": "..."
}
```

### 7.2 Eval Candidate

```json
{
  "eval_candidate_id": "eval-candidate-<stable-id>",
  "finding_id": "finding-...",
  "source_run_ids": ["run-..."],
  "assertion_kind": "deterministic",
  "expected_behavior": "...",
  "deterministic_assertions": [
    {"path": "diagnostic.reason_code", "op": "equals", "value": "..."}
  ],
  "semantic_rubric": null,
  "negative_example": "...",
  "evidence_refs": ["E1"],
  "suite_target": "existing_case_overlay",
  "status": "needs_review"
}
```

`assertion_kind` 取值建议为 `deterministic`、`semantic`、`hybrid`、`not_evaluable`。`not_evaluable` 不是失败，而是记录题目或证据不具备可判定条件。

### 7.3 Verification

```json
{
  "verification_id": "verification-<stable-id>",
  "finding_id": "finding-...",
  "eval_id": "...",
  "change_revision": "...",
  "verification_run_id": "...",
  "result": "pass",
  "prediction_outcome": "confirmed",
  "gate_receipts": ["..."],
  "residual_uncertainty": []
}
```

## 8. 状态机

```text
observed
  -> gate_classified
  -> triaged
  -> eval_candidate
  -> needs_review
  -> approved / rejected / needs_evidence
  -> implemented
  -> verification_pending
  -> confirmed / refuted / inconclusive
```

规则：

- `unknown`、`not_evaluable` 和 `needs_evidence` 不得自动变成 `failed`；
- 没有 first bad step 的 Finding 不能标 `confirmed`；
- 没有 approved eval 的修复可以验证，但不能宣称形成长期回归保护；
- 同一 failure criterion 的新证据应更新旧 Finding 或建立显式 supersession，不能静默复制；
- 同类 `fix_type` 连续三次 prediction refuted 时，自动建议把问题从 prompt 层升格到 harness/架构层。

## 9. 门禁分层

### 第一层：确定性结构门禁

检查：

- 是否启动过正确 phase；
- 是否有完整 synthesis artifact；
- 是否出现 template fallback；
- prepared message、claim binding、source trace 是否存在；
- elapsed/budget 是否按正确 semantic epoch 解读；
- query 是否包含必要日期锚；
- artifact 是否有合法 schema。

这层使用现有 `synthesis_health`、acceptance verdict 和本地纯函数检查。

### 第二层：确定性事实和证据门禁

检查：

- claim 是否绑定合法 evidence；
- 数值、日期、单位、方向是否一致；
- source 是否满足 cutoff；
- 证据层和公司/产业链关系是否混淆；
- 是否把缺数据写成事实。

### 第三层：语义门禁

只用于：

- 是否回答了本题；
- 是否把双红、反方和升级/降级条件讲清；
- 是否存在明显模板化或答非所问。

语义 judge 必须记录模型、rubric、输入 artifact hash 和独立性；judge 失败不能覆盖前两层的真实结果。

### 第四层：人工审核

用于：

- 通过/失败标准是否合理；
- 新 eval 是否过拟合某次答案；
- 是否应该加入正典、overlay 还是只保留诊断；
- 是否允许进入用户学习层。

## 10. 分阶段落地

### Phase 0：只读接线和样例

目标：不改变任何生产行为。

- 定义 `Finding`、`EvalCandidate`、`Verification` schema；
- 从一份已有 acceptance run 和一份 grounded run 生成脱敏 golden sidecar；
- 固定 `run_id -> finding_id -> eval_candidate_id` 关系；
- 写 schema 校验和 hash 校验。

完成标准：可以用离线 artifact 生成完整 lineage，不调用 provider。

### Phase 1：分诊结果入账

目标：把 agent-run-triage 的报告引用进账本。

- 读取现有 trace profile；
- 只接受带 failure criterion、evidence、first bad step 和 fix_type 的 Finding；
- 缺 trace 输出 `INSUFFICIENT_TRACE`；
- 不自动生成 Eval。

完成标准：至少覆盖一个 `not_prepared`、一个 synthesis fallback 和一个题目不可复现样例。

### Phase 2：候选 Eval 生成

目标：减少手写断言成本。

- LLM 根据 Finding 生成候选 Eval；
- 纯函数检查字段、证据引用和断言语法；
- 确定性候选优先；
- 语义 rubric 标记为需要人工审核；
- 不修改 `acceptance_cases.json`。

完成标准：候选 Eval 能够被人审核，且能明确说明它来自哪条 Finding。

### Phase 3：审核与冻结

目标：形成长期回归资产。

- 审核通过的候选写入 additive overlay 或专门 regression suite；
- 记录 suite hash、case revision 和审批人；
- 失败或不可复现候选保留原因，不删除。

完成标准：一次代码修改可以由 approved Eval 复现旧问题并验证修复。

### Phase 4：验证闭环和看板

目标：看见哪些修复真正有效。

- 每次验证回填 `prediction_outcome`；
- 按 fix_type 聚合 confirmed/refuted/inconclusive；
- 连续 refuted 时提示架构升格；
- 在 Workbench learning feedback 页面展示 pending Finding、Eval 和 Verification。

完成标准：可以回答“这个修复解决了哪次 run 的什么问题，后来是否再次出现”。

## 11. 方案取舍

### 方案 A：只做文档和人工 handoff

优点是风险最低、无需新 schema；缺点是经验仍依赖人记忆，不能稳定回归。

### 方案 B：审核式 Improvement Ledger（推荐）

LLM 只生成候选，确定性检查和人工审批决定是否晋升；原始 trace、现有 acceptance 和用户学习层保持不变。

推荐原因：它吸收了 Cookbook 最有价值的“反馈资产化”，同时保留金融 Agent 必须具备的证据纪律和 fail-closed 边界。

### 方案 C：HALO/LLM 自动生成并自动修改

自动化程度最高，但会把 trace 误读、rubric 漂移和 provider 方差连续放大。除非后续有稳定的 candidate sandbox、独立 evaluator 和强制 PR 审核，否则不进入生产。

## 12. 测试与验收

### 单元测试

- Finding schema 缺 evidence、缺 first bad step、缺 failure criterion 时拒绝；
- Eval candidate 的 source ref 不存在时拒绝；
- deterministic assertion 不得偷偷降级成 semantic；
- `not_evaluable` 不得计入失败分母；
- 同一 finding/eval/verification 重放不产生重复记录；
- 原始 run hash 改变时 verification 失效。

### 集成测试

- 从真实冻结 run 生成 Finding；
- 从 Finding 生成候选 Eval；
- 审批后加入 overlay；
- 对修复前后 artifact 运行同一 evaluator；
- 回填 confirmed/refuted；
- 验证 gate 失败、judge 超时、缺 trace、provider unavailable 时不会伪造通过。

### 发布验收

发布前至少要能展示：

```text
一个 Finding
一个 approved Eval
一个实现 revision
一个 verification run
一个 prediction outcome
```

且所有对象都能从 `finding_id` 反查到原始 evidence。

## 13. 隐私、安全和数据边界

- 原始用户问题、答案、股票池和个人偏好继续留在用户态目录，不入 git；
- Improvement Ledger 只保存引用、hash 和最短脱敏摘录；
- LLM 生成候选前必须使用已有 redact 规则；
- 不把 API key、绝对路径、完整工具 stdout 或 prompt 写入候选 Eval；
- 任何“可分享”的 handoff 必须经过现有 trace redaction；
- 事实知识库、用户经验卡、工程 Finding、回归 Eval 分开存储和授权。

## 14. 成功标准

第一期不以“模型回答分数提高多少”为唯一标准，而以可追溯性为主：

1. 80% 以上已确认的 agent run 问题能关联到明确 `finding_id`；
2. 每条已批准 Eval 都能回溯到至少一条原始 evidence；
3. 每次代码修复都能关联到 verification run；
4. `unknown`、`not_evaluable`、judge outage 和产品失败保持分账；
5. 连续 refuted 的 fix_type 能被识别并触发架构升格提示；
6. 不修改现有 acceptance 正典 hash，不改变现有默认运行行为。

## 15. 待用户确认的决策

1. Improvement Ledger 是否放在 `intelligence/users/<user>/improvement/`，还是放在独立的评测目录？
2. 第一批是否只接入 `synthesis/acceptance` 失败，暂不接入预测 reflection？
3. 候选 Eval 审批是否先采用 CLI/JSON 审核，还是直接接入 Workbench learning feedback 页面？
4. 已有 acceptance overlay 是否作为第一期 approved Eval 的唯一晋升目标？
5. 第一阶段是否禁止所有 semantic candidate 进入 gate，只允许 deterministic candidate？

## 16. 参考文件

- Cookbook notebook：[`agent_improvement_loop.ipynb`](https://github.com/openai/openai-cookbook/blob/05fe56240be4a27b1f6b3f424cb2e3c9bcf9980e/examples/agents_sdk/agent_improvement_loop.ipynb)
- [run_store.py](../../../intelligence/services/run_store.py)
- [trace-profile.md](../../trace-profile.md)
- [synthesis_health.py](../../../intelligence/eval/synthesis_health.py)
- [normalize_harness_trace.py](../../../intelligence/eval/normalize_harness_trace.py)
- [acceptance_verdict.py](../../../intelligence/eval/acceptance_verdict.py)
- [forecast_learning.py](../../../intelligence/services/forecast_learning.py)
- [users README](../../../intelligence/users/README.md)
- [2026-08-03 shared-layer audit handoff](../../handoffs/2026-08-03-shared-layer-audit-handoff.md)
