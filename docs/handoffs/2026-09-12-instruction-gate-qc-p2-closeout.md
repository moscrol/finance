# 2026-09-12 指令门禁清障 · 质检 P2 收尾

## 背景

`fix/instruction-gate-clearance@ecc05e09` 的独立质检（报告与全部证据：
`~/.finance-runtime/reviews/instruction-ecc05e09-qc-lzglg8rw/review.md`）判定主体修复
与全绿收据可信，但留两项 P2，建议补齐后再推送：

1. **Standards**：inflight 交接 5088 字节，超 ≤3K 约定，SessionStart 注入截掉了当前
   状态、r3 矩阵指针与已知边界——接手者先看到完成历史，拿不到接着工作的边界。
2. **Spec**：`build_registry.py` 的仓根绑定仍依赖 git common-dir 的父目录名。改名
   独立 clone（如 `renamed-clone/`）里 self_name 失配，`scan` 扫到同级标准名别树的
   技能、`backfill-tables` 退出 0 并改写别树 `AGENTS.md`。基线在同布局下同形出错，
   属旧边界未修完，不是本轮新增的回归；标准名主树及其附属 worktree 的修复有效。

期间 gitea/main 从 `c703e068` 漂到 `883e3d36`（PR #741 合入）。

## 按发现顺序

1. 复读质检探针 `renamed_clone_probe.py`：其断言「候选改别树 AGENTS.md、本树未变」
   与「新增设计断言在改名布局下 AssertionError」均固定指向同一缺口——common-dir
   父目录名不是仓的业务身份。
2. 先写端到端判据 `test_renamed_clone_scan_and_backfill_stay_in_current_tree`
   （tmp 下 `renamed-clone/` 真 git 仓 + 同级有效 `finance-workspace-private/` 诱饵树，
   脚本拷进 clone 加载）。在 ecc05e09 上跑红：
   `scan 扫到了别树内容：['ws/decoy-skill']`，与探针形状一致。
3. 修复后同判据转绿（5 passed），本树 registry 四步复验零漂移、零意外改动。
4. 变基到 883e3d36：`bcbdbb88`（台账清障）被 git 按同 patch-id 跳过——其内容与
   main 的 `a2ecd8e9` 逐字节相等（5 个台账文件逐一 cmp 验证），是 #741 已合入的
   同一份改动，跳过即忠实。其余 8 条 patch-id 变基前后逐一相同。

## 决策对比

| 问题 | 方案与评价 | 选择 |
|---|---|---|
| ws 仓根绑定 | 继续按 git common-dir 父目录名推 self_name：clone 改名即失配，且「父目录名」从来不是业务身份；明文要求独立 clone 固定命名：未检索到该约束存在，历史部署还出现过 `finance-workspace-<newsha>` 命名；直接绑 `__file__` 仓根：脚本 checked in 在 finance-workspace-private，REPO_ROOT 本来就是权威 | `_SELF_REPO_NAME = "finance-workspace-private"` 常量，删掉 `_self_repo_name()` 与 subprocess 依赖；kb/site 仍按同级约定发现 |
| 交接压缩 | 截尾删节：丢的恰是风险面；只删不搬：决策来历断档 | 长历史留在既有快照 `2026-09-12-instruction-gate-clearance.md`，本轮背景进本文；inflight 只留压缩表＋状态＋边界＋下一步，≤3K 字节 |

## 验证与收据

- 判据先红后绿：ecc05e09 上 `1 failed, 4 passed`（红的正是新判据）；修复后 `5 passed`。
- 本树（三仓在场）四步 registry 检查 exit 0 且 `git status` 零意外改动。
- 变基忠实性：patch-id 多重集相等（含被跳过条与 `a2ecd8e9` 的等价证明）。
- **最终整仓门禁在冻结 SHA 变基定版后跑**，逐叶命令/退出码/日志/收据索引：
  `~/.finance-runtime/gates/instruction-clearance-r4-20260912/matrix.md`。
  本快照不是通过证明，不在运行后 amend 写入读数。

## 后续 / 不要做

- 不要顺手扩大到 watchdog、`FWP_TEST_RECEIPT_DIR`、bash 3.2 崩溃——质检明确列为
  边界外，各自由自己的工单承接。
- `repos.present` 仍记录扫描时本地磁盘状态，跨机器可漂；拆这个设计是后续独立任务。
- 推送与开 PR 在最终收据合格后进行；合并 main 仍等用户明确确认。
