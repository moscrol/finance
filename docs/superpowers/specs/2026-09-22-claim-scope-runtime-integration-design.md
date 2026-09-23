# 2026-09-22 口径越界 lint 运行时接入点设计（#65 目标 3 · 设计稿）

| 项 | 值 |
|---|---|
| 状态 | **设计稿，未实施**。本文只定接缝、开关、映射与验收；本批不改运行时接入点，离线判据模块可独立修改（#65 红线） |
| 实施前置 | 用户对「接入运行时」单独授权 + 另立工单；每升一档再授权一次 |
| 判据版本 | #850 `fix/answer-claim-scope-0922`@`1cf35f516` + #854 `fix/claim-scope-hardening-0922`@`5f5ce2d11` |
| 行号基准 | `gitea/main@8e79893729da`（含 #863）+ #854 的预览树。行号会漂，定位以符号名为准；`ask.py` 相关行在 `f24a61a8a` 与 `8e798937` 上相同，`episode_semantic_verifier.py` 被 #863 改过（`verify` 由 1315 → 1467） |
| 证据等级 | 标 **[实测]** 的行在 `5f5ce2d11` 检出上读过代码或跑过命令；标 **[推断]** 的是设计判断 |

## 0. 一句话

把 `answer_claim_scope.review_answer_claims`（离线 CLI 判据）搬进两条作答引擎的输出门，按 **advisory → 修订轮 → 硬拦** 三档推进；每一档都要先过「冻结 run 重放的裁决与 CLI 逐字段一致」这道映射验收——映射错了不会报错，只会静默变绿，这正是 #854 刚修掉的那类失效。

## 1. 为什么要接、为什么现在只写不做

- 2026-09-21 K3 写手 + 无判官首跑两题暴露四类口径越界（库内日期冒充最近交易日 / 5 个板块说成全部归属 / 成交额推资金流向 / 材料已给亿元仍称缺单位）。#850 把它们做成不依赖模型的判据，#854 闭合三条 fail-open 并回测 1347 个历史 run。
- **[实测]** `answer_claim_scope` 现在没有任何生产路径 import：`rg -l answer_claim_scope intelligence scripts` 非测试命中只有 `scripts/check_answer_claims.py`（CLI）和 `intelligence/services/output_review.py`（docstring 里的管辖边界说明，不是 import）。所以线上答案今天一条都拦不住。
- `ASK_SEMANTIC_JUDGE=off` 是用户已定目标（#55/#830）。判官关掉后引擎 A 只剩确定性门，这套 lint 是关判官后为数不多的**内容**门之一——接入的动机在这里，不在引擎 B。
- 接入要改运行时（`ask.py` / `episode_semantic_verifier.py` / `continuous_turn_adapter.py`），属部署授权范围；#65 红线写死「运行时一行不改」，故本文只交付设计。

## 2. 接缝盘点

### 2.1 引擎 B：`ask.answer_query`（写死流程，quick_fact / external_market / dated_market_review）

**[实测]** `intelligence/services/ask.py`（`gitea/main@8e798937` 与 #854 同一份，#854 / #863 都没碰它）：

| 行 | 是什么 |
|---|---|
| 4783 | `result.review_gate = output_review.review_output(trade_date=…, audit=audit, counter_plan=…, gap_lines=…, follow_ups=…, conclusion_lines=…, final_answer=result.synthesis, stale_block_hints=result.stale_block_hints)` |
| 4794–4797 | 非 `advisory_only` 的 WARN 逐条进 `result.warnings`（`输出质检：{name}——{note}`） |
| 4799 → 3004 | `_revise_synthesis_on_warn`：`compose_revise_on_warn and stream_text_delta is None and warn_count > 0` 才把 warn_notes 回灌同一段对话改写一轮；修订失败 / 被 AnswerSpec 门禁拒绝 → 保留初稿并记原因 |
| 4643 | 先例：`result.stale_block_hints = output_review.extract_stale_block_hints(...)` 先从块层解出提示，再作为参数传进 `review_output`——**证据上下文先解再传**，就是本设计要照抄的形状 |

