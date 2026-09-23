# 2026-09-23 无人接手工作盘点（worktree / PR / 会话）

盘点者：Claude Code（主检出树 `b4a35fa2c`，18:0x–19:xx CST）。用户原话：「检查下有没有 worktree 或者 PR 没有 agent 在接手执行，或者没有收尾的」→「没人做的你分别写 spec，然后你顺手可以做的比如合并啥的你就做掉」。
所有读数 **[实测]**，方法：`scripts/worktree_board.py --json`（287 棵树，基线 `gitea/main@bbd53487f`，盘点中主干又进到 `b59d6eed0`）；`scripts/gitea_pr.py list`（40 张 open）；每张 PR head 上的 `docs/handoffs/inflight/<分支>.md`；本机 `git merge-tree --write-tree` 对 main 与各自 base 的冲突探测；PR `updated_at` 与最后评论；`~/.pi/agent/sessions/…/*.jsonl` 近 3 天转录（mtime、首末消息、提到的 PR 号）；`ps` / `lsof` 进程 cwd；`git cherry` 与「新增代码行在 main 中原样可见比例」两种落地核对。

## 一、活会话与它们正在管的东西

12 个 Pi 会话于 09:22–09:29 CST 启动，盘点时最近 30 分钟内均有动作：

| 会话在做 | PR / 分支 | 盘点时一步 |
|---|---|---|
| runtime 量具补验 | #884 `test/runtime-probe-repair-0923` | 本地领先远端 12 提交，在加沙箱预检 |
| 行情恢复 QC 修复（#61 线） | `fix/market-recovery-qc-0923`（+25，未推，无 PR） | 在 `bbd53487f` + 修复上跑 tests |
| 波次协调者 | gate-closeout 系列树 / `docs/closeout-workorders-0922`（本地 +4 未推） | 全量 pytest 81% |
| claim-scope 终态（#65 线） | #883 + #885 | 候选 `264bc9d0d` 全门禁 |
| 东财熔断（#60，P0，今日 18:30 夜跑） | #856 | 预览 `d6ad408d` 定向 119P，全量在跑 |
| 自适应回路 L6 自然题（#72） | #868 | Q1 降级 / Q2 失败 / Q3 未发，转离线收尾 |
| #67/#69 证据台账 | #880 | 第三次 Python 准入 |
| #70 后续 + 8792 切换预演 | #874（提到 30 次）、#862 已合 | 切前探针通过，隔离候选做 HTTP 就绪 |
| #876 合后主干门禁 | main tip | registry 过、定向 74P，等资源跑前端 |
| Knevo 收口 | #877（本地 +131 未推） | 全仓终门禁 @ `537c4c4c4` |
| #74 + #77 批（已收工） | #857；#804 / #807 / #836 / #838 / #840 / #849 / #853 | 结论「无 PR 满足当前完整合并门禁」，没合没关 |
| #876（已收工） | 已合入 `bbd53487f` | — |

另有 `claude` pid 32111（16 h，主检出树，另一终端）与 Claude 桌面 scratch 会话，均非本仓 PR 的持有者。

## 二、无人接手（无活会话、最后动作 ≥ 1 天）

**已被接替却没关**（今日全部关闭并留指针，评论 6297–6325）：

| PR | 接替链 | 新增代码在 main 可见比例 | 处置 |
|---|---|---|---|
| #783 | → #800 → #833（已关）→ #863 已合 | 99% | 关闭；剩余历史工作 → #68 |
| #800 | → #833 → #863 | 99% | 关闭 |
| #797 | → #835（已关）→ #863（财务 squash） | 94% | 关闭；#855 → #66 |
| #798 | → #834（已关）→ #863 | 98% | 关闭 |
| #829 | → #841（评论明写接替） | 32%（未落地，载体是 #841） | 关闭 → #841 / #68 |
| #809 | → #832（#809 head 是 #832 祖先） | 52%（未落地） | 关闭 → #832 / 新单 #81 |
| #811 | → #816 → #817（评论明写「以 #816 为验收入口」） | 0% | 关闭 → #817 / 新单 #82 |

**阻塞或暂停、无 owner**（各立新单，见 INDEX 续表 81–87）：

