# 判官身份与校准有效性 Implementation Plan

> **For agentic workers:** 使用 `subagent-driven-development` 按任务执行；共享调用台账与评分入口依序修改，互不改同一文件。复审通过后再推进下一任务。

**Goal:** 主评、补评和完整重评都只能使用同一有效评审批次的评分与校准出实验结论；未知身份或不兼容记录保留，但不能产生 `callable`。

**Architecture:** 复用 `llm_refine.LLMCallLedger` 记录实际调用证据，服务层只采集，纯评测模块验证身份与批次。`aggregate_components` 是唯一实验决定入口，命令行预检只负责提前阻止已知无效调用；评分与噪声底的生成共用同一身份合同。

**Tech Stack:** Python 标准库（dataclasses、contextvars、hashlib、json、math）与现有 pytest。正文中的新字段、函数和测试名是待实现合同，不表示代码已具备。

**状态：Task 1–5 已实施并验收，未合 main。** 日期 2026-09-14；依据 `gitea/main@1fef3d276d0e251158803fc09d5a81e60d79241b`，实施在 `codex/judge-calibration-validity`（代码 `7117125e`、文档 `87845e09`），工作树 `/Users/a77/fwp-wt-judge-calibration-validity`。

**2026-09-16 追平主干**：两次合并 `ffb0d281`（并 `main@c29a6401`，解两处 token 计费 × 调用身份冲突）、`26f18e99`（并 `main@d433b907`），并落实移交的 `identity_state` 跨层一致性 P1（`intelligence/call_identity.py` + `intelligence/tests/test_call_identity_contract.py`）。四叶对 `26f18e99` 重跑全绿：pytest **11359 passed / 0 failed**、vitest **107 passed**、e2e **34 passed / 2 skipped**、registry 五项 exit 0（收据 `20260916T152203Z-26f18e99.json`）。详见 `docs/handoffs/2026-09-16-judge-calibration-main-integration.md`。

全量 9766 passed / 0 failed 与 `ruff check .` 绑定 `7117125e`（收据 `~/.finance-runtime/test-receipts/20260914T152057Z-7117125e.json`，`check_test_receipt.py --expect-revision` 七项全过、干净树）。§5 的反向证明已跑：拆掉身份门 / 源 writer 独立性 / 校准绑定哈希 / 非有限数检查，V1/V4/V6/V8 分别见红，还原后 85 项全绿。**未调真实判官**——全部验收走假传输与内存夹具，「门会拦」已证、「真实模型分差如何」未测。frontend / e2e 两片叶子已在 `26f18e99` 补跑全绿（见上方追平段），合入仍待用户确认。交接见 `docs/handoffs/inflight/codex-judge-calibration-validity.md`。

## 1. 已核实的故障与范围

- `scripts/rejudge_quality_ablation.py::rejudge_artifact` 直接沿用源 `noise_floor`；`aggregate_components` 只检查 rubric 版本混用，未绑定实际判官。
- 离线最小反例：同题 baseline 原判官标签 Grok、20 分，关断臂由 GPT 补评、5 分；同 rubric，旧底 `measured=True, sigma=2, sd_delta_single_question=0.1`，仍得到 `callable`、边际贡献 15。该夹具证明聚合缺门，不证明真实模型有这份分差。
- `judge_answer` 走 `llm_refine.complete -> _post_chat / _complete_cli_judge`；`provider_label` 读取 `LLMProvider` 请求配置。`openai_agents_runtime.py::ServedModelLog` 只覆盖 SDK 研究臂，不是本次判官采集入口。
- `resolve_judge` 从当前环境读 composer；事后补评需要核对源答案的写作者，不能用今天的配置代替历史证据。
- `run_ask` 调用 `intelligence.cli ask --compose`，属于 legacy 问答路径。本计划的实验结论仅覆盖该入口，不宣称验证 Workbench Episode。

本轮不改生产问答判官的准入策略、不改时间长河写入、不改 `graph_audit.py`；共享台账只加可选证据字段。无身份旧收据可读，但不自动补造身份或追认有效。数据与模型调用在未来执行时仍遵循现有预算，不为身份校验追加隐式探活请求。

## 2. 文件与职责