`OutputReviewGate.warn_count` 只数非 advisory 的 WARN；`summary_lines()` 把 advisory 项也列出来但不计入分子分母（`output_review.py:76–110`）。Workbench 侧 `intelligence/runtime/conversation_orchestrator.py:1489–1497` `_review_notes_from_gate` 同样只取非 advisory WARN 进 notes，公开答案不拼附录。**advisory 档在这两条路径上天然「只记录不改答案」，不需要新分支。**

两条 advisory 先例，推进方式相同：`_check_stale_mislabel`（docstring：「观察一段在场率后再议是否升格进修订轮」）与 KC-13 五元素 lint（`conclusion_five_element_lint.py`：「缺项进核验 warning，不阻断、不触发修订」）。

### 2.2 引擎 A：`agent_episode` continuous loop（生产默认；K3 首跑走的就是它）

**[实测]** 冻结 run `run_20260921_183642_325351/continuous-episode.json` 顶层含 `semantic_verifier / structural_verifier / publication_assessment / runtime_backend / repair_attempts`——这是引擎 A 的产物。**只接引擎 B，K3 首跑那种题依然拦不住。**

| 位置 | 是什么 |
|---|---|
| `episode_semantic_verifier.py:1467` `SemanticEpisodeVerifier.verify(*, frame, structurally_verified, deadline, retrieve_fn=None)` | 引擎 A 的语义门入口；`judge_mode = semantic_judge_mode()` 在此读取；返回 `SemanticEpisodeOutcome` |
| `SemanticEpisodeOutcome`（630 起） | `public_answer: str`（最终公开文本）、`status`、`judge_status`、`judge_mode`、`issues`、`sentence_verdicts`、`material_claim_checks`… `to_dict()` 被 adapter 写进 private artifact |
| `VerifiedEpisodeOutcome.outcome.evidence`（`episode_verifier.py:38`、`agent_research.py:158`） | `AgentEvidence` 元组，`source_date` 字段就是 CLI `evidence_dates` 的来源；`detail` 是 CLI 台账资金流正则扫的文本 |
| `verify()` 收尾（1504 `recheck_material_public_delivery(outcome)` 之后、`premise_calculation` 分支附近） | 推荐接缝：此处同时拿得到最终 `public_answer` 与证据元组；`premise_calculation.admit` 那段（status→partial + `TerminalFacts` 披露）就是硬拦档可照抄的公开形态先例 |
| `runtime/continuous_turn_adapter.py:1183`（终稿）与 `:1360`（partial 路径） | 两处都把 `structural.to_dict() / semantic.to_dict() / asdict(publication)` 写进 artifact——lint 结果落在 `semantic_verifier` 字典里即可被冻结 run 与 `check_answer_claims` 读到；**两条路径都要落，漏一条就是 partial 答案无收据** |
| `retrieve_fn` 注入口（`verify` 签名 1473） | 先例：adapter 按回合造依赖注入 verifier。**工具请求（`compared_scope_count` 的来源）只在 adapter 的 events/traces 里，verifier 拿不到**，要照 `retrieve_fn` 的形状把 `ClaimEvidenceContext`（或其构造函数）注进来 |

### 2.3 判据本身的层级 **[实测]**

`answer_claim_scope.py` 只 import `re / dataclasses / typing`，位于 `intelligence/services/`；两条引擎的接缝也都在 services（verifier）或 runtime（adapter，允许 import services）。`layer_audit.py` 不会因接入新增 services → runtime 依赖。

## 3. 三档与开关

### 3.1 开关

- 环境变量 **`ASK_CLAIM_SCOPE_REVIEW`**，闭集 `{off, advisory, revise, block}`，**默认 `off`**（接入合并后行为逐字节不变，翻开关才生效）。
- 读法照 `intelligence/services/judge_mode.py`：单函数 `claim_scope_mode()`，模块不 import services/runtime，两条引擎读同一个函数。**非法值 → `off`**，并在收据写 `claim_scope_mode_invalid: "<原始值>"`——不静默当 advisory，也不静默当 block。
- 收据字段 **`claim_scope_mode`** 原样落地：引擎 B 进 `OutputReviewGate.to_dict()`，引擎 A 进 `SemanticEpisodeOutcome.to_dict()`；`judge_mode` 怎么落它就怎么落。
- 回滚 = 翻回 `off`，不需要代码回退。

### 3.2 三档

