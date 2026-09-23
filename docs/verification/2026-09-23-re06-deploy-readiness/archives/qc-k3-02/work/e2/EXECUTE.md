# K3 e2 组（C1–C3）stage=execute · v3 执行账本

stage=execute；group=e2；revision=8eac9b3b55c563b1eb3be58686fcc0918464f69a；
baseline=b59d6eed0356ae093b52bd291ab328628de8790e。
唯一执行入口：只读包装器 `run_probe_v3.py e2 <role>`；每条 bash 仅提交该一条命令。
候选源码全程只读，未修改。本账本只记执行事实，不构成候选 PASS/FAIL 裁决。

## 执行汇总（3 次包装器调用，全部入账）

| # | role | 探针来源 | exit | 收集 | 结果 | blocked | 分类 |
|---|---|---|---|---|---|---|---|
| 1 | positive_control | inputs/frozen-explore-e2-v3/probes/test_positive_control.py | 1 | 1 | 1 failed | null | probe_bug / expected_positive_control |
| 2 | reviewer | inputs/frozen-explore-e2-v3/probes/test_reviewer.py | 0 | 19 | 19 passed | null | passed（初稿一次成功，无 v2 修复） |
| 3 | author | candidate intelligence/tests/test_e2_local_question_delivery.py | 0 | 20 | 20 passed | null | passed |

收据（包装器 stdout 末行 EXECUTION_RECEIPT 原样照录）：

1. positive_control
   `.../work/e2/runs/positive_control-1790166907182750000/receipt.json`
   sha256=d5bc1a39d1b6979665c1f6a179d5b32f62877f5e1a144637c1ec748f1c3be277
2. reviewer
   `.../work/e2/runs/reviewer-1790166915668737000/receipt.json`
   sha256=a14c4f157cc2740820138ea0ed3ba6e03377cd7e09b4ca4d8ba0e3fcb97cd9ec
3. author
   `.../work/e2/runs/author-1790166926481397000/receipt.json`
   sha256=aa90464a7d031a0cb6e8221e22f7a9337cdf423aff6e7bc8281e22327e5ccbfb

各次唯一运行目录内另存：完整 stdout 日志、junit.xml、receipt.json（含源码 sha256、
资源准入输出、退出码、计数）。

## 逐次说明

### 1. positive_control — 必红对照（非候选缺陷，不从账本删除）
- exit=1，junit 恰好 1 条 failure：`test_positive_control_must_fail` 的 `assert 1 == 2`，
  无其它条数。满足「必须 exit1 且恰好一条断言失败」。
- 结论：执行链（沙箱→pytest→junit→收据）存活；reviewer/author 结果可采信。
- classification=`probe_bug/expected_positive_control`（runs 子表同列本收据一次）。

### 2. reviewer — 独立冻结初稿，一次成功
- 收集 19 条（13 个探针函数含参数化展开），19 passed，exit=0。
- 初稿未出现 API/fixture 错误，**未触发 v2 修复路径**（无 test_reviewer_v2.py）。
- 分类：probe 自身 `passed`，即探针针对的 C1–C3 实现行为与独立断言全部一致。
  各项探针 → 主张映射见 EXPLORE.md（探针正文哈希冻结在 inputs/frozen-explore-e2-v3，
  包装器记录 sources_sha256 与运行后 sources_unchanged，可核）。

### 3. author — 既有作者测试，单独计数
- 收集 20 条，20 passed，exit=0。v2 场「.agents 目录 stat 权限阻断作者收集」的
  历史阻塞在本 v3 资源门（仅放行列明受限目录元数据 + 收集预检）下未再出现。
- 作者结果**单独记入 author_runs，未合并进 reviewer_runs**。

## 历史阻塞说明（保留，不计入本次）
- v2：独立探针 19 通 + 正控 1 预期失败，但作者收集被 .agents stat 阻断 → 本 v3 作者
  运行补得 20/20。v2 结果不并入本次通过数。
- 更早期 E2：沙箱不能启动 ps，pytest 之前失败 → 原始记录保留，既非对照成功亦非候选缺陷。

## suspected_issues
- 无。三次运行未观察到与主张冲突的实现行为，未保留任何 candidate_bug 待裁决项。

## limits（本阶段未覆盖，明示）
- reviewer 探针 = 19 例的横截面：语义裁决层（episode_semantic_verifier.py 未读）、
  material_only 正向 legal_gap 结清对照、completed+缺口的 validate_episode_finish 拒收、
  IO 纯度其它 effect 值、中文「第N题」小节形式、混绑（gap+hashes 同槽）、stale 多余
  answer_q* 槽恢复——均按 EXPLORE.md 标记未探。
- 探针断言依据探索期普通解释器冒烟 + 源码阅读；本阶段 pytest 结果为其正式确认。
- complete=true 仅表示执行阶段交付完毕（3 次调用齐全入账），不是候选通过结论；
  候选裁决交由后续 report 阶段独立作出。