| 文件 | 动作与唯一职责 |
|---|---|
| `intelligence/services/llm_refine.py` | 扩展 `LLMCallRecord / LLMCallLedger.summary`；在真实传输边界采集请求与响应身份。保持 `complete` 三元组返回合同 |
| `intelligence/services/grok_cli_judge.py` | 保留 CLI 子进程的结构化响应元数据；无模型字段明确记未知，不从自然语言自述或配置补齐 |
| `intelligence/cli.py::add_ask_parser / cmd_ask` | 新增可选 `--call-provenance-json`，将该次 ask 的调用台账与最终输出哈希写为独立机器收据；普通 stdout 不变 |
| `intelligence/eval/judge_validity.py`（新） | 无 IO 的版本解析、规格哈希、身份与校准绑定校验，返回资格及原因码；不从 services 反向导入 |
| `scripts/run_quality_ablation.py` | 生成冻结批次、收集 writer 证据、逐次评分与校准；共同聚合入口强制消费资格结果 |
| `scripts/rejudge_quality_ablation.py` | `pending` 补评与 `new-batch` 完整重评分路；保留源答案、分数和失败历史 |
| `intelligence/tests/test_judge_validity.py`（新） | 纯合同与数值、身份、批次反例 |
| `intelligence/tests/test_llm_call_provenance.py`（新） | HTTP/CLI 重试、回退、并发、输出绑定测试；用假传输与子进程，无真实模型调用 |
| `intelligence/tests/test_quality_ablation_noise_floor.py` | 旧噪声底测试改为带身份条件的验收；保留数学与零方差正例 |
| `intelligence/tests/test_quality_ablation_judge_independence.py` | 历史 writer、未知家族、同族、配置与响应不一致反例 |
| `intelligence/tests/test_rejudge_quality_ablation.py` | 命令行预检、两种模式、失败持久化、原收据不变、恢复资格 |
| `docs/agent-product-door.md` | 增加该评测的 legacy 入口限定与本计划指针，不新增产品正门 |

## 3. 冻结的合同

### 3.1 逐次调用证据

扩展现有调用记录，而不另建平行计费台账。所有字段在调用作用域内绑定；`attempt_id` 在实际派发前生成，不能用全局「最近模型」或仅靠列表位置关联。

`llm_refine.py` 新增 `call_provenance_scope(call_id, phase)`，yield 一个 `LLMCallContext`，含 `call_id / phase / selected_attempt_id`；由 `ContextVar` 承载。每次实际派发生成 attempt，`complete` 确认返回哪次成功正文时在该 context 记录 `selected_attempt_id`；失败时为空，函数三元组返回保持不变。`LLMCallLedger.records_for_call(call_id)` 返回该调用记录快照。主评、pending 与 new-batch runner 都必须开启或复用 `call_ledger_scope`，逐次 `judge_answer` 在独立 `call_provenance_scope` 内执行；成功 verdict 的 attempt 必须存在于当前 ledger 且正文哈希匹配。没有活动台账时不得把空证据视为成功采集。该上下文属于一次逻辑调用，并发调用使用不同实例，不从台账的末行猜测返回者。

| 字段 | 合同 |
|---|---|
| `call_id / attempt_id` | 一次逻辑调用 / 一次实际 provider 尝试的不同身份；重试与回退产生新 attempt |
| `phase` | `writer / judge / calibration`；校准角色只影响本地记录，不进入模型提示词 |
| `requested_model` | 真正发出的请求字段，不从之后变化的环境取值 |
| `reported_model` | 本次成功响应结构化字段，缺失为 null；CLI 无结构化模型字段也为 null |
| `identity_state` | `not_called / unreported / reported`；与 `status=success/failed` 正交。HTTP 错误页里的模型名不能证明评分身份 |
| `endpoint_id / transport` | 预先声明的非敏感端点标识与 HTTP/CLI 类型；不写 key、Authorization、原始配置或含凭据 URL |
| `request_id / response_id` | 对端确实返回时保留，用于关联；不是模型真实身份的认证 |
| `request_sha256 / result_sha256` | 实际发出的非敏感评分消息与返回正文的哈希；成功评分须能绑定到确切 attempt |

复用 `_served_model_from_body` 的「缺失不补配置」规则。HTTP 的 `_post_chat`、`_post_chat_synthesis`、工具调用以及流式最终结算点均需覆盖 writer 可能经过的路径；流式不同分块报告不同模型时记冲突，不能取第一个掩盖后续变化。CLI 元数据解析失败保留未知，正文仍按原合同返回。

预算仍在副作用前预占，台账扩展不改变计数。预算拒发用 `not_called` 记入逻辑调用结果，不伪造一次已花费的 attempt。嵌套作用域、线程与 async 任务沿用 `ContextVar` 传播模式，不能重置外层预算或把并发两题的身份混到一起。

