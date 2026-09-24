# 2026-09-05 接手单 D：方法论回测 P1 第四刀收口（证伪库 / 归属字段 / 按阶段拆分）→ 开 PR → 合入 → 第五刀「按阶段基准率」

可独立分发。执行方无需读聊天记录，本单自带现状核实、证据路径、步骤、验收与红线。
接的是 2026-09-04 深夜中断的 Cursor session（用户最后一句口令：「合入，然后继续按照最优路径推进」）。
中断原因是 Cursor 模型不可用，上一轮 agent **最后一段动作没有留在转录里**，下面「现状」全部以 git / 收据文件 / stash 重新核实，不是转述。

> **派单口令（贴给新 agent）**：你是仓库 `/Users/a77/finance-workspace-private` 的执行 agent。读 `/Users/a77/fwp-wt-resume-specs-0905/docs/superpowers/specs/2026-09-05-resume-methodology-backtest-p1-fourth-cut-closeout.md` 全文并逐条执行；用户不在线，判断写进交接「决策与被否方案」；**合并 `main` 前必须拿到用户一句话确认**（本口令若含「合入」二字即视为确认第四刀 PR 的合并）。

## 1. 这条线是什么、停在哪

方法论回测（设计稿 `docs/superpowers/specs/2026-09-04-methodology-backtest-structured-history-design.md`，INDEX #21）已合四张 PR：P0 #573、P1 第一刀 #576（统计门）、第二刀 #581（`propose`）、第三刀 #585（个股标签，交接 `docs/handoffs/inflight/feat-methodology-backtest-p1-stock-labels.md`，顶部已回写「已合入」）。

**第四刀已写完、已本地提交、没推、没开 PR**：

| 项 | 值（2026-09-05 00:40 核实） |
|---|---|
| 树 / 分支 | `/Users/a77/fwp-wt-methodology-backtest-p1d` @ `feat/methodology-backtest-p1-refuted`，工作区干净 |
| 提交 | `e520e31e`（2026-09-04 23:06）`feat(methodology-backtest): P1 第四刀——规则归属 sharing/owner + 证伪库 methodology/refuted/ + 按大盘阶段拆分 + report --refuted`；12 文件 +546/−18，全部在 `intelligence/services/methodology_backtest/`、`intelligence/tests/test_methodology_backtest.py`、`scripts/methodology_backtest*.py`、`methodology/rules/*.json`、`docs/learning/ledger-map.md` |
| 基座 | `47a4fcde`（#585 回写后的 main）；现 `gitea/main`=`c6e702a6`，落后 21 个提交，**其中零个碰 `methodology_backtest` / `scripts/methodology_backtest.py` / `methodology/`**（`git log 47a4fcde..gitea/main -- <这些路径>` 为空） |
| 远端 | `git ls-remote --heads gitea feat/methodology-backtest-p1-refuted` 为空——**未 push** |
| 交接文档 | **在 stash 里**：`stash@{0}`「untracked files on feat/methodology-backtest-p1-refuted」= `docs/handoffs/inflight/feat-methodology-backtest-p1-refuted.md`（77 行，23:18 写成，门禁读数一行留白「见本文末」）。stash 是整个仓共享的，`git stash list` 在任何一棵树都能看到，**只能在 p1d 树、停在该分支时 `git stash pop`** |
| 全量门禁 | `~/.finance-runtime/test-receipts/20260904T153125Z-e520e31e.json`：**7719 passed / 2 failed / 15 skipped**，exit 1，`dirty=false`。红的两条：`intelligence/tests/test_conversation_orchestrator.py::test_ask_watchdog_returns_partial_and_suppresses_late_progress`、`intelligence/tests/test_workbench_conversation_integration.py::test_skill_timeout_degrades_one_module_and_continues`——都是看门狗 / 超时时序测试，与本刀 diff 无交集；同一时段（23:24–23:37）本机有**三个全量门禁并行**（另两个是 `bf7a8f4a` 7710P/0F 与 `892a6ec2` 7714P/1F），swap 20/21 GB。**红是负载抖动的嫌疑很大，但按合并纪律「红不合」，必须重跑拿绿收据，不能拿嫌疑当结论** |
| INDEX | `docs/superpowers/specs/2026-09-01-workorders-INDEX.md` #21 行已写「⏳ P1 第四刀在途（`e520e31e`，未开 PR）」（`gitea/main@c6e702a6`），开 PR / 合入后要改 |
| 跨线依赖 | 工单 #25（历史重放引擎）的 schema 步骤**等本刀合入后再做**（#25 §1「不做 `sharing / owner / source_perspective`」、§4 最后一行）。本刀合入越早，#25 越不用绕 |