| PR | 分支 | 对 main 冲突 | 新增代码在 main 可见 | 停下原因 | 新单 |
|---|---|---|---|---|---|
| #832 | `fix/react-trace-qc-0921` | 6 | 44% | K3 600 s 超时无终稿；自然质量 0 次 | #81 |
| #816 / #817 | `fix/arena-*-0921` | 0 | 0% | 离线复核 NO-GO 后 #817 修了但无新组合四叶 | #82 |
| #802 / #813 | `fix/backfill-*` | 0 | 4% | K3 两轴 ENOSPC 中断；生产回填从未跑 | #83 |
| #812 | `ops/worktree-ownership-closeout-0921` | 1（`worktree_board.py`） | — | 同上；与今日 #876 拆树工具重叠 | #84 |
| #810 | `feat/hithink-research-data` | 1（lessons） | — | Codex 额度到 09-27；429 未处置；独立复审未做 | #85 |
| #846 | `fix/deploy-help-fail-closed-0921` | 1（lessons） | — | 外审 300 s 空输出；无四叶 | #86 |
| #847 | `fix/briefing-consumption-qc-0921` | 1（lessons） | — | 复审三轮无可放行结论；live 验收等 #61 | #87 |

**已有工单、待派、无人做**：#62（#844 RAG readiness）、#66（#855 TTL 两道门，对 main 34 处冲突，需在新 main 重新前向）、#68（历史完成；`fix/history-completion-0922` 已推无 PR；#841 26 处冲突）、#73（`fix/re06-timer-scope-0923` 9 提交只在本机，K3 审查 BLOCKED_PROVIDER_TIMEOUT）。

**只在本机、无 PR 的其他分支**：`fix/react-trace-runtime-0921`（+3，09-21，归 #81 判定）；`docs/claim-scope-merge-65`（+7，疑被 #883 取代）；`docs/knevo-0917-absorb`（+1，疑被 #877 取代）；`docs/market-recovery-qc-0923` / `docs/runtime-postmerge-qc-0923`（各 +1，活会话的副产物）。

**其他观察**：#867 与自己的 base（`docs/closeout-workorders-0922`，协调者本地 +4 未推）冲突，归协调者；#799（docs，564 文件，仅 lessons 冲突）与 #77 批同类但未纳入本轮，待判定；`/private/tmp/fwp-qc-853-current` 与 `fwp-qc-857-current` 是 detached QC 树却各有 4 / 8 个未提交代码改动，来源未知，未动；主检出树 192 个改动是 L2 运营覆盖层，未动。

## 三、等用户决定的（不是无人，是停在拍板）

- #856（#60）合入与装机（活会话在跑门禁）。
- #861 + #871（#61）：五问 a–e + 三合同待拍；活会话在做 QC 修复。
- #868（#72）：合入确认。
- #874：活会话持有，其自述「不合并未授权的 #874」——用户本轮已给合并授权，但该会话看不到，需用户在那边说一句或由下一位 agent 接。
- #77 批（#853 / #857 / #804 / #807 / #836 / #840 / #849）：本轮由 Claude Code 代跑合并批，见第四节。

## 四、今日动作（Claude Code）

1. 关闭 7 张被接替 PR 并各贴接替指针（上表）；给 #838 贴「退回作者」评论（6330，三点：lessons 冲突 / 6 份死分支 inflight / 过期自述）。
2. 杀掉 7 个 09-21 起的 `pi-ttys*` tmux 僵尸会话（转录末条均为「Tool not found」，无子进程；转录文件保留可 `pi --session <id>` 续）。pid 13109（09-12，真实终端窗口）未动。
3. 写新工单 #81–#87 + INDEX 续表（本分支 `docs/orphan-workorders-0923`）。
4. 合并批：预览树 `/Users/a77/fwp-preview-batch-0923`，`gitea/main@b59d6eed0` 依序合 #853 → #857 → #804 → #840 → #849 → #836 → #807（#807 的 `.claude/lessons_learned.md` 用 `git merge-file --union`，0 冲突标记，654 行），预览 tip `88d31911b`，非文档改动 8 个文件（全部来自 #853 / #857）。四叶读数与逐张合入结果见本文件末尾「合并批收据」节（合入后补写）。

## 五、合并批收据

（执行后补写：每张 PR 的 `--record` JSON 路径、合前 `merge-tree`、合后 `git diff --name-only <before> gitea/main == PR 文件集` 核对。）