响应自报身份只支持“按对端声明相同/不同”的审计强度；不称为已认证真实模型，也不保证跨家族偏差统计独立。家族解析采取明确支持表，识别不了为 unknown，不能用两个陌生字符串不相等就判异构。

### 3.2 源答案与评审批次

新收据增加 `schema_version=2`，保留原 `kind` 与旧展示字段；规范 JSON 哈希使用 UTF-8、键排序、固定 separators、`allow_nan=False`，不含生成时间和秘密配置。字段缺失不使用当前配置回填。

- `answer_id` 绑定源 run、`case_id`、arm 和完整 `answer_sha256`；`judge_input_sha256` 另绑定问题、日期及实际截断后的正文。存储、评分与校准分别验证，防止“原答案没变但实际送评文本换了”。
- `writer_provenance` 绑定源 ask 的台账、输出哈希和成功且可能影响答案的调用身份集合。`run_ask` 为每个 `(case_id, arm, attempt)` 传唯一收据路径；读回哈希必须等于同一子进程输出。保留原始输出哈希和既有 `.strip()` 后答案哈希，不让空白规范化造成错绑。CLI 收据另记 `delivery_state=delivered/clarification/no_answer`，依据真实工作流结果；`run_ask` 去掉仅因正文少于 200 字而排除送评的判据，短答、拒答与扣稿话术按原文评。启动异常文本不能仅凭长度冒充交付。
- 在只能收集全部 ask 模型调用时，保守使用全部成功调用的家族集合，并声明该范围；它可能降低判官可用性，不能冒充精确的最终写作者集合。无法归属的成功调用或缺失收据导致独立性 unknown；失败且未贡献内容的尝试只进历史，不冒充 writer。
- `judge_spec` 包含请求模型、允许的响应模型、显式家族映射版本、端点标识、传输类型、rubric 标签及实际正文、temperature、有效 thinking/推理设置、token 上限、截断上限与算法版本、重试提示及选择规则。`judge_spec_sha256` 从这些有效值派生。别名兼容映射必须事前冻结，缺失或冲突不可运行时猜测。
- `batch_id` 在首次付费调用前分配。先冻结 `run_manifest`：源文件哈希、全部题目与臂、judge spec、校准选样规则与次数、重试预算、截止时间、分母及排除规则。答案生成后、首次评分前再封存 `answer_manifest`，绑定全部答案哈希与按预声明规则得到的校准文本；后者引用前者哈希，不改写事前计划。配置哈希相同不是跨批次复用校准的许可。
- `calibration` 每次重复保留完整 verdict 和成功 attempt 引用，不再仅存 totals；底值绑定 `batch_id / judge_spec_sha256 / calibration_sha256`，总分必须能从这些原始 verdict 重算。
- 批次生命周期为 `open -> sealed`，发现身份冲突后为 `invalid` 且不在原批次复活。`expires_at` 在开始前按显式 `--batch-max-seconds`（默认 3600 秒）冻结；这是工程会话边界，不是模型一小时稳定的统计证明。seal、进程退出/中断或过期后不得新增评分并沿用旧底，后续恢复走新批次。

期限约束的是**采集和追加**：已在期限内完成并封存的收据，日后读取仍按其调用时间与封存证据判断，不与当前墙钟相比而自动过期。纯验证中 `now` 仅用于 open 批次准入；sealed 收据检查全部尝试和校准是否在原冻结时间窗内完成。`manifest` 下文统指已绑定的 `run_manifest + answer_manifest`。

### 3.3 唯一资格门

新增纯函数 `validate_judging_batch(answers, calibration, manifest, *, now)`，返回 `{valid, reason_codes, invalid_answer_ids}`。`aggregate_components` 每次调用都先验证原始记录与 manifest，不能只相信传入的 `valid=True` 或旧 `decision`。

验证按以下顺序执行，任何一项失败，相关整个批次的组件决定为 `no_call`，仍保留描述性分差和覆盖率：