第四刀做了什么（抄 stash 里的交接，合入前以它为准）：

1. 规则归属层：`sharing ∈ {shared, private}` + `owner` **必填、无默认**（shared → `owner=system` + 可选 `source_perspective`；private → 用户 id）；四条种子规则显式标 `shared / system / 来源`；`propose` 默认 private、`--sharing shared` 时 owner 恒 system。
2. 按大盘阶段拆分：runner 把已到期事件按事件日 `market_stage` 拆桶（n / k / p）进收据 `by_market_stage` 与 md 表；**只作读数拆分，不参与四态**。
3. 证伪库：结论 `refuted` 的收据另落 `methodology/refuted/<rule_id>@v<version>/<date>.json`（schema `methodology-backtest-refuted/v0`，**进 git**）；scan 模式以 BH 校正后结论为准；CLI `run/scan --refuted-dir`、`report --refuted`；台账地图新行。
4. selftest 18 → 19；`test_methodology_backtest.py` 48 → 61；ruff 0；pre-commit 10 道全过。真库四条种子规则整体读数与 #585 逐位相同，证伪库为空；按阶段拆分的读数表在交接里（例：`diff_ratio_turn_up_5d` 主升阶段 71.7% vs 顶部横盘 22.1%）。

## 2. 目标（可验收）

1. 第四刀以**绿门禁**开出 PR：分支尖 = `e520e31e` 之上「合 `gitea/main` 的合并提交 + 交接文档提交」；PR 正文含真库读数、决策与被否方案、门禁收据路径。
2. 用户确认后合入；主树 `git pull --ff-only gitea main`；交接顶部回写「已合入」；INDEX #21 行「第四刀在途」→「已合（PR #N）」；记忆库项目笔记加一条交接记录。
3. 第五刀立项并开工（不要求本单做完）：**按阶段基准率**——`baseline.kind = same_stage_days`（universe 里同阶段日子的 success 比例）作为第三列对照，让「这个阶段这招不灵」从描述性读数升为四态；分支 `feat/methodology-backtest-p1-stage-baseline`，从合入后的 `gitea/main` 新开树。

## 3. 非目标（写死认领）

- ❌ `lifecycle_stage` 标签：卡在人工标注集（需用户给 30–50 条 `(题材, 日期, 阶段)`，五段各 ≥ 6 条），见 #585 交接「下一步 2」。不要占空标签位。
- ❌ 归一 `market_stage` 的「XX阶段 / XX」两套写法（P0 决定直接投影；归一要升 `LABEL_VERSION` 且影响所有用 `market_stage` 的规则）。
- ❌ 渲染层合规硬门（仅登录可见 / 必带 N 与区间 / 实体粒度到板块题材 / KOL 匿名化 / `entity_type=stock` 共享规则禁渲染）——P2。
- ❌ 让经验卡统计门（`experience_cards.gate_promotion`）读证伪库——交接「已知边界」记了两处将来可能不一致，先记不改。
- ❌ 碰工单 #24 / #25 的任何文件；#25 的 schema 加法由 #25 的执行者在本刀合入后自己做。
- ❌ 为了让门禁绿而改、跳过、`xfail` 那两条时序测试。红就是红，先查是不是负载，再决定。

## 4. 证据路径表（先读这些，禁止臆测）

