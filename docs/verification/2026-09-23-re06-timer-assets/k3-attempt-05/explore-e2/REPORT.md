# E2 组探索收官报告（stage=explore, group=e2, 仅 C1–C3）

## 交付完整性声明（先说缺口）

**工具预算在静态阅读阶段耗尽，探针文件未能落盘**：`work/e2/probes/test_reviewer.py` 未创建，`work/e2/EXPLORE.md` 未创建。以下全部为静态源码阅读证据，**未运行任何测试，不签候选 PASS**。JSON 中 `complete:true` 仅表示本场探索任务收尾，artifacts 为空属实。

## 已核对的静态证据（含行号）

### C1 — local_only 编号题冻结 answer_qN，绑定不掩盖正文缺失（静态支持，未见反例）
- 题号来源：`user_task.py:955-1044`，按用户原始编号 `q{number}` 解析且顺序校验（`expected = number + 1`），起始号可非 1；消费者不得重编号（`user_task.py:455-459`）。
- 契约校验：`material_contract.py:101-109`，`question_id` 必须 `q\d+`、重复题号拒绝。
- 槽冻结：`material_delivery.py` `material_question_outputs`（约89-100行）按 `answer_{question_id}` 取槽。
- 正文门槛：`question_body`（约186-200行）——重复段（`len(blocks)!=1`）、空正文、仅引用、仅题标题、与题干同文、memo 超字数均返回 `""`；`material_delivery_missing_outputs`（约218-229行）要求 binding 存在 + 正文非空 + gap 已公开披露三者齐备，缺一即 missing。**"来源绑定齐全不能掩盖缺答题正文"在代码层成立。**

### C2 — material_only 豁免不泄漏到 local_only（静态支持，未见反例）
- `episode_verifier.py:240-263`：`legal_gap` 仅在 `grounding_scope(contract)=="material_only"` 时成立；local_only 下 spec=None → `REQUIRED_OUTPUT_GAP`（普通 partial）。
- `material_delivery.py:53-60`：`material_input_output_ids` 对 local_only 返回 `frozenset()`，不豁免工具证据可达性；`with_all_material_gaps_notice`（约233-252行）仅 material_only 加「仅凭本轮材料」声明；`_LOCAL_ONLY_RULES` 明确"没有可结清的合法缺口"。
- `episode_semantic_verifier.py:4181-4199`（`_material_questions_settled`：legal_gap 永不提升 completed）与 4221-4237（语义放行 material_only 专用分支，local_only 走普通 RELEASE_POLICY）。

### C3 — 恢复保护题号；未编号本地题与 full 不改形（静态支持，附条件）
- 恢复校验：`research_contract.py:1125-1145`（`from_dict` 触发 `__post_init__`），local_only 且已有 `answer_q*` 槽时每题须唯一、必需、evidence 槽；判据用"合同已有 answer_q\*"而非"有编号问题"，明确保护旧 direct_answer 形状会话。
- 工厂：`episode_factory.py:712-731`，仅 material_only 有题或 local_only **有编号题**才重建 answer_q\* 槽；local_only 无题（未编号）elif 条件不满足 → 形状不变；full 模式两分支均不进（854行 full 亦跳过受限预检）。`material_delivery.py` `question_delivery_scope` 对 full 返回 None → 无编号强制。

## 疑点（未构造反例验证，移交下一场）
1. `research_contract.py:1129` 保护循环只遍历 `material.questions`：多余的无题 `answer_q99` 槽不会被该校验拒绝，影响未知。
2. 旧 direct_answer 形状恢复后，若 `material.questions` 非空但无 answer_q\* 槽，`material_question_outputs` 返回空 → 编号题在旧合同上无逐题结构校验（`research_contract.py:1127-1129` 注释显示有意为之，属合同外遗留路径，风险未量化）。
3. `episode_factory.py:717/731` 重建槽时 `output_ids = (*material_descriptions, "evidence_boundary")` 会丢弃此前挂上的 prior_recall/residual_prime 槽，是否预期未验证。
4. 跨轮 questions 变化时恢复会 raise（fail closed）而非静默改号——方向合理但未造反例。
5. `_HEADER_RE` 不匹配 `## q1。`（句号后缀），保守方向，影响小。

## 未覆盖边界 / 限制
- **探针零落盘**：作者测试（`intelligence/tests/test_e2_local_question_delivery.py`，289行）仅读至218行用于学 API；restore 参数化、unnumbered_and_full、real episode 测试未读完，更未据以改写自造探针。
- `episode_semantic_verifier.py` 仅读 4180-4249；2614/3445/5664/6299 处 legal_gap 用法未细查。`episode_protocol.py:1129-1161` 调用点、`material_grounding.py:148` 的 `grounding_scope` 定义未读。
- 未读 source.diff、未做 baseline 对比、未运行 pytest（本场要求不运行）。C4–C10 属其他组，未审。

## 建议下一场执行（探针补齐后）
```
cd candidate/finance-workspace-private && /Users/a77/finance-workspace-private/.venv-workbench/bin/python -m pytest work/e2/probes/test_reviewer.py -q
```
探针应基于 `understand_query`+`build_episode_context` 构造 local_only 双题合同（参考作者测试的 `AgentOutcome/OutputEvidenceBinding/validate_episode_finish/verify_episode_outcome` API，临时 task_id，无真实 LLM），重点造：多余 answer_q99 槽恢复、题号跳号（q1,q3）、旧 direct_answer 形状+编号题、full 模式编号题不改形、绑定齐全但正文仅引用/重复段。

```json
{"stage":"explore","group":"e2","revision":"b24c86f87aaef6244dc6a2c6cf80f74ae1918943","baseline":"ffd1b7f1572067e9a4c7e3a5845e99cf7f876cfb","complete":true,"artifacts":[],"suspected_issues":["research_contract.py:1129 恢复校验不拒绝无对应题的多余 answer_qN 槽","旧 direct_answer 形状合同恢复后编号题无逐题结构校验（有意设计但风险未量化）","episode_factory.py:717/731 重建编号槽时丢弃 prior_recall/residual_prime 槽是否预期未验证"],"limits":["探针与 EXPLORE.md 未落盘（工具预算耗尽），artifacts 为空","未运行 pytest，未签候选 PASS","作者测试仅读 218/289 行；episode_semantic_verifier.py 仅局部阅读","未读 source.diff / 未做 baseline 对比","仅覆盖 C1-C3"]}
```
