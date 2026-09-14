# feat/extraction-first-p0 · 工单 #53 提取前置 P0

## 这个分支做什么
带读披露前先收用户自己写的观察剧本，再展示字段差异（不评分、不算收敛）；可显式跳过，不计失败。
工单 `docs/superpowers/specs/2026-09-14-extraction-first-p0-workorder.md`；设计依据 `~/foresight/docs/specs/2026-09-13-extraction-first-spec.md` rev.4（仓外，未改）。

## 当前状态
已提交、未推、未合 main、未开真人实验。**顶端以 `git log -1` 为准**——写死过 SHA，下轮返修后它就指向旧树，复审按它复跑会漏掉最终修复（复审二实测）。三轮返修：`08ca525f`（S1–S10/N2/N3）→ `8410e9d3`（R1–R6）→ 第三轮（T1–T4 + 导出同族）。
复审报告与探针：`~/.finance-runtime/reviews/extraction-caba87c7-20260914/`。

## 决策与被否方案
首轮五个取舍见快照 `docs/handoffs/2026-09-14-extraction-first-p0-review-fixes.md`；各轮返修的修法与理由逐条在对应提交信息正文，此处不抄。

## 已验证（第二轮由另一 agent 独立复跑，非提交者自述）
- 复审三根探针全翻绿：残片隔离后读写通且残片保留；`pending_after_retry=[]`；错误关联退 2 且无 checkpoint；close 后 confirm/skip 退 2；改 due 出新记录新 checkpoint；复用草稿可按新尝试确认（exit=0）。
- 10 个相关测试模块 245 过；改动三文件 ruff 过；`merge-tree` 对 `gitea/main@1fef3d27` 无冲突；树干净。

## 未验证 / 已知边界
- 19 条变异 RED→GREEN 仅提交者自述，未独立复跑。
- **仓级全量已跑**（提交者，`8410e9d3` 干净树）：首跑 1 红 `test_real_conversation_round_trip_persists_skills_sse_and_three_turns`，
  **重跑 9670P/0F/exit 0**。判负载敏感抖动：零路径交集、隔离连跑两次绿、
  `docs/verification/2026-09-07-forward-call-gate-live.md` 有同一条测试的同一处置。
  **不是「已知红照常合」**，两读数留档 `/tmp/xfp0/final{3,4}-pytest.txt`。
- read 失败诊断已拆成两句（收据没落 = 交付结果未知 / 收据已落仅终态没写 = 确实交付了、重试可愈合），带断言。
- 绑定读数与被测 SHA **只记在收据 §1 / §6.1 一处**，其余文档一律指过去、不复制 SHA。
- 真人效果 / §7 阈值 / 真库身份解析仍未验（同前轮）。

## 下一步
1. 下一轮复审固定**当前分支顶端**复核（收据 §1 那一行是唯一 SHA 来源）；通过且**用户明说**才合 main，不推不合。
2. 合并前对当时最新 `gitea/main` 重跑 merge-tree + 本机等价 CI 全叶子（pytest/ruff/前端/e2e/registry-check）。

## 踩过的坑
前轮三条（跑测中途改码、夹具绕过缺陷路径、同名两道防线分别钉）见快照。本轮新增：
- `git status` 显示 ` M` 但 `git diff` 为空 = 只被碰过 mtime；先 `update-index --refresh` 再下「树干净」结论。
- 共享仓里别的 agent 可能正在你读状态的间隙推进分支：动手前 `rev-parse HEAD` + reflog 确认顶端没动。
