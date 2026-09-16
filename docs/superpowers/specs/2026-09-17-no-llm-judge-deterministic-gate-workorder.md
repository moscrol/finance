# 2026-09-17 去掉线上 LLM 判官：确定性门模式工单（#55）

> 可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
> 后续单：#56 `2026-09-17-judge-code-retirement-workorder.md`（占位）——默认翻转与代码退役，等本单上线满 5 个交易日再派。两单串行，不并行。

## 1. 背景与动机

- **用户决策链**：2026-09-12 用户拍板撤掉独立 Grok CLI 判官（启动器 `~/.local/bin/start-finance-workbench` L153–199 的「2026-09-12 用户决策」注释块：08-28 余额 402、09-02 read-only 沙箱拒启、09-09 钉版本被自动更新清掉，三次都以 `judge unavailable → fail-closed → 公开稿被扣` 收场），改为 kimi-k3 写手兼判官（`correlated_judge=true`）。2026-09-17 用户进一步拍板：**不用 LLM 判官**，「Knevo 本身也没这个设计」。
- **Knevo 的对照**：`docs/learning/knevo-distill/README.md` L15 把质量闭环写成「判断写入 → 市场验证 → fork 回上下文 → 用户归因 → 反思回写 → 统计胜率」；`docs/learning/knevo-distill/workflow-absorption-2026-09-16.md` L21/L24 把「事实核对」定为同一 agent 带工具执行的生成纪律，并明确「不冒充新增语义审稿器」「拒绝没发现问题就 PASS」。即 Knevo 没有生成时的第二模型判官，靠事后结果与人校。
- **判官在生产里实际的贡献与代价**（2026-09-17 01:1x 统计 `~/.local/share/finance-workbench/users/*/runs/*/report.json`，mtime ≥ 09-12，24 个带 `gate_receipt` 的 run）：`judge_status` repaired 9 / unavailable 8 / passed 3 / not_applicable 4。repaired 的两个典型是**引用绑定类**（「第 12 句把 E104 的日期写成 2026-08-21，证据 source_date 是 2026-09-11」「第 19 句引用 E14、E23 不在 counterpoint 的 evidence_ids 里」），机械可判；unavailable 占三分之一，正是被忍受的税。
- **已定形态决策（写死，执行方不要重新设计）**：
  1. 用**一个共享开关** `ASK_SEMANTIC_JUDGE=llm|off` 同时管 Episode 终稿判官（引擎 A）与 ask 合成判官（引擎 B）；检索侧证据判官沿用既有 `ASK_EVIDENCE_JUDGE=off`（`intelligence/services/evidence_judge.py` L13–27），不新造第二个开关。
  2. 开关常量与解析放**无依赖小模块** `intelligence/services/judge_mode.py`（照 `intelligence/call_identity.py` 的形状：三个字符串常量 + 一个纯函数），A/B 两侧只 import，不各写一套。
  3. **本单默认值仍是 `llm`**，行为零变化；生产启动器显式置 `off`。这不是「永远不开的开关」——生产真用它。默认翻转、删 held 路径归 #56。理由：`episode_semantic_verifier.py` 有 5646 行、测试 5047 行钉着现行为，一次翻默认会把回归和设计变更搅在一张 PR 里。
  4. `off` 模式**不引入新的 `judge_status` 值**（`JudgeStatus` Literal 见 `episode_semantic_verifier.py` L107），而是加一个正交字段 `judge_mode: "llm" | "deterministic"`。`passed/repaired/rejected` 在两种模式下都表示「过了门 / 门删了句并修好 / 修不好」，`judge_mode` 说明是谁在判。理由：`continuous_turn_adapter.py` L803/904/943/1085/1191/1201 与 `gate_receipt.py` 按 `judge_status` 的闭集分类，加新值会散到六处。
  5. 判官抓到的两类绑定错误的去向：**日期错配 → 机械探测器删句**（与 `_mismatched_weekday_indexes` 同级、同 preflight 阶段）；**槽级引用越界 → 只记账不删句**。后者是 R-20260821-06 的既定裁决（`_project_semantic_evidence` docstring：「漏记账不该让判官对真实证据做存在性否证」），本单不推翻，只把量记出来给以后决定。

## 2. 目标（交付物，每条可验收）