| 文件 / 命令 | 看什么 |
|---|---|
| `git -C /Users/a77/fwp-wt-methodology-backtest-p1d status --short && git -C ... log --oneline -3 && git -C ... stash list` | 树干净、HEAD `e520e31e`、stash 还在 |
| `git -C /Users/a77/fwp-wt-methodology-backtest-p1d show stash@{0}^3:docs/handoffs/inflight/feat-methodology-backtest-p1-refuted.md` | 先读 stash 里的交接全文（不 pop 也能读）；这是本刀的「分支做什么 / 决策与被否方案 / 已验证 / 未验证 / 下一步」 |
| `git -C /Users/a77/fwp-wt-methodology-backtest-p1d show --stat HEAD` | 12 个文件；确认没有 `*.duckdb` / 台账 / 收据被提交（`methodology/receipts/` 应仍在 gitignore；`methodology/refuted/` 目录当前不存在，因为四条种子规则无一被证伪） |
| `python3 -c "import json;d=json.load(open('/Users/a77/.finance-runtime/test-receipts/20260904T153125Z-e520e31e.json'));print(d['counts'],d['failed_ids'])"` | 上次门禁的两条红 |
| `docs/handoffs/inflight/feat-methodology-backtest-p1-stock-labels.md` | 上一刀交接：真库读数表格式、「下一步」、「踩过的坑」（门禁要干净树、conftest 写共享 `latest.json`） |
| `docs/handoffs/inflight/feat-methodology-backtest-p1-propose.md` `feat-methodology-backtest-p1-gate.md` `feat-methodology-backtest-p0.md` | 本线交接体例（顶部回写「已合入」的写法照抄） |
| `docs/superpowers/specs/2026-09-04-methodology-backtest-structured-history-design.md` §6「以下三条是 2026-09-04 BP v0.4 壁垒重构后补入的产品约束」、§10.4 | 第四刀对应的设计稿条目；第五刀「按阶段基准率」在 §3.2「同 universe」延伸 |
| `intelligence/services/methodology_backtest/runner.py`（`e520e31e` 上）`by_market_stage` 拆桶处、`stats.py` 基准率函数、`receipts.py::build_receipt` `baseline_alt` 字段 | 第五刀落点：`baseline_alt` 已是「事件日配对基准率」的第二列，第三列 `same_stage_days` 照它的形状加 |
| `scripts/methodology_backtest_selftest.py` | 19 项自测；第五刀加「各阶段基准率 n 之和 = universe 日数」一项 |
| `scripts/run_main_gate.sh`、`scripts/check_test_receipt.py`、`test-environment.json` | 门禁要干净树；收据按 `<stamp>-<rev8>.json` 找，不看 `latest.json` |
| `scripts/gitea_pr.py --help` | `conflict-check / open / merge`；无 comment 子命令 |
| `docs/superpowers/specs/2026-09-01-workorders-INDEX.md` #21 行（在 `gitea/main`，主树 `ba0393d1` 上没有这版，先 ff 主树或到新树读） | 要改的那句 |
| `/Users/a77/agent-memory/20_projects/finance-workspace-private.md` 「交接记录」段 | 记忆回写体例（`- 2026-09-05 · cursor · **…**。…` 一行一条） |

## 5. 步骤 + 验收

### 步骤