1. schema、题臂唯一性与完整性、源答案及送评哈希、manifest 封存校验通过。未知版本拒绝出结论；旧 v1 仅展示。删行、改 arm、重复 case 或替换答案不能取得更好资格。
2. 每条成功评分与校准评分都能定位唯一成功 attempt，身份不是 unknown；响应在事前允许集合内，与该批次其他成功评分兼容。失败重试也保留，任何已返回成功内容的未知/冲突身份不能因 JSON 解析失败被丢掉后继续称批次兼容。
3. 判官家族与源 writer 的全部已知贡献家族不同；未识别或未知为 `writer_identity_unknown`。`--judge-independence allow-correlated` 只允许生成探索收据，绝不恢复 `callable`。
4. 校准来自同一批次、同一有效规格和相同文本。校准计划事前冻结，至少两份不同基线文本、每份至少两次评分；每份原始首次评分是否参与须写入计划，默认参与。计划中任何重复最终缺失则 `calibration_incomplete`，不看分数后挑剩余成功样本重新凑底。
5. 噪声参数从原始分数重算并核对：`sigma > 0`、标准差非负、所有数有限，缺字段/NaN/Infinity/负值均无效。完整同文本重复恰好同分的真实零方差允许；不能把缺失标准差用 `or 0.0` 变成零噪声。
6. 所有预登记题臂都有有效评分，才允许该批次质量分差进入判定；外部判官最终失败保留为未评分并阻断该批次质量结论。产品失败仍留在端到端分母，不能通过身份门重归因为实验条件失效。无正文时不伪造评分，该批次质量分差为 `no_call`，同时保留交付/失败率；有正文的拒答或内部扣稿按原文送评。成功子集的分差可以描述性展示，但不能冒充整个实验有效。

`decision=callable` 仅表示越过当次判官噪声门，不自动授权合并，也不证明跨任务或未来效果。`baseline_absolute` 只作该批次描述性统计，带资格与样本数；CLI 和 JSON 必须同时输出原因码、总样本/已交付/已评分/失败尝试数，旧消费者读到 `decision` 也须是保守值。

### 3.4 补评与完整重评

新增 `--mode pending|new-batch`，默认 `pending`，两种模式都不重跑 ask、不覆盖输入文件、不改源答案或既有分数。

| 情况 | 行为 |
|---|---|
| 同一活跃进程内，open 且未过期批次的临时评分失败 | 可按预登记预算补 pending；之后完成该批次校准，再封存 |
| CLI 读到已封存/进程已结束的源收据，只要求补 pending | 可以另存诊断补评分，但标 `calibration_stale`、旧底仅作证据；所有实验决定 `no_call`，不冒充续同一批次 |
| `new-batch`，所有源 writer 与源内容可核实 | 全部相关题目的 baseline 与关断臂重新盲评，重新校准；新 `batch_id`，保留 `source_run_sha256 / parent_batch_id`，原分数只在源收据中有效 |
| 源 writer 不可核实、别名未知、配置同族且默认 require | 调用前报告 `writer_identity_unknown / judge_not_independent`，零付费；旧答案可探索重评但只能 `no_call` |
| 调用后才发现响应换模型/无身份 | 写出已产生的评分、attempt 与 invalid 原因，停止新增结论性调用；不能退出到只剩异常堆栈、丢失已花费的证据 |

`new-batch` 不是在原 `rejudge_artifact` 中覆盖 scored 项；它另构新收据。现有“已评分绝不重评”继续约束 `pending`，完整重评明确声明对冻结文本产生新的评审版本。新底不能与源批次旧分混用；如果历史 writer 永远不可考，单靠重评无法恢复独立性资格。

文件校验、输出路径冲突与必填参数在任何模型调用前完成。每次已结算 attempt/评分后原子更新独立的新批次工作收据，结束时封存；中断保留 incomplete/invalid，不生成可用结论。读回只接受已写完整且哈希一致的记录，新增元数据不能改变旧 stdout 答案。沿用现有本地文件产物，不另开自动同步台账。

## 4. 执行任务

以下复用主树解释器。进入实施工作树后运行：

```bash
PYTHON=/Users/a77/finance-workspace-private/.venv-workbench/bin/python
```

### Task 1: 先复现现有缺口，再建立纯合同

- [x] 把下列最小反例固定到 `test_rejudge_quality_ablation.py`，先断言修复目标 `no_call`，在现有代码应红；记录基线 revision。只用内存数据，不调模型。