1. `intelligence/services/judge_mode.py`：`JUDGE_MODE_LLM="llm"`、`JUDGE_MODE_OFF="off"`、`ENV_SEMANTIC_JUDGE="ASK_SEMANTIC_JUDGE"`、`semantic_judge_mode() -> str`（`0/false/off/no` → off，其余 → llm）。
2. 引擎 A：`SemanticEpisodeVerifier._run_judge` 在 `off` 模式返回合成的 `_JudgeCall(report=GroundingJudgeReport(passed=True), unavailable=False, correlated=False)`，**不触碰任何模型**；三处调用点（首判 L1526、修复后复判 L1761、第三判 L1907）与 V11 引导复判（L1285，经 `_guided_retrieve_and_rejudge` L1158）都经这一个缝。V11 在 `off` 模式记 `GuidedRetrievalTelemetry(skip_reason="judge_off")`。判后机械门（`_apply_numeric_condition_gate` / `_reject_material_gaps` / `_apply_meta_disclosure_exemption` / `_apply_unresolved_evidence_ordinal_gate`）与 `_repair`（纯机械删句 + 补回真值，见 L2997 前后与 `_repair` 定义）照常运行，所以整条链在 `off` 下是全确定性的。
3. `SemanticEpisodeOutcome` 新字段 `judge_mode`（默认 `"llm"`），`to_dict` 平铺；`off` 时 `correlated_judge=False`、`pending_rejudge=False`、`judge_unavailable_count=0`。`gate_receipt.py` 私有/公开字段表（L45–69）加 `judge_mode`，旧收据无该字段读为 `None`。
4. 引擎 B：`ask_synthesis.py` 判官段（L2188–2300）在 `off` 模式不发调用、不走 `_judge_outage_release`（那是「判官掉线放行」，会给正文加 `_JUDGE_OUTAGE_NOTICE` 首句——判官没掉线，不能这么标），`_record_synthesis_phase(name="judge", status="skipped", reason="judge_off")`，`GroundedComposerShadow.status` 新值 `"deterministic_only"`，正文按确定性层结果原样交付。
5. 机械探测器 `_mismatched_evidence_date_indexes(sentences, verified)`：句子**恰好引用一条** E（`cited_evidence_ordinals`，`episode_protocol.py` L676）且能反解（`evidence_ordinal_table` L650）；句内含 ≥1 个完整日期（复用 `_FULL_ISO_DATE_RE` / `_FULL_CHINESE_DATE_RE`）；该 E 的语料（title/detail/source/source_date，同 `_bound_evidence_dates` 的拼法）含 ≥1 个完整日期；且句内**没有任何一个**日期出现在该语料中 → 删句。新增 `VERDICT_REASON_EVIDENCE_DATE="evidence_date_mismatch"`、`_EVIDENCE_DATE_ISSUE`，接进 `_mechanical_reasons_by_index`、`_mechanical_sentence_indexes`、preflight 元组与 `preflight_issues`。两种模式都生效。
6. 记账探测 `_cited_outside_slot_binding_indexes(sentences, verified)`：按句序扫，遇到含 `answer_has_output_marker(output_id, text)`（`task_fulfillment.py` L448）的句子切换当前槽；其后句子引用的 E 若不在该槽 `OutputEvidenceBinding.output_id` 对应的 `evidence_hashes`（`agent_runtime.py` L228）反解出的 E 集合里，记 `sentence_verdicts` 一条 `reason=cited_outside_slot_binding`、`decision=kept`（复用 `_record_sentence_verdicts`，新增阶段常量 `VERDICT_STAGE_CENSUS="census"`），并在 `to_dict` 加 `cited_outside_slot_count`。**正文逐字节不变。** 无槽标记的稿子跳过、记 0。
7. 测试 `intelligence/tests/test_judge_mode_off.py`（见 §6 验收），既有判官测试在 `llm` 默认下全绿不改。
8. 文档：`docs/agent-product-door.md` L254「A 与 B 的门禁不对等」段后加「判官模式」小节（开关、两种模式各自的 `judge_status` 语义、`judge_mode` 字段、生产取值、#56 指针）；`~/agent-memory/10_knowledge/finance-agent-capability-graph.md` 加在途行 `intelligence/services/judge_mode.py::semantic_judge_mode@feat/no-llm-judge-mode`（合入后提升）；本单 INDEX 行状态回写。
9. 上线步骤写进本单 §5 末尾，**合并后由用户确认再切**，不随代码 PR 一起做。