1. 开工三连（主树）`cd /Users/a77/finance-workspace-private && git status --short && git branch --show-current && git worktree list`。主树若有他人足迹不管它，本单全程在 p1d 树里干活；主树只在合入后 `git pull --ff-only gitea main`。
2. p1d 树：`git -C /Users/a77/fwp-wt-methodology-backtest-p1d status --short`（应为空）→ `git stash list` → **`cd /Users/a77/fwp-wt-methodology-backtest-p1d && git stash pop`** → 交接文档回到工作区（untracked）。读全文。
3. 合基线：`git fetch gitea --quiet && git merge --no-edit gitea/main`（预期无冲突；若有，只可能在 `docs/learning/ledger-map.md` 或 INDEX，手工解）。合并后 `git status --short` 只剩那份 untracked 交接。
4. 等机器安静再测：`ps -eo command | rg -c 'python -m pytest|Python -m pytest'` 非 0 就 `sleep 30` 再查（最多 30 分钟）。先定向：`.venv-workbench/bin/python -m pytest -q -p no:cacheprovider intelligence/tests/test_methodology_backtest.py intelligence/tests/test_experience_cards.py`（预期 61 + 19 绿），`python scripts/methodology_backtest_selftest.py`（19/19），再把两条红**单独跑 3 次**：`-k "test_ask_watchdog_returns_partial_and_suppresses_late_progress or test_skill_timeout_degrades_one_module_and_continues"`。三次全绿 → 负载抖动成立，记进交接「踩过的坑」；任一次红 → 停，把失败输出原样贴进交接「未验证」，向用户报告，不合。
5. 全量门禁（干净树：先把交接文档 `git add -- docs/handoffs/inflight/feat-methodology-backtest-p1-refuted.md && git commit -m "docs(handoff): 方法论回测 P1 第四刀在途交接" -- docs/handoffs/inflight/feat-methodology-backtest-p1-refuted.md`，门禁读数之后再补一个 docs 提交）：确认无其他 pytest 后 `bash scripts/run_main_gate.sh`；收据取 `ls -t ~/.finance-runtime/test-receipts/ | rg "$(git rev-parse --short=8 HEAD)"`，跑 `python scripts/check_test_receipt.py <该文件> --expect-revision "$(git rev-parse HEAD)"`。**0 failed 才继续**。
6. 交接补门禁读数与收据路径（照 #585 交接「已验证」最后两条的写法），提交 `docs(handoff): …补全量门禁读数`（pathspec）。`git push -u gitea feat/methodology-backtest-p1-refuted`。主树下 `python3 scripts/gitea_pr.py conflict-check --head feat/methodology-backtest-p1-refuted --base gitea/main` clean 后 `python3 scripts/gitea_pr.py open --head feat/methodology-backtest-p1-refuted --base main --title "feat(methodology-backtest): P1 第四刀——规则归属 sharing/owner + 证伪库 methodology/refuted/ + 按大盘阶段拆分 + report --refuted" --body-file <PR 正文 md>`。PR 正文照 #585 的结构（做什么 / 关键决策 / 真库读数 / 验证 / 未做）。
7. 合并：用户已在 09-04 说「合入，然后继续按照最优路径推进」，但那句针对的是 #585；**本刀合并要派单口令里有「合入」或用户当场一句确认**。有 → `python3 scripts/gitea_pr.py merge <N> --yes` → 主树 `git pull --ff-only gitea main` → 交接顶部加「已合入（PR #N，`gitea/main@<sha>`）」→ INDEX #21 行改「✅ P1 第四刀已合（PR #N）」→ 这两处是小文档修补，可直接在主树 `main` 上 pathspec 提交并 `git push gitea main`（#585 回写 `47a4fcde` 就是这么做的）。没有 → 停在 PR 打开状态，报告。
8. 记忆回写：`/Users/a77/agent-memory/20_projects/finance-workspace-private.md` 「交接记录」加一条（第四刀合入 / 门禁读数 / 三个门禁并行导致假红的教训 / 第五刀分支名），`git -C /Users/a77/agent-memory commit -- 20_projects/finance-workspace-private.md && git -C /Users/a77/agent-memory push gitea main`（该仓 `main` 直接推是惯例）。
9. 第五刀开工（合入后）：`git worktree add /Users/a77/fwp-wt-methodology-backtest-p1e -b feat/methodology-backtest-p1-stage-baseline gitea/main`。形态写死：`stats.py` 加 `same_stage_baseline(...)`：对每个 `market_stage` 值，p0_stage = universe 内该阶段日子的 success 比例（与 `baseline` 同一 success 定义、同一 universe、同一窗口）；`runner.py` 把它算进 `by_market_stage[stage].p0 / lift / wilson`；`receipts.py` 收据字段 `by_market_stage[*]` 加 `p0 / lift / verdict`（**阶段级四态只在 n ≥ `min_n` 时给**，否则 `insufficient`）；`report --refuted` 与 md 表加列；selftest 加「各阶段 n 之和 = N、各阶段 baseline_n 之和 = universe 日数」；测试用 mini 库精确断言。变异测试：把阶段基准率的阶段过滤条件去掉（退化成整体 p0）→ 「阶段 p0 各不相同」的断言必须变红。真库跑四条种子规则，把「主升 vs 顶部横盘」的阶段级四态写进交接。开 PR、不合。

### 验收

