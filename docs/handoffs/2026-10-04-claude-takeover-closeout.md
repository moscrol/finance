# 接手收口交接（2026-10-04，Claude 接手 codex → arena 的 harness 质量闭环）

## 背景（不读会误判后面的决定）

- **初衷**：让弱模型答得更准，让强模型在复杂题上有更大发挥空间。用户三次纠偏都在说同一件事：
  - `d0abda287494`（10-02）：改善任务、证据、工具、状态与错误反馈；不靠针对题型或坏例不断添加硬语义规则；
    权限、预算、协议、证据身份可以硬约束。
  - `f7ddbfc308ce`（10-02）：不要围绕单个题型反复加硬规则或补丁。
  - `65961f19bae1`（10-03）：下一片优先收敛职责、退出被替代的硬编码裁决，而非仅扩解释字段和叠加校验。
- **接手链**：codex 10-03～10-04 做发布与收口，交接在 `~/.finance-runtime/harness-quality-closeout-1003/HANDOFF-2026-10-04.md`；
  arena 接手后被用户停止；Claude 接手。Pi 仍在推 PR30（`feat/harness-integration-1003`），不在本轮范围内。
- **状态真本源**仍是任务板 FINANCEWORKS-1..13（`taskctl`；写操作要 `--thread-id`，本轮用 `claude-code:<会话id>` 署名）。
- **用户新决定**（原话）：「强模型的对照之前做过，就是react臂的对照，目前的话先不做，先用之前的。」
  对应 08-27 四臂对照 `~/.finance-runtime/four-arm-20260827/`。读数（machine-truth mean_rate）：unseen 集
  react-claude 0.857 vs 8792 0.567，seen 集 1.0 vs 0.721。引用边界：该对照模型与外壳同时变，只能当「强模型 + 薄循环」参照；
  D 组差距题已被后续修复调过，不再是留出题。FINANCEWORKS-5 已转 backlog。

## codex 收口质量（用户问的第一个问题，结论照录）

手法扎实：12 个已关 PR 全留接替指针或理由；1092 个分支引用逐条分类；拆树先 dry-run 后 apply，打钉、残留打包；汇报诚实，
没说「清零」，也明说未证明模型收益。

漏了五处，本轮已补或已列入下一步：

1. `/tmp` 里三份从未提交的 10-02 文档没保全，其中包括方向审查。已补，随本 PR 入仓。
2. 逐树去向缺失：codex 自己的规格要求「未知去向为零」，交接只点名约 5 棵。已补，见下表。
3. 19897 孤儿 sidecar 跑了 43 小时。已停。
4. 闲置门槛 2h→0 没写理由，另有嵌套树「被启动器引用」误报。误报写入下一步。
5. 5 条分支只存在本机 `.git`。本轮已备份 gitea。

## 按发现顺序做了什么

1. 保全 `/tmp` 文档 → `~/.finance-runtime/reviews/claude-takeover-20261004/tmp-salvage/`（MANIFEST.sha256），并随本 PR
   放回原定路径：
   - `docs/handoffs/2026-10-02-harness-direction-audit.md`：结论「局部偏离，最明显的是 #20 模型档位的前提与验收口径」；
     强侧空评测也 PASS；Episode 步数两档都是 6。
   - `docs/superpowers/plans/2026-10-02-harness-release.md`
   - `docs/verification/2026-10-02-harness-release-disposition.md`
2. 停孤儿 uvicorn 127.0.0.1:19897（PID 43897/43901/43911，PPID=1，10-02 20:21 起，cwd 在已合 PR24 的 /tmp 树）。
   停前快照 `orphan-19897-before.txt`；生产 8792 复核为 healthy@04799bc6f。
3. `finance-workspace-ffe1c60d84da` 上锁，理由带 `retain/保留`：生产 venv 是软链进这棵树的。
   `cleanup_gate_trees` 遇到含 retain/保留 的锁永不自动解。
4. 任务板记录用户决定，FINANCEWORKS-5 → backlog。
5. 读 arena 的首错诊断（`task6-first-error-20261004/`：首错都在第一个 model_turn，属推理越界），再用同一冻结源量化交付损失。
   19 份答卷里 7 份 unusable **全是交付失败**；12 条可追 run 中 10 条首个拒收是「一句一 claim」。