## 3. 非目标（写死认领）

- ❌ 翻默认值为 `off`、删 `_gap_answer(judge_unavailable=True)` / `CAUSE_JUDGE_UNAVAILABLE_HELD`（L1572 / L3336）held 路径、删 V11 `_guided_retrieve_and_rejudge`、删 `judge_source_recheck` 挂载、删 B 侧 `_judge_outage_release` → **#56 占位单**。
- ❌ 重新配置独立判官链、改启动器 `LLM_JUDGE_*` 任何一行 → 用户决策范围，本单不碰。
- ❌ 槽级引用越界**删句** → 只记账（目标 6），删句决策等 census 数据；理由 R-20260821-06。
- ❌ 整改 `_verify_inner` 顶部三处结构守卫（contract 缺失 / hash 不一致 / 非可放行 partial，L1345–1395）与空稿（L1414）返回的 `judge_status="unavailable"` 标签 → 它们让 `judge_unavailable_count` 混入结构失败，是本单统计里 unavailable 8 的一部分成因；**登记 finding**，不在本单改语义。
- ❌ 扩引擎 B 的确定性输出质检（answer_lint / 五要素 lint）→ 不动。
- ❌ 离线评测侧判官（`scripts/run_quality_ablation.py`、`intelligence/services/auto_eval.py` 的 answer-score）→ 评测工装不是线上门禁，`--no-score` 已可关；不改。#775 的资格门在无独立判官时按设计只出 `no_call`，属预期。
- ❌ 前端展示 `judge_mode` → `intelligence/webapp/src` 零处读 `judge_status`（2026-09-17 grep），无需改；登记 finding「收据字段前端不展示」。
- ❌ Knevo 式学习闭环（错因归因回流、批注回流）→ 另立单，本单不占号不开工。
- ❌ 主检出树 `/Users/a77/finance-workspace-private`（detached `b4a35fa2`，L2 运维覆盖层，30 个未提交改动）→ 不动、不 reset、不在里面跑门禁。

## 4. 证据路径表（先读这些，禁止臆测）

| 文件 | 看什么 |
|---|---|
| `intelligence/services/episode_semantic_verifier.py` L106–107 | `SemanticStatus` / `JudgeStatus` 闭集 |
| 同上 L518–640 | `SemanticEpisodeOutcome` 字段与 `to_dict`（`pending_rejudge`、`judge_unavailable_count` 由 `classify_degrade_counts` 算） |
| 同上 L716–735 | `_JudgeCall` 字段（合成对象照它构造） |
| 同上 L933–960 | `SemanticEpisodeVerifier.__init__`（`judge_fn` 是最小测试缝，`primary_judge`/`judge_client` 生产注入） |
| 同上 L1330–1760 | `_verify_inner` 全流程：结构守卫 → 机械 preflight（L1424–1440 三探测器 + `_repair`）→ `_apply_unattempted_claim_rewrite` → 首判 L1526 → 判后机械门 L1580–1590 → 修复 → 复判 L1761 |
| 同上 L1158–1300 | `_guided_retrieve_and_rejudge`（V11，内含复判 L1285）、`guided_retrieve_enabled()` L846–853 |
| 同上 L2377–2600 | `_run_judge`：窗与尝试帽、`primary is None → unavailable "semantic judge unavailable"` L2588 |
| 同上 L2250–2330 | `_judge_request`（`output_bindings` / `evidence_registry` 投影）、`source_recheck` 挂载 L2322 |
| 同上 `_bound_evidence_dates`、`_mismatched_weekday_indexes`、`_unresolved_evidence_ordinal_indexes`、`_mechanical_sentence_indexes`、`_mechanical_reasons_by_index`、`_record_sentence_verdicts`、`VERDICT_*` L211–223、`_*_ISSUE` L281–296 | 新探测器与记账**复用勿重造**的全部零件 |
| `intelligence/services/episode_protocol.py` L650–690 | `evidence_ordinal_table` / `parse_evidence_ordinal` / `cited_evidence_ordinals` |
| `intelligence/services/agent_runtime.py` L228 | `OutputEvidenceBinding(output_id, evidence_hashes, gap, basis)` |
| `intelligence/services/task_fulfillment.py` L448 | `answer_has_output_marker` |
| `intelligence/services/ask_synthesis.py` L1971–1980、L2188–2370 | B 侧判官段、`_judge_outage_release`、`GroundedComposerShadow` 各 status 值 |
| `intelligence/services/answer_model.py` L517 | `GroundingJudgeReport(passed, rejected_sentence_indexes, issues)`；`GroundedComposerShadow` 字段 |
| `intelligence/services/gate_receipt.py` L15–160 | 字段表、`classify_degrade_counts`、`episode_public_correlated_judge` |
| `intelligence/services/evidence_judge.py` L13–27 | `ASK_EVIDENCE_JUDGE` 三态（已有，沿用） |
| `intelligence/api/app.py` L583 | 生产构造 `SemanticEpisodeVerifier(primary_judge=client, finalizer=finalizer)` |
| `intelligence/runtime/continuous_turn_adapter.py` L803/904/943/1085/1191/1201 | `judge_status` 的六个消费点（不加新值的理由） |
| `intelligence/call_identity.py` | 无依赖常量模块的形状（照抄） |
| `intelligence/tests/test_episode_semantic_verifier.py` | 构造 `TaskFrame` / `VerifiedEpisodeOutcome` / contract 的夹具，**复用勿重造** |
| `intelligence/tests/test_judge_outage_degrades.py`、`test_v11_judge_guided_retrieval.py`、`test_judge_sentence_verdicts.py`、`test_semantic_judge_gate.py` | 既有判官行为的钉子；`off` 模式不得让它们变红 |
| `~/.local/bin/start-finance-workbench` L138、L153–199 | 生产 `ASK_EVIDENCE_JUDGE="auto"`、判官决策注释块（只读，本单不改） |
| `docs/agent-product-door.md` L254 | A/B 门禁段（文档改动落点） |
| `docs/workflows/acceptance-workflow.md` §4 | 上线用的链切五步（合并后另做） |