- [ ] `git stash list` 为空；p1d 树 HEAD 含 `e520e31e` 且合入了 `gitea/main`；交接文档在 git 里。
- [ ] 全量门禁收据 `<stamp>-<rev8>.json` 与分支尖一致，`counts.failed == 0`，`check_test_receipt.py` 退出码 0；两条时序测试单独 3/3 绿的记录在交接「踩过的坑」。
- [ ] `python scripts/methodology_backtest_selftest.py` 19/19；`test_methodology_backtest.py` 61 绿；`ruff check .` 0；`python scripts/layer_audit.py`、`python scripts/check_unread_fields.py` 无新增。
- [ ] 真库 `scripts/methodology_backtest.py scan --rules-dir methodology/rules --labels-db /Users/a77/finance-workspace-private/db/history_labels.duckdb` 四条读数与 #585 交接逐位相同；`report --refuted` 输出「证伪库为空」；`methodology/refuted/` 未被创建；主库 mtime / 体积不变。
- [ ] PR 已开且 `conflict-check` clean；合入（若被授权）后主树 `git log --oneline -1` == `gitea/main`，交接顶部与 INDEX #21 行已回写并推到 `gitea/main`。
- [ ] 记忆库有本轮条目。
- [ ] 第五刀树与分支存在，至少有「stats 函数 + 测试」一个提交；未合。

## 6. 红线（抄 AGENTS.md，不新发明）

- 开工先 `git status --short && git branch --show-current && git worktree list`；主树有他人足迹**不在主树动手**。
- 🚫 禁 `git add -A` / `git add .`；一律 `git commit -- <明确文件列表>`；不强推；**合并 `main` 必须等用户确认**。
- 🚫 禁提交 `*.duckdb` / `methodology/receipts/` 本机收据 / `*.jsonl` 用户台账 / `.env*` / `.DS_Store`；`methodology/refuted/` 条目是设计上要进 git 的（本刀真库为空，不会产生）。
- 解释器只用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`；主库 `db/market_feature_store.duckdb` 与旁路库 `db/history_labels.duckdb` 全程 `read_only=True`（`scan` 会写 `methodology/receipts/`，那是 gitignore 的本机产物，允许）。
- 门禁纪律：任何 pytest 前先确认本机没有别的 pytest 在跑；全量门禁只在最后跑；不用 `-n auto`；不看 `latest.json`。**红门禁不合**。
- 本机 16 GB、swap 常年接近满：不起第二个 bge-m3、不跑前端 `pnpm build`（本刀前端零改动，交接写明）。
- 用户纠偏必落 correction（`python3 -m intelligence.cli record-correction ...`）。

## 7. 成立条件

- 现状读于 2026-09-05 00:30–00:45（`gitea/main@c6e702a6`）；若 `gitea/main` 又动了，以 `git log 47a4fcde..gitea/main -- intelligence/services/methodology_backtest scripts/methodology_backtest.py methodology/` 重看有没有人碰了本刀的文件。
- 门禁读数只对「干净树 + 该 revision + 本机无其他 pytest」成立。
- stash 只有一份（`stash@{0}`），若 `git stash list` 多于一条，先看每条的分支名再 pop，不要 `git stash clear`。

## 8. 最终回复给派单人（简明，中文）

PR URL 与号；分支尖 SHA；两条时序测试单独重跑结果；全量门禁读数（passed/failed/skipped、收据路径、`check_test_receipt.py` 退出码）；是否已合入（若合，`gitea/main` 新 SHA、INDEX / 交接 / 记忆三处回写的提交号）；第五刀分支名、树路径、已提交内容与真库阶段级读数摘要；未做与原因。

## 9. 可迁移知识点（教学备注）

- **并行门禁会互相制造假红**：三个全量 pytest 在 16 GB、swap 满的机器上同时跑，时序类测试（看门狗、超时、进程组关停）最先倒。「红不合」的纪律没错，但归因要分「代码红」还是「环境红」——判据是**隔离重跑 + 干净时段重跑**都绿，且失败用例与 diff 零交集。这在 CI 上叫 flaky test 隔离，和数据库测试里「共享 fixture 竞态」是同一形状。
- **stash 是仓级不是树级**：多 worktree 共享一个 `.git`，`git stash` 在任何一棵树都可见、可 pop；pop 到错的分支会把文件放错地方。习惯上宁可提交一个 `docs(wip)` 也别 stash 交接文档。
- **读数拆分 ≠ 结论拆分**：第四刀按阶段拆 n/k/p 但不给阶段级四态，因为 p0 是整体基准；第五刀补阶段级基准率后才能给。这是「每一个结论都要有它自己的基准」——A/B 实验里按 segment 看效果也必须按 segment 算对照组，不能拿总体对照组比。
