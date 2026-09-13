# feat/extraction-first-p0 · 工单 #53 提取前置 P0

## 这个分支做什么
带读披露之前先收**用户自己写的**观察剧本，再展示字段差异（不评分、不算收敛）；可显式跳过，不计失败。
工单 `docs/superpowers/specs/2026-09-14-extraction-first-p0-workorder.md`，收据 `docs/verification/2026-09-14-extraction-first-p0.md`。
基线 `gitea/main@d7e5380551ba`（工单冻结号）。设计依据 `~/foresight/docs/specs/2026-09-13-extraction-first-spec.md` rev.4（仓外，未改）。

## 当前状态
已提交三笔，**未推、未合 main、未部署、未开真人实验**：
- `95f3c5e7` 实现 + 测试 + 文档
- `b42dc9bf` 收据回填
- `08ca525f` 质检返修（S1–S10 / N2 / N3 十二项）

## 决策与被否方案
五个非显然取舍（成功事件随行写、顺序门在 build 之前、台账分型不另开文件、确认去重键不含时间戳、关联键 scope 由身份推导）连同理由，在日期快照 `docs/handoffs/2026-09-14-extraction-first-p0-review-fixes.md`。

## 已验证
- 干净基线与最终读数：见收据 §1 / §6，两次都在**跑测期间无人触碰**的干净提交上取得，并用 `scripts/check_test_receipt.py --expect-revision` 绑定。
- 八条门禁叶子：ruff / pytest / frontend lint·typecheck·test·build / e2e / registry-check。
- 验收 A1–A15 + 质检返修 25 条回归；13 个变异逐条 RED→GREEN（`/tmp/xfp0/mutations.txt`）。

## 未验证 / 已知边界
- **真人效果完全未验证**：工单 §7 三项阈值未填，实验未开跑。`read_completed` 只证明系统交付，`pending` 不等于离开。
- 真库路径上的身份解析未在本单跑过（用例全打桩），复用既有 `river.resolve_entity`。
- `--from-draft` 与 `--from-slice` 同传时后者胜，未做互斥拒绝。
- 关联键里的 `scope` 是冗余项（由 canonical id 唯一决定），按工单口径保留。

## 下一步
1. 用户评审；**要合并请明说**（本分支不自行合 main、不推）。
2. 合并前按「比较基准是目标分支不是快照」重新 diff；`gitea/main` 已从 `d7e5380` 前移到 `1fef3d27`，工单 INDEX 是热文件，开 PR 前 `git merge-tree` 列一遍新造冲突。
3. 开跑真人实验前先由用户填 §7 三项阈值写进工单，不得事后补。

## 踩过的坑
全部细节（含质检 14 项的逐条根因与返修取舍）在日期快照 `docs/handoffs/2026-09-14-extraction-first-p0-review-fixes.md`。三条最贵的：
- **全量跑到一半改被测代码**，那次读数条件不自洽；收据还把它写成「干净基线」——假证据比没证据更糟。
- **夹具绕开了缺陷路径**：遮蔽用例的夹具行没有 `due`，正好躲过 `expire_stale`，于是缺陷在绿灯下活着。
- **同名两道防线要分别钉**：写入侧与读取侧都修了，只断言最终结果会被其中一道兜住，另一道回退看不出来。