## 5. 步骤

0. 开工三连：`git status --short && git branch --show-current`、`git worktree list`、读 `docs/handoffs/inflight/feat-no-llm-judge-mode.md`（首轮不存在）。主检出树不干净是常态，**不要在里面做**。
1. `git fetch gitea && git worktree add /Users/a77/fwp-wt-no-llm-judge -b feat/no-llm-judge-mode gitea/main`（门禁树必须在 `/Users/a77/` 下，`/tmp` 会让 Codex 沙箱测试假红）。解释器一律主树 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。
2. T1 `judge_mode.py` + 单测（三值解析、大小写与空白）。
3. T2 引擎 A：`_run_judge` 首行按模式短路；`_guided_retrieve_and_rejudge` 首行按模式 skip；`SemanticEpisodeOutcome.judge_mode` + `to_dict` + `_finalize_outcome` / `_completed_public` 把 mode 带到每个返回点（用 `replace(outcome, judge_mode=...)` 收口在 `verify()` 出口一处，别在十几个 return 各写一遍）。
4. T3 `gate_receipt.py` 字段表 + `continuous_turn_adapter.py` 若有字段白名单同步。
5. T4 引擎 B：判官段按模式短路，新 shadow status；确认 `present_grounded_composer_answer` 的确定性层照常跑。
6. T5 日期错配探测器 + 槽级记账探测器。
7. T6 测试文件 `test_judge_mode_off.py`；跑定向集：`intelligence/tests/test_episode_semantic_verifier.py test_judge_*.py test_v11_judge_guided_retrieval.py test_semantic_judge_gate.py test_judge_mode_off.py` 与 `rg -l "ask_synthesis" intelligence/tests`。
8. 变异反证（§6 倒数第三条），还原后全量四叶：`ruff check .`、`pytest -q`（收据 `check_test_receipt.py --expect-revision <tip> --base-drift-max 5`）、前端四步、e2e（另一会话占 8791 时 `WORKBENCH_E2E_PORT=8793 RE06_E2E_PORT=8795 RE06_E2E_URL=http://127.0.0.1:8795`，`WORKBENCH_PYTHON` 指主树 venv）、registry 五项。
9. 文档三处（§2 目标 8）；`handoff` skill 覆写 `docs/handoffs/inflight/feat-no-llm-judge-mode.md`（≤3 KB）；PR 开到 `main`，**不合**。
10. 上线（合并后、用户确认）：`cp ~/.local/bin/start-finance-workbench ~/.local/bin/start-finance-workbench.bak-<date>-pre-nojudge` → 加 `export ASK_SEMANTIC_JUDGE="off"`、`ASK_EVIDENCE_JUDGE="auto"` 改 `"off"`（在 L138 原地改，注释写日期与本单号）→ 按 acceptance-workflow §4 链切五步切到含本单的 main → health 三读 + readiness → 探针 run 的 `report.json` 里 `gate_receipt.judge_mode == "deterministic"`、`judge_unavailable_count == 0`。回滚 = 还原启动器备份 + `launchctl kickstart -k gui/$(id -u)/com.a77.finance-workbench`（代码侧不用回滚，默认 `llm`）。