```python
from pathlib import Path
from scripts.rejudge_quality_ablation import rejudge_artifact
from scripts.run_quality_ablation import RUBRIC_DIMENSIONS, RUBRIC_VERSION

def test_changed_judge_cannot_reuse_old_calibration():
    def verdict(score, provider):
        return {"scored": True, "scores": dict.fromkeys(RUBRIC_DIMENSIONS, score),
                "total": score * len(RUBRIC_DIMENSIONS),
                "rubric_version": RUBRIC_VERSION, "provider": provider}
    source = {
        "kind": "quality_ablation",
        "questions": [{"case_id": "q1", "text": "fixture", "as_of": "2026-09-01"}],
        "answers": [
            {"case_id": "q1", "arm": "baseline", "ok": True, "answer": "original A",
             "judge": verdict(4, "judge/grok-test")},
            {"case_id": "q1", "arm": "kb-rag", "ok": True, "answer": "original B",
             "judge": {"scored": False}},
        ],
        "aggregates": {"kb-rag": {}},
        "noise_floor": {"measured": True, "sigma": 2, "sd_delta_single_question": 0.1},
    }
    out = rejudge_artifact(source, judge_fn=lambda q, a: verdict(1, "judge/gpt-test"),
                           seed=1, source_path=Path("fixture.json"), source_sha256="fixture")
    assert out["aggregates"]["kb-rag"]["decision"] == "no_call"
```

- [x] 在 `test_judge_validity.py` 建立完整 v2 正常夹具：两题、每题两臂、冻结 writer 家族、同一 judge、每题两次校准，原始 verdict 与 manifest 都能重算哈希；正常夹具可取得有效资格。
- [x] 实现 `judge_validity.py` 的规格/manifest 规范哈希、显式版本解析和纯资格函数；使用 §5 的 V1-V8 变体测试，不依赖生产库或环境模型设置。
- [x] 运行 `$PYTHON -m pytest -q intelligence/tests/test_judge_validity.py`；全部通过后检查没有 services 导入 eval 或 runtime。

### Task 2: 贯通真实调用证据与源 writer

- [x] 扩展 `LLMCallRecord` 可选字段和序列化，传输适配器返回值保持兼容；为请求绑定作用域中的 call/attempt 身份。单元测试假 HTTP、CLI 和流式响应先红，再接记录点。
- [x] 在 `cmd_ask` 中仅对 `--call-provenance-json` 建立或复用台账作用域，最终输出与身份一并写入该路径；嵌套已有台账不重置预算。提前短路、异常、零调用均明确记状态。
- [x] `run_ask` 每次新建唯一收据路径并验证原始/规范化输出哈希；不扫描 `exports_dir` 找“最新文件”。校准不能把旧 run 的 writer 收据换成当前配置。
- [x] 运行 `$PYTHON -m pytest -q intelligence/tests/test_llm_call_provenance.py intelligence/tests/test_grok_cli_judge.py intelligence/tests/test_llm_refine_tool_stream.py`；V9-V12 通过，CLI 普通输出保持原字节。

### Task 3: 主轮评分、校准与聚合共用一扇门

- [x] 主评与补评进程开启或复用 `call_ledger_scope`，逐次 `judge_answer` 使用 §3.1 的调用 context，返回完整 attempt 引用与有效规格哈希，校准重复走同一接口；失败保留原因与已收集身份。初次和 JSON 格式重试的提示都纳入预声明策略。
- [x] 主 runner 先冻结计划并落盘，再 ask、评分、校准、封存；每次结果结算保存工作收据，`judge_noise_floor` 从完整校准 verdict 计算。
- [x] `aggregate_components` 每次复验原始记录与 manifest；所有不兼容路径按 §3.3 降为 `no_call`。`threshold_for` 缺值不再当 0，返回的旧 `decision` 字段不能绕开新门。
- [x] 修改 `test_补评沿用源轮实测的方差底`：旧无身份夹具应 `no_call`；另加同一 open 批次的正例，完整零方差也可通过。保留原噪声公式测试，不删数学验收。
- [x] 运行 `$PYTHON -m pytest -q intelligence/tests/test_quality_ablation_noise_floor.py intelligence/tests/test_quality_ablation_judge_independence.py intelligence/tests/test_judge_validity.py`。

### Task 4: 两种重评模式与安全恢复

- [x] CLI 增加 §3.4 模式与期限参数，`--dry-run` 输出调用数上界、资格缺口和预计模式；路径冲突/未知 writer 在 require 模式下应零调用、零覆盖。
- [x] `pending` 保留原 scored 项和源答案；`new-batch` 新建全部评分，不拷旧分进新聚合。源文件哈希、原答案及既有分数前后逐条一致，输出目标已存在时拒绝覆盖。
- [x] 统一人读报告与 JSON 的有效性、覆盖率、失败尝试和原因码；读取旧收据展示历史数但不复活旧 `callable`。正文缩短、拒答、内部判官扣稿仍按产品状态统计。
- [x] 运行 `$PYTHON -m pytest -q intelligence/tests/test_rejudge_quality_ablation.py intelligence/tests/test_quality_ablation_noise_floor.py intelligence/tests/test_quality_ablation_judge_independence.py intelligence/tests/test_judge_validity.py intelligence/tests/test_llm_call_provenance.py`；V13-V17 全过。

