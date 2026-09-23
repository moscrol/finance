# K3 终审 · e2 组（C1–C3）stage=report

- revision=8eac9b3b55c563b1eb3be58686fcc0918464f69a
- baseline=b59d6eed0356ae093b52bd291ab328628de8790e
- 候选只读：`candidate/finance-workspace-private`；未改任何候选源码，未复跑测试（report 阶段）
- 核对件：`stage-execution-checks-v3/e2.json` 仅核对日志/JUnit/退出码/哈希（complete_execution_evidence=true, errors=[]），其 candidate_semantic_verdict=null；语义裁决由本终审独立作出
- 历史保留：更早期 E2 沙箱 ps 失败既非对照成功亦非候选缺陷；v2 作者收集被 .agents stat 阻断的结果不并入本轮通过数；v3 三次运行为本轮唯一入账依据

## 执行事实核对（以实际收据为准，非探索预估）

| role | 收据 sha256（前16） | exit | 收集/通过 | 判定 |
|---|---|---|---|---|
| positive_control | d5bc1a39d1b6979665 | 1 | 收1 / 败1 | 首红1例=`test_positive_control_must_fail`（`assert 1 == 2`），junit 恰好1条 failure；分类 probe_bug/expected_positive_control，**不计入业务失败**；执行链存活 |
| reviewer | a14c4f157cc27408 | 0 | **收19 / 19 passed** | 冻结初稿一次成功，probe sha256=b4c6296fbc06eb92，sources_unchanged=true，无 v2 修复、无 candidate_bug |
| author | aa90464a7d031a0c | 0 | **收20 / 20 passed** | 作者测试 `intelligence/tests/test_e2_local_question_delivery.py`，单独计数，未并入 reviewer_runs |

本会话另抽读收据 `runs/reviewer-1790166915668737000/receipt.json`：sandbox-exec 包装、隔离 users 根、退出码/计数/sources 哈希与宿主核对件一致。宿主核对件三笔收据哈希与 EXECUTE.json 全部吻合。

## 独立语义抽核（本会话亲读，非照抄）

- 冻结探针正文 `inputs/frozen-explore-e2-v3/probes/test_reviewer.py`（311行）：自造查询/答案/绑定，消费链为真实路径 `understand_query → build_episode_context → verify_episode_outcome / validate_episode_finish`；`test_positive_control.py` 即 `assert 1 == 2`。
- `material_delivery.py:172-190` `question_body`：`len(blocks)!=1 → ""`、占位符集（待补/待回答/略/暂无/tbd）、memo 超限返回空——与 C1 探针断言语义一致；`:212-228` `material_delivery_missing_outputs` 确以 binding+正文双判，绑定不掩盖缺答。
- `research_contract.py:1128-1138`：local_only 恢复保护以「已有 answer_q* 槽」为判据，要求每题唯一必需且 grounding_mode=evidence，否则 ResearchContractError；无 answer_q* 槽（旧 direct_answer 形状）不进该校验——与 C3 探针一致。

## 逐条裁决

### C1 原题号冻结、绑定不掩盖缺答 — verified
- 证据：探针 7 函数（从2编号冻结不重组/collect q2,q3→answer_q2,answer_q3；q0 端到端；正文+绑定齐全无缺；重复 ## q3 小节仍缺；空正文/占位符/纯引用/memo超120字 4 例绑定齐全仍缺；跳号不重排为 q1；重复编号不塌缩），全部实跑通过（收据 a14c…，19/19）；源码抽核 material_delivery.py:172-228 语义吻合；消费路径 user_task.py:966-1005 连续编号约束 + episode_factory.py:721-733 冻结分支（探索期阅读，探针经真实路径运行确认行为）。
- limits：中文「第N题」小节形式未探；跳号仅钉死「q1 不得出现」不变量，未枚举全部跳号组合；混绑（gap+hashes 同槽）未探（旧疑点③）。

### C2 material_only 豁免不外溢 local — verified
- 证据：探针 3 函数（local 契约 `material_input_output_ids==∅`、`claim_finish_format is None`、交付 rules 含 local_only 不含 legal_gap；本地题披露缺口经 `verify_episode_outcome` 落 partial、answer_q2 missing、无 legal_gap 状态；`validate_episode_finish` 对 io_effect=external_or_mixed 证据抛 ValueError「frozen data scope」、local_read 放行），实跑 19/19 内全部通过；episode_verifier.py:239-257（legal_gap 仅 material_only）为探索期阅读，探针行为实测确认。
- limits：material_only 正向 legal_gap 结清对照未建（需材料载体）；completed+缺口的 validate 拒收路径未自造（作者 20/20 覆盖，不计入独立验证）；IO 纯度仅探 external_or_mixed 一种 effect；`episode_semantic_verifier.py`（6720行）未读，语义裁决层无探针。

### C3 恢复保护既有题号 — verified
- 证据：探针 4 函数（to_dict→from_dict 往返保 q2/q3 槽；删槽/降可选/改 model_reasoning 3 例均抛 ResearchContractError 且 match "local_only"；旧 direct_answer 形状恢复不误伤；未编号本地题与 full 编号题均无 answer_q* 槽），实跑通过；源码抽核 research_contract.py:1128-1138 判据吻合（探索期 :1125-1138 行号引用与本次抽读一致）。
- limits：stale 多余 answer_q* 槽恢复未探（旧疑点④，疑似良性，不猜为缺陷）。

## Quality（本组范围）— PASS_WITH_LIMITS

findings：
- 未观察到与主张冲突的实现行为；三次运行 suspected_issues 为空，无 candidate_bug 保留项。
- 维护性正面：恢复保护判据写在 research_contract.py:1128-1138 并注释说明兼容旧 direct_answer 会话的意图，判据为「已有 answer_q* 槽」而非「有编号题」，回归方向考虑周全；缺答判定集中于 material_delivery.py `question_body`/`material_delivery_missing_outputs`，形状/语义分离（注释明示 disclosed gap 是否结清由 verifier 决定）。
- 回归风险（非缺陷）：compile_material_contract 不查重与 from_dict:105 拒重的不对称存在；当前靠 user_task.py:966-1005 连续编号约束闭合可达性（已由探针钉死不变量）。若未来出现绕开 classify_top_level_regions 直接构造 TopLevelRegions 的路径，dict 塌缩风险会重新打开——建议后续在 compile_material_contract 一并查重（EXPLORE 疑点①，当前不升级为缺陷）。
- 覆盖限制：19 例为横截面，不得推广为全部业务无缺陷：episode_semantic_verifier 语义层（6720行）未读无探针；material_only 正向 legal_gap 对照、completed+缺口拒收、IO 纯度其它 effect 值、中文「第N题」、混绑同槽、stale 多余槽均未探；作者测试 20/20 单独计数支持同向结论但不替代独立覆盖。

limits：同各 C1–C3 limits；候选全局结论由各组完整证据合并，本组不代签别组（C7 独立 UI 动态测试与发布物身份、consent 事务同族分类均不在 e2 范围，本组不涉及、不置评）。

blocking_issues：无（本组范围内 C1–C3 均已独立验证；历史 v2/.agents 与更早沙箱 ps 事件按规则仅保留说明，非本轮阻塞）。

complete=true 仅表示本终审报告交付完整，不代表候选全局通过。
