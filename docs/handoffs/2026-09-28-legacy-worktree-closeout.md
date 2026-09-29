# 遗留 worktree 收口（2026-09-28）

## 授权与性质

- 用户原话（逐字）：「遗留的worktree，你按照最优方案去处理推进」。出处：Claude Code 桌面会话 `local_4ed0c651-5005-440c-9afc-c7f7d90a02ef`，2026-09-28 08:3x CST。上文把「46 条未合线逐条定去留、两个证据目录怎么处理、老生产版本要不要删」列为待用户定的事项。
- 性质：**Claude 受托代拍**，不是用户逐项拍板。每一项都可以被用户一句话推翻（走 `record-correction`，本文件写完不改）。
- 授权**不含**：合入 main、部署 / 换库、停任何在跑服务、归档别的会话、动别的会话在途分支。本文件所在 PR 的合入也留给用户。
- 执行收据（逐棵 JSON、补丁、残留包、脚本）：`~/.finance-runtime/reviews/legacy-worktree-closeout-20260928/`（`AUTHORIZATION.md`、`apply-*.json`、`plan.py`、`closeout.py`）。

## 结果

| | 之前（08:53） | 之后（09:00） |
|---|---:|---:|
| worktree | 87 | **23** |
| 数据卷可用 | 22 GiB（95%） | **35 GiB（92%）** |
| 本机独有提交（`rev-list --all` 减 Gitea 全部 sha） | 1（Codex Knevo 在途） | **0** |

分批看可用空间：快照与门禁树 +11 GiB，已落地与搁置线 +6 GiB，**取证树 −4 GiB**（原因见「取证树」一节的更正）。

拆 64 棵：过期快照 22、门禁 / 独审树 15、已落地线 17、搁置线 8、取证树 2。4 个有真实未提交内容的树先封存成 `salvage/*-20260928` 分支；全部 64 个 HEAD 钉到 `refs/archive/wt-20260928/<slug>`；以上都已推 Gitea。删本地分支 3 条（`git branch -d`，都是 `gitea/main` 的祖先）：`codex/8792-readiness-closeout-0928`、`fix/market-recovery-0921`、`fix/mootdx-history-0922`。其余分支一律保留。

## 判据（08:40 实测，`gitea/main` = `bdd19f4165ab`）

1. **备份**：逐棵 `rev-list <HEAD> --not <Gitea ls-remote 全部 sha>`。只有 `~/fwp-wt-knevo-cashflow-0927` 有 1 个未推提交（Codex 在途，树保留），另钉 `refs/archive/backup-20260928/docs-knevo-cashflow-0927` 推 Gitea。
2. **在用**：`lsof -d cwd` 只在主树、3 棵 Claude 会话树、8792（5a5e）、8796（40fd）、8816（`fwp-wt-finance-arena`）、8899（`fwp-wt-workbench-tech-premium`）。
3. **引用**：`~/Library/LaunchAgents/*.plist` 与 `~/.local/bin/*` 只引用 `finance-s7-sync`、`finance-sync-fe9fdbfd70a6`、40fd、7afe、`~/finance-workspace-sync`、主树、`~/finance-workspace-runtime`（→ 5a5e）。`FINANCE_GENERATION_CODE_ROOT` 缺省落到 `$CODE_ROOT`，所以 `finance-generation-*` / `finance-l2-*` 已不被引用。
4. **部署账本**（`~/.finance-runtime/deploy-ledger.jsonl`）：8792 依次 4f33 → 4c11 → 85bc → 7a40 → 326a →（回滚 7a40）→ 326a → 5a5e。回滚锚按 `2026-09-28-8792-interactive-readiness-closeout.md` 原文是 7a40。
5. **已落地**：未合分支按「新增非文档行在 `gitea/main` 同文件中逐字出现的比例」判。本仓的接替 PR 多是前向 / squash 合入，祖先关系判不出来。
6. 每棵拆之前复核：HEAD 未变、无进程 cwd、无启动器引用、盘点后无新文件、HEAD 全在 Gitea。

## 处置

规则：被跟踪文件的改动存 `<slug>.tracked.patch`；未跟踪与被忽略的非缓存文件打 `<slug>.residue.tar.gz` 并核文件数；有真实未提交内容（非缓存、非运行噪声、非禁提文件）的用临时索引封存成 `salvage/<slug>-20260928`；HEAD 钉 `refs/archive/wt-20260928/<slug>`（slug = 相对家目录的路径，去掉 `.finance-runtime/` 前缀，`/` 换 `--`）；锁树先 `unlock`；最后 `git worktree remove --force`。