### Task 5: 反向证明门会拦，再交接

- [x] 分别临时绕过身份门、源 writer 校验、校准哈希与非有限数检查，对应 V1/V4/V6/V8 必须见红；还原后全绿。变异只在隔离副本，不改他人树。
- [x] 在 `docs/agent-product-door.md` 登记 legacy 评测边界，更新能力图谱与在途交接：只有实现和检查完成后才改“已实现”。旧收据不批量重写，不用 live 重评美化历史结果。
- [x] 冻结候选 revision，运行 `$PYTHON -m ruff check .` 与 `$PYTHON -m pytest -q`；合入前按仓库要求补齐 frontend/e2e/registry 等价检查，并将每片结果绑定 revision。任何门红或无结论均不合；本计划不含合并授权。

## 5. 必须满足的验收矩阵

| ID | 对正常夹具只改什么 | 预期 |
|---|---|---|
| V1 | 配置没变，一次成功响应换模型 | `judge_identity_mismatch`，整批 `no_call`；attempt 保留 |
| V2 | CLI 或 HTTP 成功但没报结构化模型 | `judge_identity_unknown`；不能填 requested_model |
| V3 | 补评新判官，源旧底仍在 | 原底留作证据，`calibration_stale`，不混算成有效分差 |
| V4 | 当前环境 writer 是 A、源 writer 是判官同族 B | 根据源 B 拦截；当前 A 不起证明作用 |
| V5 | rubric 标签不变，正文/temperature/截断规则任改一项 | 规格不兼容，`no_call` |
| V6 | 校准 totals 看似合法，引用别的答案/批次或哈希不一致 | `calibration_binding_mismatch` |
| V7 | 旧 v1、缺身份或陌生模型家族；传 allow-correlated | 可读/可探索，决定仍 `no_call` |
| V8 | 底值缺失、NaN、Infinity、负数；另测真实零方差 | 前四类失效；完整且绑定一致的零方差不过度拦截 |
| V9 | HTTP A 失败后 B 成功、JSON 重试、流分块身份冲突 | 每个 attempt 不丢、不串；成功冲突不能被重试擦掉 |
| V10 | 两题并发返回顺序颠倒或嵌套调用作用域；真实 judge_answer 经 complete 到假传输 | 每条评分绑定自己请求，外层预算未重置；verdict 的 selected attempt 确实存在于已落盘工作收据 |
| V11 | 子进程收据指到另一题/旧文件，或输出哈希不同 | `writer_provenance_mismatch`，不按当前配置恢复 |
| V12 | 预检失败、预算拒发或输出路径冲突 | 零新增模型调用；not_called 不计费、不覆盖输入 |
| V13 | sealed/过期/中断批次拿去 pending 补评；另测日后只读 sealed 收据 | 新增评分仅诊断、旧底不授资格；期限内完成的 sealed 收据不会因读取日期变晚自动失效 |
| V14 | 源 writer 完整，new-batch 全臂重评并完整新校准 | 原文件/原答案/原分不变，新批次可正常取得资格 |
| V15 | 删除失败行、改 arm、重复 case，或校准挑成功重复 | manifest 不符或校准不完整；无 callable，分母与尝试仍可核 |
| V16 | 模型调用后中断或响应身份失效 | 新工作收据保存已结算证据，状态 incomplete/invalid；重启不沿用旧底 |
| V17 | 五题中四题产品未交付、剩余一题分差很高；另测短答/拒答 | 全部样本留在端到端分母，整批 `no_call`，成功子集只作条件统计；有正文短答与拒答仍送评 |

## 6. 本轮文档交付与未完成项

- [x] 复核真实 judge 调用链、源 writer 缺口及旧噪声底反例。
- [x] 明确两种重评模式、共同资格门、来源哈希、缺失与失效语义。
- [x] 给出文件职责、执行步骤和成功/失败验收。
- [x] Task 1-5 的代码实现、测试和运行收据已完成（见开头状态行）；本文件仍不充当测试通过证明——读数以收据与 `check_test_receipt.py` 为准。

方法依据：agent-memory 的 `kept-history-is-not-replayable-history.md` 与 `exclusion-must-name-its-denominator.md`。项目实现合同以本文件为准；知识笔记保留可迁移原则，不复制全部字段和任务。