| 档 | 值 | 引擎 B 行为 | 引擎 A 行为 | 升到本档需要 |
|---|---|---|---|---|
| 观察 | `advisory` | 每条命中一个 `ReviewCheck(name="口径越界·<label>", status=WARN, note="<原句摘录>——<理由>", advisory_only=True)`；不进 `result.warnings`、不触发修订轮、不改正文 | `semantic_verifier` 字典新增 `claim_scope: {mode, issues[], degraded[]}` 只记账；`status / judge_status / public_answer` 不变 | 接入授权 + 实施单（本文 §5 验收全过） |
| 修订轮 | `revise` | 同上但 `advisory_only=False` → 进 `warnings` 并触发 `_revise_synthesis_on_warn`（一轮定向改写，失败保留初稿；不加模型调用次数上限之外的请求） | 命中句作为 issue 交给既有**删句式**有界修复（判官关时的确定性修复路径）；不新增模型调用。实施单先确认 repair 入口是否接受外部 issue，不接受就在本档只对 B 生效并写明 | advisory 期读数 + 用户定阈值（§6） |
| 硬拦 | `block` | 保留初稿，答案前置披露段「以下断言未通过口径核验：…」，命中句不作为结论呈现（形态待用户拍板） | `status → partial`，`public_answer` 走 `TerminalFacts` 披露（先例：`premise_calculation.admit` 出错分支） | revise 期读数 + 用户拍板硬拦形态 |

**degraded 的在线语义**（CLI 退 2 的对应物）：任何档下，`build_context` 解不出比较范围数等「判据本次没有真在跑」的情况都要写进收据 `claim_scope.degraded[]`，并出一条 `advisory_only=True` 的 WARN「口径越界·判据降级」——**不触发修订**（模型改不了取数形状），但 **`block` 档下 degraded 不得算作 clean**，按 unverifiable 披露。进程内没有退出码，不写这条就会「取数形状一变，判据无声放行」。

## 4. 映射表：CLI 的证据上下文怎么在进程内重建

CLI 侧 `scripts/check_answer_claims.py::build_context` **[实测]** 是唯一的真值来源；进程内映射每一格都要对着它做，验收见 §5。

| `ClaimEvidenceContext` 字段 | CLI 来源（`build_context`） | 引擎 A 进程内 | 引擎 B 进程内 | 风险 |
|---|---|---|---|---|
| `question` | `run.json.question` | `frame.raw_question` | `options.query` | 低 |
| `evidence_dates` | `episode.outcome.evidence[].source_date` 去重排序 | `structurally_verified.outcome.evidence` 的 `AgentEvidence.source_date` | D 块 outcome / citations 的日期字段——**没有现成的等价集合，需新建提取**（先例 `extract_stale_block_hints`） | 中：B 侧集合定义若与 CLI 不同，日期规则的「证据日期」理由文字会漂 |
| `calendar_evidence` | 只能 `--calendar-evidence-source` 人工声明；**工具面没有交易日历 dataset，episode 推不出** | 恒 `False`——除非未来新增日历工具，并**按工具身份**（不是 payload 子串）判定 | 同 | 高：任何「自动推断」都是猜，#854 刚把这条 fail-open 关掉 |
| `compared_scope_count` | tool_request `filters[].field ∈ _SECTOR_FIELDS` 的 code 数 | adapter 持有的 events/traces 里的 tool_request（同一解析函数，从 CLI 抽成共享函数后两边 import） | D 块（板块归属 / 边际量）实际比较的板块清单长度 | 中：解析函数不共享就会分叉 |
| `known_scope_total` | `--scope-total` 人工给，来源写进收据 | **开放问题 1**：在线要么查库（当日 `fact_sector_stock_daily` 该股归属板块数）由 adapter 回合开始时预取注入；要么 `None` → 范围规则沉默并记 degraded | 同 | 高：查库属副作用边界，需用户拍 |
| `fund_flow_evidence` | 请求 `metrics ∈ FUND_FLOW_METRICS`（注册表锁漂移）**或** 取回证据台账命中 `_LEDGER_FLOW` 正则；**不扫工具参数** | 同两条：events 的 metrics + `AgentEvidence.detail` 正则 | D 块是否含资金流 provider 的实际取数 | 中：只认 metrics 会把新闻里的「主力净流入 38 亿」判成无证据（回测 13 例） |