### 过期快照 22

- 8792 旧版：326a、85bc、4c11、4f33、3396、3b7e。未上线候选：6d97、896b、98a7（裁决文件在 `reviews/8792-readiness-20260927/`）。
- 09-21 那一代：`finance-workspace-adcda94b5e40`（`intelligence/` 被部署脚本 rsync 改写过，与 HEAD 差 600 个文件；差异封存为 `salvage/finance-workspace-adcda94b5e40-20260928`）、`-recovery-20260921`、`finance-generation-`、`finance-l2-`、`finance-sync-adcda94b5e40`（2 个 eastmoney 同步改动封存为 `salvage/finance-sync-adcda94b5e40-20260928`）。
- 旁路：e480（8823）、ea42（19984）、`finance-readiness-d68913b27587`、`finance-readiness-sidecar-225a7af64`。
- 锁树 4 棵：`finance-nightly-installer-{0525e780e043,b59d6eed0356,f47d464eb7af}`、`finance-sync-2edbe4c46595`。锁理由是「留待授权部署」；09-25 #60 实装用的是 `79861f07e485`（安装源）与 `fe9fdbfd70a6`（运行根），这两棵保留，锁理由已失效的四棵拆。

### 门禁 / 独审树 15

`reviews/8792-readiness-20260927/` 下 9 棵（报告在同级目录）、eastmoney `qc-final`、RE06 `qc-k3-0{1,2,3}`、`pr910-911-qc-20260925-01/candidate`、`~/fwp-wt-market-recovery-qc-preview-0923`（锁理由「preserve tested revision d3abd670」，该修订已钉并推 Gitea）。

### 已落地线 17（内容 ≥90% 在 main 或已被合入的 PR 取代）

`codex/8792-readiness-closeout-0928`（已合入）、`baseline/pr868-{combined,current}-0925`（100% / 99%）、`fix/runtime-{contracts,authority-pc,evidence-probe}-0918`（DECISION-SHEET D1–D3，97%）、`feat/finance-query-technical-daily`（G4，96%；未提交的交接与测试改动封存为 `salvage/fwp-wt-technical-daily-20260928`）、`feat/e2-p6-conditioned-input`（E1，96%）、`baseline/history-evidence-qc-0921`（G8，随 #841，90%）、`fix/backfill-302132-scoped`（H9，#813 已合入并回填，99%）、`feat/instruction-migration-agents-md`（92%）、`fix/dated-recovery-{forward,inputs}-0925`（#913 → #940）、`fix/re06-closeout-forward-0924`、`docs/closeout-workorders-0922`（RE06 随 #942）、`docs/agent-foundation-deploy-0925`（#912 已关）、`feat/e2-material-contract-design`（E3，17 个文件中 16 个已在 main）。

### 搁置线 8（未落地；只拆检出，分支留在 Gitea）

没代拍「放弃」，也没代拍「合」。重启：`git worktree add <路径> <分支>`，前向到当时的 main，按 DECISION-SHEET（`~/.finance-runtime/reviews/pi-session-inventory-20260924/cleanup/DECISION-SHEET.md`）那一行的建议走。

| 分支 @ tip | 在 main 的比例 | 状态 / 重启条件 |
|---|---:|---|
| `fix/market-date-advisory-0921` @ `4a6e18da6` | 6% | A6：与 main #870 单源截止解析器语义级冲突；09-25 结论「以分支测试为规格在 main 上重做」 |
| `fix/research-contract-citations-0921` @ `5b2d1c488` | 2% | C2：同上，语义级冲突 |
| `feat/research-answer-preservation` @ `d064dee1c` | 22% | C3：留给 #76 L1；live 未过 |
| `fix/capability-wiring-closeout` @ `e8a63007b` | 3% | G3：#732 后两个修复（材料证据进账本、降级留痕），需前向 |
| `feat/e2-material-contract-impl` @ `8bd55b26c` | 82% | E2：余量等 QC R7 |
| `perf/wiki-hybrid-25s` @ `cd94a1db4` | 5% | H2：INDEX #22 RAG worker 常驻内存 |
| `codex/docs-historical-discovery-spec` @ `da254cd34` | 文档 | H6：设计稿，2 个文件不在 main |
| `docs/docs-batch-merge-0923` @ `729ac1d3e` | 文档 | H8：#77 判定表草稿；树里 2 份未提交文档封存为 `salvage/fwp-wt-docs-batch-0923-20260928` |