6. FINANCEWORKS-6 改向：先退出 harness 自己造成的交付损失。实现分支 `fix/material-claim-sentence-split-1004`
   （cf14e8498 + d940a287f，**PR #40**）。离线重放首稿结构合法 1/20 → 10/20，引用与私有 ID 反向对照照拒，变异 5/5；
   本机全量门禁 20400 passed / 0 failed（d940a287f，收据 `gate-Xb03H7Pu` 经 `check_test_receipt.py --require-full-scope` 判可采信）。
   证据 `docs/verification/2026-10-04-material-claim-sentence-split.md`（在该分支上）。
7. 发现 arena 停止前已提交 `cc1888e71`（`fix/material-financial-semantics-1004`，双远端），并开了 **PR #38**（open），新建两棵树，留下一个孤儿全量 pytest。
   该 pytest 跑完：20382 passed / 18 failed，18 条全在 `tests/test_pi_review_repair.py`，与其改动无关。同一批测试在本轮 PR #40 门禁里全绿，佐证是它在沙箱内跑的环境红。
8. 5 条只在本机的分支推到 gitea（不推 GitHub，GitHub 是公开仓）：`fix/8792-answer-review-0929`、
   `feat/harness-output-provenance-1003`、`feat/harness-plan-ownership-1002`、`fix/owner-output-contract-1002`、
   `fix/pr16-qc-1002`。收据 `gitea-backup.txt`，SHA 逐条一致。

## 决策与被否方案

| 决策点 | 方案 | 评价 | 结果 |
|---|---|---|---|
| FINANCEWORKS-6 下一步 | A. arena：6 条坏例归纳的财务口径不变量，同时进作者和判官提示（cc1888e71） | 坏例驱动；对所有材料题常驻（spec §5.2 要按需）；两个因素一起改；未在未调参题评测 | 不采用，分支保留待用户裁决 |
| | B. harness 切句：多句 claim 不再整稿退回 | 证据最硬（7/7 unusable 是交付失败；首拒 10/12）；属于退出硬编码裁决；对强弱模型都不加限制 | **采用** |
| | C. 只继续做内容首错诊断 | 不改东西就拿不到读数 | 后置：内容推理错另立因素，优先供给信息与工具 |
| 切句实现 | 先切再渲染 | 跨句 Markdown 强调被切成两段 | 否 |
| | 先渲染原文再切绑定 | 公开正文与作者一致，判官句与绑定同一函数切 | 采用 |
| | 反馈坐标用切片序号 | 引用错误不带原文，序号是作者唯一指针，会指向不存在的 `claims[1]` | 否，改为映射回作者序号 |
| | 同时放宽作者提示词 | 两个因素混在一起 | 否，提示词不动 |
| 本地独有分支 | 推 GitHub | 公开仓，内容未审 | 否 |
| | 推 gitea 备份 | 本机恢复点；可逆、无删除 | 采用 |
| 拆树 | 本轮直接回收可回收树 | 多棵属于 Codex 应用、Pi 或 arena；嵌套树还会被工具误报挡住 | 否：先出表，回收等用户点头，走 `worktree_closeout` dry-run → apply |
| 合入 / 部署 | 本轮合入 | AGENTS 要求合入 main 须用户确认 | 否：开 PR，等用户确认 |

## 逐树去向（基线 origin/main=ae02f420d，2026-10-04 16:25，共 36 棵）

c+ 指补丁不在 main 的提交数，「落地」指新增行在 main 的占比。板面原件
`~/.finance-runtime/reviews/claude-takeover-20261004/worktree-board-1625.json`。

**保留：生产、回滚、定时任务（7）**

