# #75 claim-scope — GLM 独立审查 Spec 裁决（glm-session-03，report 阶段）

- 候选：`/Users/a77/.finance-runtime/reviews/claim-scope-runtime-20260923/continue-01/qc/candidate`（git HEAD 实测 `14f885e01f4a538492b54a27f67ab5d33b58f875`，源码 `git status --porcelain -- intelligence scripts conftest.py pytest.ini` 为空，无 `__pycache__` 新增）
- 计数来源：本人以 `xml.etree.ElementTree` 解析 `probes.xml`/`positive.xml`/`author.xml`（非手写数字、非单行 grep）：probes **tests=15, errors=0, failures=0, skipped=0**；positive **tests=1, errors=0, failures=1**（唯一失败即 `probe_positive_control.py:10` 行内 `assert 1 == 2`，装置控制预期红）；author **tests=22, errors=0, failures=0**。
- 探针文件 sha256 `0366c056…` 与执行会话（glm-session-02）逐字节一致（diff 校验）；修正配额 0/1 使用，无修后分账。
- 标注约定：**[S]** = 静态阅读源码；**[D]** = 独立探针动态执行（probes.xml 用例）；[A] = 作者测试（仅佐证，不作为独立证据）。

## C1 — CLI 与 runtime 共用 `build_context`，无复制规则 → **verified**
- [S] `scripts/check_answer_claims.py:37` `from intelligence.services.claim_scope_context import build_context`，:75 调用；:33/:78 import 并调用 `review_answer_claims`。`intelligence/services/claim_scope_review.py:16` import 同一符号，:39 调用。规则本体唯一在 `intelligence/services/answer_claim_scope.py`（`_RULE_CHECKS` :355，恰四条）。
- [D] `probes.xml::test_c1_cli_and_runtime_share_single_build_context`：CLI 模块、`claim_scope_review` 模块与 `claim_scope_context` 三方 `build_context` 为**同一函数对象**。explore.md 引用行号 47-49/73-76 与实测 37/75 有小幅漂移，实质一致。

## C2 — 未设/off 不改公开答案与既有序列化形状 → **verified（动态部分覆盖，见限制）**
- [S] off 早退：`claim_scope_review.py:31-33`（off → `None`）；`ask_claim_scope.py:20-21`（off → 入参原对象直接返回，先于任何字段改动）。序列化条件键：`output_review.py:100-102`、`episode_semantic_verifier.py:789-791` 仅在 `claim_scope is not None` 时加 `claim_scope_mode/claim_scope` 键；off 时 `episode_semantic_verifier.py:804-805` 显式 `replace(outcome, claim_scope=None)`。
- [S] advisory WARN 无从进入答案正文：`conversation_orchestrator.py:3747-3749` `_review_notes_from_gate` 先于 :3751-3753 claim-scope 审阅；`_review_notes_from_gate`（:1493-1500）过滤 `advisory_only`。
- [D] `test_c2_off_returns_none_and_ask_passthrough_identity`：off → `None`；哨兵对象经 `review_ask_claim_scope` 原样同一对象返回。
- 覆盖限制：**序列化形状（to_dict 键集）未独立动态压测**，为静态结论；作者 `test_off_keeps_serialized_gates_and_answer_unchanged[None/off]` 绿仅佐证 [A]。

## C3 — advisory 不改终态/正文/修订次数，无新增模型/取数；非法/未实现档 off+私有诊断 → **verified**
- [S] `claim_scope_review.py` 全文件 import 仅 `hashlib/os` + 本地服务，`review_runtime_claims` 无 IO/模型/取数。`revise/block` → `claim_scope_mode_unsupported`，其他非法值 → `claim_scope_mode_invalid`，mode 均 `off`（:26-29，私有诊断键，无 `checks`，`ask_claim_scope.py` 用 `receipt.get("checks", [])` 安全）。checks 全部 `status=WARN, advisory_only=True`（:57-66）；`output_review.py:86-90` `warn_count` 显式排除 `advisory_only` → gate 状态不受影响。
- [D] `test_c3_unsupported_and_invalid_tiers_are_off_with_private_diagnostic`（revise/block/banana/ADVISORY 四档）；`test_c3_advisory_checks_are_all_warn_and_advisory_only`（全 WARN+advisory_only、`warn_count==0`、gate `PASS`）。
- 覆盖限制："无新增模型/取数调用"为静态结论（import 面审查），未做调用拦截类动态探针。