### 取证树 2（无损归档后拆）

| 原路径 | 新位置 |
|---|---|
| `~/fwp-wt-market-recovery-0921/tmp/recovery-20260921/`（424 个文件，3 份 DuckDB） | `~/.finance-runtime/evidence-archive/fwp-wt-market-recovery-0921/` |
| `~/fwp-wt-mootdx-history-0922/tmp/mootdx-unblock-20260922/`（47 个文件，2 份 DuckDB） | `~/.finance-runtime/evidence-archive/fwp-wt-mootdx-history-0922/` |

`MANIFEST.sha256` 记原始文件的 sha256（路径相对原树根）；DuckDB 各自一份 `zstd -12 --long=27`（3.45 GB → 约 1 GB，解压回读 sha256 一致）；其余文件 `residue.tar.gz`（逐个回读核过）。还原方法与全部指纹见该目录 `README.md`。

**更正：这一步没有省空间，反而多占约 4 GiB。** 按 `du` 算，原件 17.5 GB 变成 4.8 GB。但那 5 份 DuckDB 是 APFS 克隆（`cp -c` / `clone_to_staging` 一脉），物理块绝大部分与现存的生产库和 `db/*.bak-*` 共用。拆树实际只释放约 0.5 GiB，新写的压缩件却是 4.5 GiB 独占数据。已用排除法核实：批次期间没有别的大文件写入，交换文件也没有增长。长期差距不到 1 GiB：生产库轮换、备份删掉之后，原地的克隆也会逐渐独占约 3.9 GB（5 份两两 95–99.9% 块相同）。现在的形态是固定 4.5 GiB，且每份都能单独还原。以后要再省约 3.7 GiB，可以改成「1 份基准 + 4 份块差分」，代价是 5 份都依赖同一个基准。

引用旧路径的文档：`2026-09-22-market-recovery-input-contract.md`、`2026-09-22-market-recovery-field-contracts.md`、`2026-09-22-rag-readiness-live-resume.md`、`2026-09-23-disk-cleanup-and-burn-fix.md`、`docs/superpowers/specs/2026-09-22-push-unpushed-branches-and-finish-market-cutoff-tree-workorder.md`。它们写的 `tmp/recovery-20260921/…` 相对路径在 `residue.tar.gz` 里原样保留。

### 保留 23

| 树 | 为什么留 |
|---|---|
| 主树 `~/finance-workspace-private` | 生产数据根 + L2 运维叠层（242 个脏文件） |
| `.claude/worktrees/{nervous-lederberg-184f79,pi-session-cleanup-479dc5}` | 两个未归档 Claude 会话（「Fix LLM call hanging…」、「本地 Pi session 会话整理」）；归档要在各自会话里回「归档」 |
| `.claude/worktrees/unclosed-session-stats-838ac4` | 本会话 |
| `finance-workspace-5a5e4cbb671a` | 8792 当前生产 |
| `finance-workspace-7a405e1b096b` | 8792 回滚锚 |
| `finance-workspace-40fd5a847c65` | 8796 capability sidecar（launchd 在跑） |
| `finance-workspace-7afe37be1913` | `start-finance-workbench-numbackfill-canary` 引用 |
| `finance-sync-fe9fdbfd70a6`、`finance-s7-sync`、`finance-nightly-installer-79861f07e485` | 夜跑运行根、S7 根、现装安装源 |
| `~/finance-workspace-sync` | `daily-full-review-sync.plist` 注明「旧树及产物保留」 |
| FinArena 6 棵（`fwp-wt-finance-arena`、`arena-main-ready`、`arena-recovery`、`arena-recovery-gates`、`ownership-arena-gates`、`-v2`） | #82 用户原话「执行」：保留分支、原工作树和原件（`2026-09-23-finarena-archive-pointer.md`）；8816 在跑 |
| `fwp-wt-workbench-tech-premium` | 8899 预览在跑（H3：看过预览再定合 / 关） |
| Knevo 4 棵（`knevo-cashflow-0927`、`knevo-intake-0926`、`knevo-sample-0926a`、`knevo-intake-0924`） | Codex 在途 |

## 决策与被否方案

