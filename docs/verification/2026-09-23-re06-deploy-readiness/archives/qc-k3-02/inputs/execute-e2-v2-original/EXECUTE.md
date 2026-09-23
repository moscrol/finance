# K3 e2 组（C1–C3）stage=execute 执行账本（v2 终审场）

- revision=8eac9b3b55c563b1eb3be58686fcc0918464f69a
- baseline=b59d6eed0356ae093b52bd291ab328628de8790e
- 唯一执行入口：只读包装器 `run_probe_v2.py e2 <role>`（宿主即时资源检查 + 原沙箱内跑 pytest）
- 探针：宿主逐字冻结稿 `inputs/frozen-explore-e2-v2/probes/test_reviewer.py`（未改一字，无需 v2 修正版）
- 历史说明：旧 E2 执行因沙箱无法启动 ps 在 pytest 之前失败，原始记录保留但不计入本次任何计数。

## 执行流水（全部包装器调用，各列一次）

| # | role | exit | 收集 | 通过 | 失败 | 错误 | classification | receipt |
|---|---|---|---|---|---|---|---|---|
| 1 | positive_control | 1 | 1 | 0 | 1 | 0 | probe_bug/expected_positive_control | work/e2/runs/positive_control-1790165683204812000/receipt.json (sha256 406ef397…f93baa) |
| 2 | reviewer | 0 | 19 | 19 | 0 | 0 | pass | work/e2/runs/reviewer-1790165691133932000/receipt.json (sha256 682de5d3…269d51) |
| 3 | author | 4 | 0 | 0 | 0 | 1 | blocked_sandbox_permission | work/e2/runs/author-1790165702885800000/receipt.json (sha256 b5e16a1e…50bfcb) |

## 1. positive_control（执行链阳性对照）

- 结果：exit 1，恰好 1 条失败 `test_positive_control_must_fail`（`assert 1 == 2`），与预期完全一致。
- classification=`probe_bug/expected_positive_control`：证明执行链能捕获失败；**不是候选缺陷，不从账本删除**。

## 2. reviewer（冻结初稿，19/19 全绿）

- 冻结稿一次通过：collected=19，passed=19，failed=0，errors=0，exit 0，用时 0.34s。
- 无 API/fixture 错误，**未写 test_reviewer_v2.py**，无任何 probe_bug 修正。
- 19 例清单（JUnit 权威记录，classname=inputs.frozen-explore-e2-v2.probes.test_reviewer）：
  - C1（10 例）：numbering_starting_at_2 冻结不重排、q0 边界端到端、齐全正控、重复小节仍缺、
    binding_cannot_hide[empty_body/placeholder/quoted_only/memo_overflow]、跳号不重排、重复编号不塌缩
  - C2（3 例）：material_only 豁免不外溢、本地缺口只 partial 非 legal_gap、冻结数据范围拒外呼证据
  - C3（6 例）：契约往返保原题号、restore 保护[drop/optional/reasoning]、旧 direct_answer 形状不误伤、
    未编号/full 编号不改形
- 含义：C1–C3 主张在探针覆盖范围内与实现一致；**本阶段未发现 candidate_bug**。

## 3. author（既有测试，沙箱阻断，未执行）

- 包装器选定作者测试 `intelligence/tests/test_e2_local_question_delivery.py`，但 pytest 收集阶段
  `pytest_ignore_collect` 对候选树 `.agents` 目录 stat 时被沙箱拒绝：
  `PermissionError: [Errno 1] Operation not permitted: '.../candidate/finance-workspace-private/.agents'`
- exit 4（pytest 用法/收集错误），collected=0，errors=1，**0 条作者测试实际运行**。
- 这是环境/沙箱阻断，不是候选缺陷，也不是资源门 exit75；按纪律未重试、未绕门、未直接 python -m pytest。
- 作者测试通过数**记「未执行」，不以 0 冒充通过**；是否换径补跑交 report/后续会话裁决。

## 计数汇总（本阶段）

- reviewer 探针：19 通过 / 0 失败 / 0 错误（冻结稿，独立证据）。
- positive_control：1 失败（预期内，probe_bug/expected_positive_control）。
- author：未执行（沙箱阻断），不计通过、不计失败。
- 旧 E2 执行结果：不计入。

## suspected_issues

- 无（对候选无疑点；reviewer 19/19 全绿）。

## limits / 未覆盖

- author 既有测试未能执行（上述沙箱 PermissionError），C1–C3 的作者侧证据缺失。
- EXPLORE.md 自述「13 条/17 例」为预估，冻结稿实际 14 函数/19 例；按任务要求以实际收集数 19 为准。
- 探针未覆盖（沿用 EXPLORE.md）：episode_semantic_verifier 未读未探；material_only 正向 legal_gap
  结清无对照探针；混绑（gap+hashes 同槽）未探；stale answer_q7 槽恢复未探；中文「第N题」小节未探；
  IO 纯度仅探 external_or_mixed。
- complete=true 仅表示本阶段交付齐全，**不代表候选通过**；最终裁决属 report 阶段。