## C4 — 四类已知词法形状检出，不主张语义完备 → **verified**
- [S] `answer_claim_scope.py:355` `_RULE_CHECKS` 恰四条；模块 docstring 明示"检出器，不是评分器/判官"；`ClaimScopeReport.to_dict` 的 `boundary` 文案随收据输出。
- [D] `test_c4_latest_trading_day_shapes`（越界断言命中；日历证据/否定句/8 字内免责/库内限定四类放行）、`test_c4_scope_overreach_shapes`（有/无全集数命中、已比较限定放行）、`test_c4_fund_flow_and_unit_gap_shapes`（断言命中；引号提及/榜单名放行；题面有单位命中、无单位放行）。
- 词表完备性不在主张内（主张明示不主张语义完备）。

## C5 — 资金流证据不认模型自写检索词；否定/缺失台账不自动豁免 → **verified**
- [S] `claim_scope_context.py:88-98` `_fund_flow_metrics` 只读 `arguments.metrics` 对照 `FUND_FLOW_METRICS` 注册表，不扫 payload 文本；:50-62 `_ledger_flow_clauses` 按子句切分，否定/缺失子句（`_LEDGER_NEGATION`）入 `fund_flow_ledger_negated_clauses` 不算证据，仅肯定子句置 `fund_flow_in_evidence_ledger`。
- [D] `test_c5_search_keywords_are_not_flow_evidence`（kb_search query 写满资金词、无 metrics → `fund_flow_metrics_seen==[]` 仍命中规则）；`test_c5_registry_metric_and_ledger_clauses`（registry 指标成立；否定子句不豁免且进 negated；肯定子句成立）。

## C6 — 缺比较数/全集全称句、malformed 映射显式 degraded，不默认 clean → **verified**
- [S] `claim_scope_review.py:50` `scope_total_not_provided`、:52 `compared_scope_count_unavailable`、:46 `context_mapping_failed:*`、:59 `clean = report["clean"] and not degraded`；CLI 降级退 2：`check_answer_claims.py:96`；`build_context` 自身 degraded：`claim_scope_context.py:123-129`。
- [D] `test_c6_universal_without_total_is_degraded_not_clean`、`test_c6_scope_total_without_codes_is_degraded`、`test_c6_malformed_mapping_degrades_runtime_receipt`（episode=None → AttributeError 被捕获进 `context_mapping_failed:AttributeError`，clean=False）。

## C7 — A 最终及异常恢复出口收据绑定交付文本 hash，恢复只用此前核验证据 → **verified（静态布线 + helper 级动态；集成级动态未覆盖，见限制）**
- [S] 最终出口：`continuous_turn_adapter.py:1183-1186` `review_public_claim_scope(semantic, …, delivered_answer=answer, evidence_outcome=outcome)`，位于全部公开投影（`recheck_material_public_delivery`/`_with_semantic_contract_gaps`/`_track_public_delivery`）之后；语义终出口 `episode_semantic_verifier.py:1573`（缺省用 `outcome.public_answer`）。恢复出口：`continuous_turn_adapter.py:1377-1380`，`evidence_outcome=trusted`（= :1331 `semantic.verified.outcome`，且恢复出口前置核验过滤 :1339-1344），`delivered_answer=view(TerminalFacts(cause=CAUSE_VERIFIED, public=answer))`——`session_projection.py:90-93` 该 cause 下 `view` 返回 `facts.public` 原文，即哈希绑定最终交付文本。hash 计算：`claim_scope_review.py:62`。orchestrator B 侧：3753 审阅后 `answer_text` 至 :3951 `revise_message(content=answer_text)` 无再赋值（grep 3753-3960 段核实）。
- [D] `test_c7_receipt_hashes_delivered_answer`：**helper 级**——`review_runtime_claims` 的 `answer_sha256 == sha256(answer)`，两次运行稳定。
- 覆盖限制：**A 侧 adapter/verifier 集成（真实最终出口与异常恢复流中 receipt 实际生成与绑定）未做独立动态执行**；作者 `test_adapter_reviews_final_delivery_including_recovery[none/raises/recheck_raises/good]` 4 参数绿仅佐证 [A]，按规则不作为独立证据采纳，不扩大 helper 级探针结论。