| 树 | 去向与理由 |
|---|---|
| `~/finance-workspace-private` [main] | 不动：L2 运维叠层，48 个他人未提交代码改动，落后 main 218 提交 |
| `~/.finance-runtime/finance-workspace-04799bc6fb60` | 现役 8792 代码根 |
| `~/.finance-runtime/finance-workspace-ffe1c60d84da` | 现役 venv 来源，已上锁 retain |
| `~/.finance-runtime/finance-workspace-2c3949786568` | 已上锁（09-30 post988 切流快照），锁理由失效前不动 |
| `~/.finance-runtime/finance-workspace-40fd5a847c65` | 被 `~/.local/bin/start-finance-workbench-capability-sidecar` 引用；该启动器若已弃用，先改启动器再回收 |
| `~/.finance-runtime/finance-sync-7eec31b04b4b` | 夜跑 sync 代码根（launchd） |
| `~/.finance-runtime/finance-s7-sync` [spec/continuous-depth-gap-r1，c+3 仅 gitea] | 被 nightly-review-sync-staged 启动器引用 |

**在途或待裁决（5）**

| 树 | 去向与理由 |
|---|---|
| `~/fwp-wt-harness-integration-1003` [PR30 @bffc675da] | Pi 活动树，不碰 |
| `.claude/worktrees/kind-engelbart-aa727f` [fix/material-claim-sentence-split-1004] | 本轮代码分支，PR #40，待合入裁决 |
| `~/fwp-wt-takeover-closeout-1004` [docs/takeover-closeout-1004] | 本轮文档分支，PR #39 |
| `~/fwp-wt-material-financial-semantics-1004` [cc1888e71，双远端，PR #38] | arena 遗留，待用户裁决是否评测或关闭 |
| `~/.finance-runtime/reviews/harness-integration-20261003/gate-trees/mutation-fix` [c+2，双远端] | PR30 家族探针树，PR30 定案后回收 |

**内容已在 PR30 推送头（2）：PR30 定案后回收**

| 树 | 理由 |
|---|---|
| `~/fwp-wt-harness-output-provenance-1003` [c+14] | 新增行 99% 在 bffc675da；今日已备份 gitea |
| `~/fwp-wt-harness-plan-ownership-1002` [c+4] | 98% 在 bffc675da；今日已备份 gitea |

**可回收（19）：无独有内容，或独有内容已在远端**

| 树 | 理由 |
|---|---|
| `/private/tmp/harness-opt` [feat/harness-opt-1001 @19c820824，c+24，双远端] | #20 档位线未采用（PR16 关闭理由）；未提交文档已回收。**先拆其 tmp/ 下三棵嵌套树** |
| `/private/tmp/harness-opt/tmp/arena-harness-release-1002` | PR24 已合；孤儿服务已停 |
| `/private/tmp/harness-opt/tmp/harness-release-1002` | c+0；未跟踪文档已回收 |
| `/private/tmp/harness-opt/tmp/pr10-gates-1002` | PR15 由 #24 接替 |
| `/private/tmp/review-pr16-1002` [detached，c+27，双远端] | PR16 已关 |
| `~/fwp-wt-pr16-qc-1002` [c+32，73% 独有] | 在未采用的档位基座上；今日已备份 gitea。回收树、保留分支 |
| `~/fwp-wt-harness-simplification-1002` | PR23 经 #25 合入 |
| `~/fwp-wt-material-financial-baseline-1004` [detached@ae02] | arena 对照树，干净（10-04 16:00 新建，闲置门槛要等） |
| `~/.codex/worktrees/9020` [codex/memory-recall-audit-1004] | PR32 已合；先在 Codex 归档该线程 |
| `~/.codex/worktrees/{7d30,9c8d,cb6f,cf60}` [detached@3a2718c6c] | 干净，c+0；由 Codex 应用管理，宜在 Codex 侧清 |
| `~/.codex/worktrees/8792-quote-repair-review` [c+30，77% 在 main] | 今日已备份 gitea。回收树、保留分支 |
| `.worktrees/arena-8792-harness-takeover-0929` [c+30，84% 在 main，gitea] | 回收树、保留分支 |
| `.worktrees/capture-quotes-0929` | c+0 |
| `.claude/worktrees/blissful-noether-6da136` | c+0 |
| `.claude/worktrees/pi-session-cleanup-479dc5` | c+0 |
| `~/.finance-runtime/finance-workspace-45a7dcfc219f` | 旧生产快照，无启动器引用；回收前核部署账本是否仍列为回滚点 |

**去向待定（3）：含独有未合内容**

| 树 | 待定点 |
|---|---|
| `~/fwp-wt-owner-output-contract-1002` | 未合代码修复 4cba44a63（重复 direct-output 身份在 owner 执行前编译，+326 行，含 242 行测试），main 与 PR30 中都没有（2%）。今日已备份 gitea。要与 PR30 的 `output_requirement` 比对，看是否已被取代 |
| `~/.codex/worktrees/remote-sync-handoff-0930` [6 个文档提交，双远端] | 内容基本未进 main（dual-remote-collaboration.md 4/48 行）。判断是否已被 main 后续版本取代；树可回收，分支保留 |
| `.claude/worktrees/unclosed-session-stats-838ac4` [fix/main-gate-tmpdir-isolation，c+0] | 有未提交的 `tests/test_main_gate_receipt.py`（+22 行，09-30 09:59），归属不明。用 `worktree_closeout` 的 salvage 保全后回收 |

可回收树 dry-run（只读，未 apply）：点名 7 棵，无阻塞 2 棵（`fwp-wt-harness-simplification-1002`、`fwp-wt-pr16-qc-1002`）。另 5 棵 /tmp 树的唯一阻塞是启动器前缀误报：约 29 个 `com.a77.ima-*` launchd plist 引用目录 `/private/tmp`。收据 `~/.finance-runtime/reviews/claude-takeover-20261004/closeout/dry-20261004T163245.json`。

嵌套在主检出下的树（`.claude/worktrees/*`、`.worktrees/*`）目前也拆不动：`worktree_safety.context_blockers` 对启动器引用做路径前缀匹配，
主检出被引用，导致全部误标「被启动器引用」。09-25 只修了 `$HOME` 特例，见 `scripts/worktree_safety.py:229`。

## 验证与收据

- 收据根 `~/.finance-runtime/reviews/claude-takeover-20261004/`：`tmp-salvage/`、`orphan-19897-before.txt`、`taskboard/`
  （各条评论原文与回执）、`replay/`、`mutation/`、`gitea-backup.txt`、`worktree-board-1625.json`、`gate-d940a287f.log`。
- 代码分支全量门禁读数贴在其 PR 评论里（先提交交接再跑，读数不回写文档）。
- **不成立的结论**：离线重放只证明首稿结构合法；修复轮、判官与终局未重放；真实交付率、内容正确性与模型收益都没测。
  n=20 来自同一批冻结题，不能读成统计结论。

## 下一步

1. 用户确认后合入 PR #40（CI 通过为前提）；部署走切 8792 规程（`deploy-8792-switch-procedure`）。PR #39 为纯文档，可同批。
2. 预注册 GLM 同模型旧/新配对：未调参 holdout，主指标为交付率与硬错误。前置是标准 API 的运输与费用硬边界，
   Pi 记 `live_ready=false`，见 `~/.finance-runtime/reviews/harness-budgeted-preflight-20261004/forward-20261004T1256/workbench-preflight/admission-status.md`。
3. 下一个交付因素：输出 schema 违规（JSON 破损、字段类型、未知字段、历史摘录形状）在 20 份首稿中占 4 份。
4. 内容推理错（现金流口径、时点、未说明≠无影响）另立因素，优先供给信息与工具：确定性现金流桥接计算、按需方法资料。
   不加坏例硬规则。
5. 用户裁决 arena 的 PR #38（cc1888e71）：在 holdout 上评测，或留理由关闭。
6. 用户点头后，对无阻塞的 2 棵直接 apply（`worktree_closeout.py --apply --plan <上面的 dry 收据>`）。其余先修 `worktree_safety` 的祖先目录前缀误报（主检出、/private/tmp 两族），带变异测试，再重新 dry-run。

## 不要做

- 不在已看过答案的 20 份冻结题上调规则再拿同一批题宣称收益：它们已是回归集，不是留出集。
- 不把只在本机或 gitea 的分支推到 GitHub：公开仓，内容未审。
- 不拆 `ffe1c60d84da`：它是生产 venv 来源，已上锁。
- 不把「首稿结构合法 10/20」读成交付率或质量提升。