## 6. 验收（全部勾上才算完）

- [ ] `ASK_SEMANTIC_JUDGE=off` + 不注入任何判官：干净 structural → `status=completed`、`judge_status=passed`、`judge_mode=deterministic`、`judge_unavailable_count=0`、`pending_rejudge=False`、`public_answer` 等于草稿（不是 gap 模板）。**阳性对照**：同一夹具 `llm` 模式 → `judge_status=unavailable`、gap 模板——证明变的是模式不是夹具。
- [ ] `off` 模式下注入一个「拒绝所有句子」的 `judge_fn`：被调用 **0 次**（计数断言），含修复后的复判与第三判路径。
- [ ] `off` 模式机械门仍删句：含表外 E 引用的草稿 → `judge_status=repaired`、该句消失、`sentence_verdicts` 含 `unresolved_evidence_ordinal`。
- [ ] 日期错配探测器阳性：单引 E、句内 `2026-08-21`、E 语料仅 `2026-09-11` → 删句，reason `evidence_date_mismatch`；三阴性：日期一致 / 句子双引 E / E 语料无日期 → 保留。`llm` 与 `off` 两种模式都成立。
- [ ] 槽级记账：草稿带两个槽标记，第二槽句子引用只绑在第一槽的 E → `sentence_verdicts` 一条 `cited_outside_slot_binding` / `decision=kept`，`cited_outside_slot_count=1`，`public_answer` 与 `llm` 模式逐字节相同。
- [ ] 引擎 B `off`：不调判官（`urlopen` 替身 0 次）、phase 记录 `judge/skipped/judge_off`、正文不以 `_JUDGE_OUTAGE_NOTICE` 开头、shadow `status=deterministic_only`；`llm` 模式下 `test_judge_outage_degrades.py` 原样全绿。
- [ ] `gate_receipt` 私有与公开字段都含 `judge_mode`；对无该字段的旧收据字典调用不抛。
- [ ] 变异：`semantic_judge_mode()` 恒返 `"llm"` → 上面第 1、2、6 条至少各一红；还原后定向集全绿（每门 `grep -c` 自检替换数）。
- [ ] 四叶全绿且收据 `--expect-revision` 绑定分支尖；`git merge-tree --write-tree gitea/main feat/no-llm-judge-mode` exit 0。
- [ ] 文档三处已改；INDEX #55 状态行回写为「PR #N 待确认」。
- [ ] 上线后（用户确认切换后另勾）：探针 `judge_mode=deterministic`、`judge_unavailable_count=0`、`ASK_EVIDENCE_JUDGE=off` 下 `evidence_judge` 零调用。

## 7. 红线（抄自 AGENTS.md，不新发明）

- 提交只用 pathspec：`git add -- <文件>`、`git commit -- <文件>`；不用 `git add -A` / `.`。合并回 main 必须等用户确认，不强推。
- pytest / ruff 一律 `.venv-workbench/bin/python -m …`；宿主 python3 缺依赖会得到偏高失败数。
- 不提交 `.env*`、密钥、`*.duckdb`、缓存；不写明文密钥。
- `~/.finance-runtime/finance-workspace-*` 是生产快照，只读，不在里面改任何文件；启动器 `~/.local/bin/start-finance-workbench` 在合并前不改。
- 台账取号 `python3 scripts/claim_ledger_id.py claim --branch feat/no-llm-judge-mode`；本单不需要预注册号，若执行中要写 R 号按此取。
- 不动 `.claude/skills/` 实目录；不新建第二份能力清单，能力改动回写 `finance-agent-capability-graph.md`。
- 「有多少判官调用被省掉」这类数字一律指向产生它的脚本或收据，不写死进文档。