| 决策 | 选了 | 否了 | 为什么 |
|---|---|---|---|
| 未落地线 | 只拆检出，分支留 Gitea，重启入口写进本文件 | 代拍「放弃」关分支；代拍「合」 | 树只是检出，分支 + 本文件就能原样重启；去留是产品判断，受托也不该替用户放弃一条线 |
| 取证库 | 无损压缩 + sha256 回读 + 迁到 `evidence-archive/` | 原地保留；移入废纸篓；直接删 | 保留声明保护的是内容，不是路径；行情线已结案（#940 合入、09-26 换库、readiness 200）；废纸篓在清空前不释放空间，清空后证据就永久没了。**当时的前提「原地占 17.8 GB」是错的**，那是 `du` 读数，没算 APFS 克隆共享块，实际物理占用约 0.5 GiB（见「取证树」一节的更正）。按真实读数，原地保留短期更省；拆树换来的是取证件与生产库血统脱钩、占用固定可预期 |
| 5 份库的存放 | 各自独立压缩 | 1 份基准 + 4 份块差分（再省约 3.7 GiB） | 取证件要能用标准工具单份还原；差分需要自写的还原脚本，且 4 份都依赖同一基准。原地的克隆本来也共用物理块，所以相关失效不是新风险，决定性的是「标准格式、单份可还原」 |
| 锁树 | 锁理由已失效的解锁拆，写 retain 且仍在用的留 | 按锁一律留 | 四棵「留待授权部署」的锁在 09-25 #60 实装后已失效，实装用的是另外两棵，那两棵保留 |
| 未提交内容 | 临时索引封存到 `salvage/*` 并推送；补丁与残留包另存 | 只存补丁 | 补丁在树外、不在 git 里，下一任检索不到；封存分支可 `git log` / `diff` |
| 已合入分支 | 只删 3 条祖先关系成立的（`-d`） | `-D` 删内容已落地的 | `-D` 越过 git 自身的合并检查（钩子也拦）；那些分支已在 Gitea，留着无害 |

## 验证与收据

- 每棵拆前复核（见判据 6）；64 棵全部 `removed=true`（`apply-20260928T0853*.json`、`…T0854*`、`…T0856*`）。
- 取证库：5 份 `.zst` 解压回读 sha256 == 原件；两个 `residue.tar.gz` 逐个回读核过；`MANIFEST.sha256` 共 471 行。
- 备份：`git rev-list --all --not <Gitea 全部 sha>` = 0（推送 64 个钉、1 个 Knevo 备份钉、4 条 salvage 分支之后）。
- 封存分支禁提文件扫描：无 `.env*`、DuckDB、sqlite、`.DS_Store`、凭证配置。`finance-workspace-adcda94b5e40` 的封存里有一份 `feishu-bot.plist` 样板，只含 `cli_xxxxxxxxxxxx` 占位符。
- 没做：没有对本 PR 跑四叶（纯文档）；合入前按 AGENTS.md 补跑。

## 后续

- 用户：两个 Claude 会话要不要归档（归档后 app 清它们的树）；8899 预览（H3）合 / 关；FinArena 是否继续保留；搁置线 8 条去留。
- `~/.local/bin/start-finance-workbench-glm-canary` 引用 `finance-workspace-07af9160a677`，那棵树早已不在（启动器过期）；`numbackfill-canary` 仍钉 7afe（08-24 的快照）。两个 canary 启动器要不要退役，由用户定。
- `.git/config` 里 `fix/market-recovery-0921`、`fix/mootdx-history-0922` 两段 branch 配置因会话沙箱没删掉，无害。

## 不要做的

- 不要按 `du` 估本仓 DuckDB 拷贝的可回收空间，也不要为「省空间」把克隆一脉的库压缩成独立文件。`clone_to_staging` / `cp -c` 出来的库共用物理块，删掉只释放独占块，压缩件反而是新数据。先拆一小批，看 `df` 的实际变化再定。
- 不要把 `evidence-archive/` 里的库还原到 `db/` 或任何写入链的目标路径。它们是事故现场，不是备份。
- 不要为「清理」删 `refs/archive/wt-20260928/*` 或 `salvage/*-20260928`。收据与本文件按 SHA 引用它们，删了就无法复核。
- 不要按「分支是不是 main 的祖先」判一条线有没有落地。本轮 17 条已落地线里只有 1 条是祖先。