## C8 — B 早退/延后合成/Workbench 最终稿可观察；缺工具请求账显式 degraded → **verified（静态入口 + helper 级动态；B 全链动态未覆盖，与主张一致）**
- [S] 三入口：`ask.py:1564-1565`（`answer_query` 统一包裹 `_answer_query_impl`，内层早退一并覆盖）、`ask_synthesis.py:1055-1057`（`synthesize_prepared_answer` 包裹）、`conversation_orchestrator.py:3751-3753`（Workbench 最终稿，`delivered_answer=answer_text`）。`ask_claim_scope.py:24-27` events 恒空 + `mapping_limits=("engine_b_tool_requests_unavailable",)` 恒传 → B 收据 degraded 恒非空、不默认 clean。
- [D] `test_c8_b_path_mapping_limit_is_explicit`：**管道级**——`review_runtime_claims(mapping_limits=(…,))` 恒进 degraded 且 `clean=False`。
- 覆盖限制：**B 侧三个真实入口未独立动态执行**（是否还存在绕过 `answer_query` 包裹的其他 B 出口未穷举）；主张本身不裁 B 完整映射，降级机制与主张一致。作者 `test_ask_early_return_is_reviewed_without_revising`/`test_deferred_synthesis_replaces_old_advisory_receipt`/`test_workbench_b_persists_review_of_delivered_text` 绿仅佐证 [A]。

## C9 — 观察收据私有；WARN 不进 actionable warn/公开附录；私有落盘在终态认领后、败方不写 → **verified（仅静态独立证据；无独立动态探针，见限制）**
- [S] `conversation_orchestrator.py:3941` `_claim_terminal_run(run_id, STATUS_COMPLETED)` 先于 :3942-3948 `add_artifact(…, "claim-scope-review.json", …, visibility="internal")`；全仓 grep `claim-scope-review` 唯一写点即此处（失败/取消分支 :4186/:4346/:4607/:5236/:5319 均不写该文件）。advisory WARN 不入 `warn_count`/`summary_lines`（`output_review.py:86-90, 105-106` actionable 过滤）；正文 notes 在收据前生成（:3747-3749 先于 :3753）。A 侧 receipt 内嵌私有 episode artifact（adapter :1196-1200 `semantic_verifier` 键内），未见进公开附录。
- 覆盖限制：**落盘时序（终态认领竞争）与失败路径不落盘无独立动态探针**，本条独立证据止于静态；作者 `test_claim_scope_runtime.py` 相关断言（如 :198 附近"失败路径不落盘"）已随 22/22 绿执行，但属作者证据 [A]，仅佐证。

## C10 — census 显式产物分母，缺收据不算 clean，不调网络/模型 → **verified（合成 fixture 动态；未对真实产物目录运行）**
- [S] `scripts/claim_scope_census.py` 全文件 import 仅 `argparse/collections/json/pathlib/typing`，`census` 只 `json.loads(path.read_text())`；缺 `mode` → `modes["missing"]` 单列不并入 `advisory_count`；invalid/unsupported 单列；分母 `artifact_count = len(paths)` 显式输入产物。
- [D] `test_c10_census_denominator_and_missing`：分母=3、missing=1、invalid_or_unsupported=1、degraded=1、presence_rate=1/3、hit_rate_among_advisory=1.0。
- 覆盖限制：仅合成 fixture；未对真实生产产物目录运行（本场约束无生产数据访问，符合范围）。

## 汇总

| 主张 | 裁决 | 独立动态覆盖 |
|---|---|---|
| C1 | verified | 是（对象同一性） |
| C2 | verified | 部分（off 早退；序列化形状静态） |
| C3 | verified | 是（档位+advisory_only 形状）；无 IO 为静态 |
| C4 | verified | 是（3 用例形状+边界） |
| C5 | verified | 是（2 用例） |
| C6 | verified | 是（3 用例）；CLI 退码静态 |
| C7 | verified | 部分（helper 级 hash；集成级未覆盖） |
| C8 | verified | 部分（管道级降级；B 入口静态） |
| C9 | verified | 否（仅静态；作者佐证不计独立） |
| C10 | verified | 是（合成 fixture） |

无 not_verified 主张；B 侧完整映射/词表完备性/生产数据为 out_of_scope（与主张边界一致）。