映射实现原则：**把 `build_context` 的解析拆成可 import 的纯函数，CLI 与进程内共用**；不允许进程内「重新实现一遍」。否则两边各修各的，parity 测试会在第一次分叉时才报警。

## 5. 实施单必带的验收（写死，缺一不合）

1. **重放一致**：两个冻结 run（材料题命中 1 条 `unit_gap_claim_contradicts_input`；行情题 `--scope-total 20` 命中 3 条 `latest_trading_day_unverified / scope_claim_exceeds_comparison / fund_flow_claim_without_flow_evidence`）在进程内重建上下文后，裁决与 CLI **逐字段一致**：`rules_hit`、每条 `quote / reason`、`issue_count`、`degraded`。期望值直接读 `docs/verification/2026-09-22-claim-scope-hardening/evidence/frozen-run-parity.json` 与 `docs/verification/2026-09-22-answer-claim-scope/evidence/claim-scope-run_*.json`，夹具用原句（#850/#854 测试已含，勿改写成抽象样例）。
2. **阳性对照**（本单 2026-09-22 在 `5f5ce2d11` 上已实测，数值见 `~/.finance-runtime/reviews/claim-scope-merge-65-20260922/positive-control/`）：从 `_RULE_CHECKS` 拿掉日期规则，行情题 `rules_hit` 3 → 2（退出码仍 1，因另两条仍命中）；拿掉单位规则，材料题退出码 1 → 0；各自还原后回到原读数。实施后同一组对照要在进程内路径重跑一次。
3. **关掉后逐字节不变**：`ASK_CLAIM_SCOPE_REVIEW` 未设 / `off` 时，`AskResult` 序列化与 `continuous-episode.json` 与接入前逐字节一致（先例：带读开关 #606「关掉后逐字节不变」）。
4. **层级门禁**：`scripts/layer_audit.py` 不新增 services → runtime 依赖；`answer_claim_scope` 保持只 import 标准库。
5. **观察面**：advisory 期的在场率 / 命中率 / 按规则拆分读数由离线脚本读收据得出，不新增 live 请求。
6. **degraded 落地**：构造一个解不出比较范围数的 episode 夹具，收据必须出现 `degraded` 与「判据降级」WARN；删掉这段实现测试必红。

## 6. 升格流程

- 每一次升档 = 一次单独授权 + 一张单；判据阈值（观察多少个交易日、多少次真实作答、人工复核误报率上限）由用户定，**本文不预填数字**。
- 升档输入：advisory 期按规则拆分的命中率与人工复核误报率，对照 1347 run 回测的分布（96 命中 → 修掉 30 条误报后 66 真命中不丢）。回测是历史存量，线上分布可能不同，这正是要先 advisory 的原因。
- 任一档发现新 fail-open（换说法绕过、取数形状变化导致静默放行）→ 先补规则与回归夹具（走 #854 那样的独立 PR），不在升档单里顺手改判据。

## 7. 非目标

- 不修四条原始缺陷（写手行为）；不给召回率（无人工标注集）；不部署、不翻 `ASK_SEMANTIC_JUDGE`；不改 Workbench UI（notes 走既有 `_review_notes_from_gate`）；不把 `calendar_evidence` 做成自动推断。

## 8. 开放问题（用户拍板后进实施单）

1. `known_scope_total` 在线来源：查库预取注入，还是 `None` → 沉默 + degraded？
2. 硬拦档的公开形态：披露段 vs 直接 partial。
3. 引擎 A 的 revise 档是否允许删句式修复改公开正文（判官关时的确定性修复路径）。
4. 先接 A 还是 B：**推荐 A 先 advisory**（动机在 A，K3 首跑是 A），B 同一张单一起接以免两边判据分叉。

## 9. 参考

- 判据与 CLI：`intelligence/services/answer_claim_scope.py`、`scripts/check_answer_claims.py`（#854 分支）
- 证据：`docs/verification/2026-09-22-answer-claim-scope/`、`…-claim-scope-backtest/`、`…-claim-scope-hardening/`
- 接缝原文：`docs/handoffs/inflight/fix-claim-scope-hardening-0922.md`「接入点设计」节
- 本单证据根：`~/.finance-runtime/reviews/claim-scope-merge-65-20260922/`
- 门页：`docs/agent-product-door.md`（两条引擎的定义）
