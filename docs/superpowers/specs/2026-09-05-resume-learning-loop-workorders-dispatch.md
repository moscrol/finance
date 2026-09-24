# 2026-09-05 接手单 A：学习闭环工单线——#584 已合，派发并收口 #23（判官 token）/ #24（可证伪点 `rule_id` + 偏差目录）/ #25（历史重放引擎）

可独立分发。执行方无需读聊天记录，本单自带现状核实、证据路径、步骤、验收与红线，**附录 A/B/C 是三张工单各自的完整派单口令**（上一轮协调 agent 写好并已派过一次，原文照录，只改了「树已存在」这一处事实）。
接的是 2026-09-04 深夜中断的 Cursor session（分支 `docs/finance-agent-bp`，用户最后一句口令：「合并，然后推进」）。「合并」已做（PR #584 → `gitea/main@c6e702a6`）；「推进」= 派 #23/#24/#25，三个子 agent 刚建好树、读完证据就被 Cursor 模型不可用一起打断，**零改动**。

> **派单口令（贴给新 agent）**：你是仓库 `/Users/a77/finance-workspace-private` 的协调 agent。读 `/Users/a77/fwp-wt-resume-specs-0905/docs/superpowers/specs/2026-09-05-resume-learning-loop-workorders-dispatch.md` 全文并执行 §5；三张工单用附录 A/B/C 的口令各派一个子 agent（或告诉派单人分三个 session 贴）。用户不在线；**任何 PR 合并 `main` 都要用户一句话**。

## 1. 这条线是什么、停在哪

BP 线（`docs/bp/2026-09-finance-agent-bp.md` v0.5 + 设计稿 `docs/superpowers/specs/2026-09-04-methodology-backtest-structured-history-design.md` §10「学习闭环路线图」）把用户 09-04 晚的六句理念对到仓内实物，立了三张可独立分发的工单并登记 INDEX：

| # | 工单 | 一句话 | 量级 | 分支 / 树（**已建、干净、0 提交、基线 `c6e702a6`**） |
|---|---|---|---|---|
| 23 | `docs/superpowers/specs/2026-09-04-judge-token-usage-workorder.md` | 判官侧 token 用量记进 `LLMCallLedger`（API 读 usage / grok CLI 先探明）+ `metrics.judge_usage` + `intelligence/eval/research_cost.py` 出「写手 / 判官 / 合计」元/次报表；产出回填 BP §7.3 `【待填：Alpha 期含判官的全口径实测】` | 小单，半天到一天 | `feat/judge-token-usage` / `/Users/a77/fwp-wt-judge-token-usage` |
| 24 | `docs/superpowers/specs/2026-09-04-checkpoint-rule-id-bias-catalog-workorder.md` | 可证伪点台账加 `rule_id / rule_verdict / rule_receipt`（读者 `calibrate.by_rule` + `render_report`），`checkpoint register --rule-id` 回显规则四态不拦截；新模块 `checkpoint_bias.py` 偏差目录 v1 四条 + `bias-scan` | 一到两天 | `feat/checkpoint-rule-id-bias` / `/Users/a77/fwp-wt-checkpoint-bias` |
| 25 | `docs/superpowers/specs/2026-09-04-historical-replay-engine-workorder.md` | 历史重放引擎 `intelligence/eval/replay_engine.py`：两臂（命名 / 匿名）× 两车道（A 规则复现一致率，B 双盲格式前瞻假设）→ 自动判分 → 复用 `calibrate` 出 `pit_grade × memory_bucket × arm × category × horizon` 分格 → 与双盲台账对账；`model_cutoffs.json`；规则 schema 两加法 | 中单，三到五天；**真钱**：约 160–200 次 LLM 调用 | `feat/historical-replay-engine` / `/Users/a77/fwp-wt-replay-engine` |

现状（2026-09-05 00:40 核实）：

- `gitea/main@c6e702a6` = PR #584 合并提交，含三张工单、INDEX #23/#24/#25 三行「⏳ 待派」、设计稿 §10、BP v0.5、交接 `docs/handoffs/inflight/docs-finance-agent-bp.md`（第九轮）。
- 主树 `/Users/a77/finance-workspace-private` 在 `main@ba0393d1`，干净，**落后 `gitea/main` 14 个纯文档提交**（全是 #584 那条分支）——可 `git pull --ff-only gitea main`。
- 三棵工单树都存在、干净、HEAD = `c6e702a6`、对 `gitea/main` 0 落后、**无任何提交**；三个子 agent 只做了只读探索（读 AGENTS.md、工单、证据路径表），没写一个字，没建 `~/.finance-runtime/judge-usage-probe-*`。
- `docs/finance-agent-bp` 分支已合并，Gitea 已删远端；树 `/Users/a77/fwp-wt-finance-agent-bp` 停在 detached `c6e702a6`，可 `git worktree remove`。
- **跨线依赖**：#25 §1 写死「不做 `sharing / owner / source_perspective`——由在途分支 `feat/methodology-backtest-p1-refuted`（P1 第四刀，树 `fwp-wt-methodology-backtest-p1d`，`e520e31e`）实现；本单 schema 加法必须在第四刀合入后 rebase 再做」。第四刀的收口是**另一张接手单 D**（`2026-09-05-resume-methodology-backtest-p1-fourth-cut-closeout.md`）；派 #25 前先看 `git log gitea/main..feat/methodology-backtest-p1-refuted --oneline` 它合没合——没合也能派，#25 的口令里已写了顺序约束（schema 步骤放最后、做前再 fetch）。
- **资源**：本机 16 GB、swap 常年 20/21 GB，09-04 23:24–23:37 三个全量门禁并行直接把两条时序测试跑红（见接手单 D / B）。三张单并行时，pytest 必须串行（口令里有「任何 pytest 前先 `ps -eo command | rg -c 'python -m pytest'` 为 0」）；**#25 的 LLM 真跑与另两单的全量门禁不要撞同一小时**。

## 2. 目标（可验收）

1. 主树 ff 到 `gitea/main`；三棵工单树核实干净且与 `gitea/main` 同步（若 `gitea/main` 又动了：`git -C <树> merge --ff-only gitea/main`）。
2. 三张单各派一个执行 agent（附录 A/B/C 口令原文），#23 与 #24 可立即并行；#25 在确认 LLM 预算窗口后派（口令里已含 `--dry-run` 先行、`--max-calls 200`、被预算闸拒就停）。
3. 收口：每张单的 PR 到来后，协调者做**独立验收**——`gitea_pr.py conflict-check` clean；收据 `<stamp>-<rev8>.json` 与分支尖一致且 `counts.failed==0`、`python scripts/check_test_receipt.py <file> --expect-revision <sha>` 退出码 0；`python scripts/layer_audit.py` / `python scripts/check_unread_fields.py` 无新增；工单验收清单逐条对 ✅/❌；交接文件与 INDEX 行已改。验收结论连同「等用户一句合并」报给派单人。
4. 合入后的回写：INDEX 行「⏳ 待派」→ 已合一句话；`docs/handoffs/inflight/docs-finance-agent-bp.md`「下一步」划掉对应项；**#23 合入后**把报表对现有 run 目录的输出摘要回填 BP §7.3 的 `【待填：Alpha 期含判官的全口径实测】`（BP 是对外文档，只写核过的数字，未积累 ≥ 20 个新 run 之前写「机制已上线，样本积累中」而不是编数）；记忆库 `/Users/a77/agent-memory/20_projects/finance-workspace-private.md` 加交接记录。
5. 顺手小修（合并后、纯文档、直接主树 `main` pathspec 提交）：`CLAUDE.md` 的「12 个工具」「31 个技能」两处过期数字按 `python3 scripts/code_map.py` / 工具注册表 / `ls skills` 实数改（交接「下一步」最后一条）。

## 3. 非目标（写死认领）

- ❌ 协调者自己实施三张工单的任何一行代码——工单内容由各执行 agent 做；协调者只派、验、报、回写。
- ❌ 改三张工单正文或 INDEX 号（下一空号 #26 留给别的单）。
- ❌ 替用户合并任何 PR；替用户决定 #25 的预算窗口（口令里的 200 次上限是工单红线，不是授权）。
- ❌ 方法论回测第四刀的收口（接手单 D）、RAG 瘦身（接手单 B）、knowhow recipes（接手单 C）。
- ❌ BP 附录 C 的用户占位（注册状态 / 体验链接 / 录屏 / 产品名 / 创始人 / 收入支出 / 工位 / 数据商报价 / 入口现状）——用户填。
- ❌ 切 8792（三张单全是 services / eval / CLI 层，无运行时行为变化；#23 的 `metrics.judge_usage` 要等下次切换才进生产，交接写明即可）。

## 4. 证据路径表（先读这些，禁止臆测）

| 文件 / 命令 | 看什么 |
|---|---|
| `cd /Users/a77/finance-workspace-private && git fetch gitea --quiet && git log --oneline ba0393d1..gitea/main` | 主树落后的 14 个提交全是 `docs/finance-agent-bp` 的——ff 安全 |
| `for w in fwp-wt-judge-token-usage fwp-wt-checkpoint-bias fwp-wt-replay-engine; do git -C /Users/a77/$w status --short \| wc -l; git -C /Users/a77/$w log --oneline -1; git -C /Users/a77/$w log --oneline HEAD..gitea/main \| wc -l; done` | 三棵树干净 / HEAD / 落后数（现 0 / c6e702a6 / 0） |
| `docs/superpowers/specs/2026-09-01-workorders-INDEX.md` #21 / #23 / #24 / #25 行（在 `gitea/main`；主树 ff 之后才有） | 三行「⏳ 待派」的原文；#21 行「第四刀在途」是 #25 的前置 |
| 三张工单全文（§1 形态决策、§2 目标、§3 非目标、§5 验收、§6 红线） | 验收时逐条对 |
| `docs/handoffs/inflight/docs-finance-agent-bp.md`「第九轮」「下一步」「未验证 / 已知边界」 | 三张单是怎么立的、行号只对 `gitea/main@5c7fe2eb` 复核过（第四刀合入后会漂，工单里已写「以 `rg` 为准」） |
| `docs/superpowers/specs/2026-09-04-methodology-backtest-structured-history-design.md` §10.2 四条守门、§10.3 顺序、§10.4 分期表 | #24 / #25 在闭环里的位置；验收时对「理性 / 非理性按过程定义」「发现只出规则 JSON」「模型记忆泄漏分栏」三条守门 |
| `docs/bp/2026-09-finance-agent-bp.md` §7.3（`rg -n "待填：Alpha 期含判官"`）、附录 D | #23 合入后要回填的位置；附录 D 已写「对外版不得写『AI 已学会回顾历史』」——#25 的读数只能按 `pit_grade / memory_bucket` 分开引用 |
| `git log gitea/main..feat/methodology-backtest-p1-refuted --oneline`；`/Users/a77/fwp-wt-methodology-backtest-p1d` | #25 schema 步骤的前置合没合 |
| `scripts/gitea_pr.py --help`、`scripts/check_test_receipt.py`、`scripts/layer_audit.py`、`scripts/check_unread_fields.py`、`docs/workflows/acceptance-workflow.md` §2「逐张验收」 | 独立验收的工具与规程（本线不切 8792，只用 §2 / §3） |
| `/Users/a77/agent-memory/20_projects/finance-workspace-private.md` `rg -n "BP\|工单 #2[345]\|学习闭环"` | 记忆体例 |
| `CLAUDE.md` `rg -n "12 个工具\|31 个技能"`；工具注册表与 `skills/` 目录 | 小修的对象与实数来源（AGENTS.md「问有多少能力时点名分母」） |

## 5. 步骤 + 验收

### 步骤

1. 开工三连 `cd /Users/a77/finance-workspace-private && git status --short && git branch --show-current && git worktree list`；主树干净则 `git pull --ff-only gitea main`（只 ff）；有他人足迹就不 pull、记进回复。
2. 三棵树核实（证据表第二行命令）；有落后就 `git -C <树> merge --ff-only gitea/main`；`git worktree remove /Users/a77/fwp-wt-finance-agent-bp`（已合并的 detached 树）。
3. 派单顺序：先 #23 与 #24（附录 A、B 口令，原文贴给两个子 agent / 两个 session）；再看第四刀状态与派单人是否确认 LLM 预算窗口，派 #25（附录 C）。口令里「基线应为 `gitea/main` = `c6e702a6`（若已更新以当时最新为准）」保持；「先 `git worktree add …`」那句**已由上一轮做完**——子 agent 若发现树已存在，直接进树、`git status --short` 确认干净、`git log -1` 确认在 `gitea/main`，不要删了重建，也不要另开第二棵。
4. 等待期间不空转：把 §2.5 的 CLAUDE.md 小修做掉（纯文档，主树 `main` pathspec 提交推送，提交信息 `docs(claude): 工具 / 技能实数按注册表更新`）。
5. 每张 PR 到来：按 §2.3 独立验收，把「✅/❌ 逐条 + 收据路径 + 未做原因」写成一段报给派单人，**不合**。用户说「合 <N>」后：`python3 scripts/gitea_pr.py merge <N> --yes` → 主树 ff → INDEX 行、`docs-finance-agent-bp.md`「下一步」、记忆库回写（小文档修补，主树 `main` pathspec 提交推送）→ 若是 #23，回填 BP §7.3（同一提交）。
6. #25 合入后（或其 PR 到来时）额外核三件：`memory_bucket` 分布与 `model_cutoffs.json` 是否只认官方来源（查不到填 null）；读数是否全带 `pit_grade / memory_bucket / arm` 三标签、N<10 格子只给 N；`docs/learning/forecast-review-ledger/` 与 `/Users/a77/fidelity-replay/pit-snapshots/` 零改动（`git status` 该目录为空）。这三条是设计稿 §10.2 第四条守门，验收不过不放行。
7. 三张全部合入后：INDEX 三行齐、交接「下一步」只剩用户项与「下一空号 #26」、记忆库一条总结；回复派单人。

### 验收

- [ ] 主树 `git log --oneline -1` == `gitea/main`；三棵工单树干净且与 `gitea/main` 同步；`fwp-wt-finance-agent-bp` 已移除。
- [ ] 三张单各有执行 agent 在跑（或口令已交给派单人）；#25 派出前 `git log gitea/main..feat/methodology-backtest-p1-refuted` 的结果与预算窗口确认记录在回复里。
- [ ] 每张 PR 的验收段：`conflict-check` clean、收据 `counts.failed==0` 且 `check_test_receipt.py` 退出码 0、`layer_audit` / `check_unread_fields` 无新增、工单验收项逐条 ✅/❌、交接与 INDEX 行已改。
- [ ] 合入后：INDEX 行改为一句话现状；`docs-finance-agent-bp.md`「下一步」对应项划掉；#23 合入后 BP §7.3 占位已替换为核过的句子；记忆库有条目。
- [ ] `CLAUDE.md` 两处数字已按实数更新并推送。
- [ ] 全程零合并未经用户确认；零 push `main` 除小文档回写。

## 6. 红线（抄 AGENTS.md，不新发明）

- 开工先 `git status --short && git branch --show-current && git worktree list`；主树只做 `--ff-only` 与小文档 pathspec 提交。
- 🚫 禁 `git add -A` / `git add .`；一律 `git commit -- <明确文件列表>`；不强推；**合并 `main` 必须等用户确认**。
- 🚫 禁提交 `.env*` / 密钥 / `*.duckdb` / `*.jsonl` 用户台账 / 探针原始输出 / 节点级产物 / `.DS_Store` / 缓存。
- 解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`；主库、旁路库、快照目录、双盲台账全程只读。
- 门禁纪律：pytest 串行（先 `ps -eo command | rg -c 'python -m pytest|Python -m pytest'` 为 0）；全量只在最后跑一次；不用 `-n auto`；收据看 `<stamp>-<rev8>.json` 不看 `latest.json`。
- LLM 调用（#25）：只走 `llm_refine.complete`，尊重 `_budget_rejection`，被拒就停；不为「让数字好看」改提示词 / 温度 / 模型。
- 用户纠偏必落 correction（`python3 -m intelligence.cli record-correction ...`）。

## 7. 成立条件

- 现状读于 2026-09-05 00:30–00:45：`gitea/main@c6e702a6`；三棵工单树 `c6e702a6` 干净；第四刀 `e520e31e` 未推未开 PR；主树 `ba0393d1`。
- 工单里的行号复核到 `gitea/main@5c7fe2eb`，第三刀 #585 合入后已漂过一次，第四刀合入后再漂——执行 agent 以 `rg` 为准（口令已写）。
- 三个子 agent 的只读探索没有产物，重派等于从零开始；不要去找「上次做到哪」。

## 8. 最终回复给派单人（简明，中文）

主树与三棵树的核实结果；三张单派出时间与方式；每张 PR 的验收段（URL、尖 SHA、收据路径、退出码、逐条 ✅/❌、未做原因）；哪几张已合、`gitea/main` 新 SHA；INDEX / 交接 / BP §7.3 / 记忆库 / CLAUDE.md 各处回写的提交号；未做与原因。

## 9. 可迁移知识点（教学备注）

- **派单与验收分权**：协调者不写代码，只拿工单验收清单逐条对、拿收据验 revision——「谁做的谁不验」是 QC 的基本形状，`acceptance-workflow.md` 就是这套的仓内版。
- **门禁读数带成立条件**：收据文件名里的 rev8 + `check_test_receipt.py --expect-revision` 把「这次绿」钉在「这个提交」上；`latest.json` 会被别的 agent 覆盖，所以不可信——和「分支绿 ≠ 合流绿」一样是同一类假证据。
- **真钱调用先 dry-run**：#25 的 `--dry-run` 先打印节点数 / 调用数 / 估算 token，再真跑并设上限；被预算闸拒绝是系统在工作，不是要绕过的障碍。

---

## 附录 A · 工单 #23 派单口令（原文，贴给执行 agent）

```text
你是仓库 /Users/a77/finance-workspace-private 的执行 agent，任务是**完整实施工单 INDEX #23**：`docs/superpowers/specs/2026-09-04-judge-token-usage-workorder.md`（判官侧 token 用量记进 LLMCallLedger + 单次研究全口径成本报表）。工单自带背景、目标、非目标、证据路径表、步骤、验收、红线——以工单为唯一规格，逐条做完、逐条验收。

## 开工前必读（按顺序）
1. `/Users/a77/finance-workspace-private/AGENTS.md`（全文，尤其「Git Branch Safety Rules」「开工前必查」「提交纪律」「合并纪律」）。
2. 工单全文 `docs/superpowers/specs/2026-09-04-judge-token-usage-workorder.md`。
3. 工单 §4 证据路径表列出的每个文件——先读再改，禁止臆测；工单里的行号是 2026-09-04 读的，实施时用 `rg` 重定位。

## 环境与树（严格照做）
- 主检出树 `/Users/a77/finance-workspace-private` **不要在里面动手**（多 agent 共用）。树 `/Users/a77/fwp-wt-judge-token-usage`（分支 `feat/judge-token-usage`）**已经建好**（上一轮从 `gitea/main@c6e702a6` 开的，干净、无提交）：先 `cd /Users/a77/fwp-wt-judge-token-usage && git status --short && git branch --show-current && git fetch gitea --quiet && git log --oneline HEAD..gitea/main | wc -l`，落后就 `git merge --ff-only gitea/main`；之后所有工作都在这棵树内进行（每条 shell 命令都显式 `cd` 到这棵树或用 `git -C`）。不要删了重建，不要另开第二棵。
- 解释器只用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`（venv 无 .pth，加载哪份代码由 cwd 决定，在新树 cwd 下调用即可）。宿主 python3 缺依赖。
- 基线应为 `gitea/main` = `c6e702a6`（若已更新则以当时最新为准，记进交接）。

## 本机资源纪律（机器 16 GB 内存、swap 接近满，且同时有其他 agent 在跑）
- **任何 pytest 之前**先 `ps -eo command | rg -c 'python -m pytest|Python -m pytest'`，结果非 0 就 `sleep 30` 再查，最多等 30 分钟；等到 0 再跑。开发中只跑工单点名的定向测试文件；**全量门禁 `bash scripts/run_main_gate.sh` 只在最后跑一次**，同样先等到无其他 pytest。不要用 `-n auto`。不要跑 `pnpm build` 等前端命令（本单前端零改动，交接里写明即可）。
- 门禁读收据时不要只看 `~/.finance-runtime/test-receipts/latest.json`（其他 agent 会覆盖它）；用你那次 pytest 生成的带时间戳文件 `<stamp>-<rev8>.json`，并跑 `python scripts/check_test_receipt.py <该文件> --expect-revision "$(git rev-parse HEAD)"`。
- 工单步骤 2「探明 CLI」要做一次真实判官调用：只做一次，原始 stdout 落 `~/.finance-runtime/judge-usage-probe-<date>/raw.json`，不进仓。

## 提交与 PR
- 每步一个提交，一律 `git add -- <文件>` + `git commit -m "..." -- <明确文件列表>`；🚫 禁 `git add -A` / `git add .`；提交信息中文、遵循仓内风格（`feat(judge-usage): …` / `docs(handoff): …`）。
- 不提交 `.env*`、密钥、`*.duckdb`、`*.jsonl` 台账、探针原始输出、`.DS_Store`、缓存。
- 做完：`git push gitea feat/judge-token-usage`，然后 `python3 scripts/gitea_pr.py open --head feat/judge-token-usage --base main --title "<中文标题，含 INDEX #23>" --body-file <PR 正文 md>`（在主树 `/Users/a77/finance-workspace-private` 下运行该脚本）。**绝对不要合并到 main，不要 push main，不要强推。**
- 在途交接 `docs/handoffs/inflight/feat-judge-token-usage.md` 按工单 §2.10 写（分支做什么 / 决策与被否方案 / 当前状态 / 已验证（带数字与收据路径）/ 未验证与已知边界 / 下一步 / 踩过的坑），并在 INDEX `docs/superpowers/specs/2026-09-01-workorders-INDEX.md` 的 #23 行把「⏳ 待派」改成一句话现状（分支、PR 号、关键读数）。
- 工单 §2.9「真库读数（≥ 20 个新 run）」依赖改动上线后积累数据，本次做不到：在交接「未验证」里写明，并把报表对合成 run 目录的输出与对现有旧 run 目录（会计入「判官未记账」）的输出都放进交接。

## 遇到问题
- 工单里说「先探明」的事实（grok CLI stdout 有无 usage）以探明结果为准，两条分支只实现真正需要的那条（另一条留可测的纯函数即可），并在交接写清依据。
- 若某条验收确实做不到，不要伪造读数：在交接「未验证 / 已知边界」逐条写出原因。
- 用户不在线，不要停下来提问；所有判断写进交接的「决策与被否方案」。

## 最终回复给我（简明，中文）
PR URL 与号；分支尖 SHA；每条工单验收项 ✅/❌ 及读数；变异测试结果；定向测试与全量门禁读数（passed/failed/skipped，收据路径，`check_test_receipt.py` 退出码）；探明结果（CLI 有无 usage）；未做与原因；交接文件路径。
```

## 附录 B · 工单 #24 派单口令（原文，贴给执行 agent）

```text
你是仓库 /Users/a77/finance-workspace-private 的执行 agent，任务是**完整实施工单 INDEX #24**：`docs/superpowers/specs/2026-09-04-checkpoint-rule-id-bias-catalog-workorder.md`（可证伪点台账带 `rule_id` + 登记时回显规则四态 + 偏差目录 v1 四条 + `bias-scan`）。工单自带背景、目标、非目标、证据路径表、步骤、验收、红线——以工单为唯一规格，逐条做完、逐条验收。

## 开工前必读（按顺序）
1. `/Users/a77/finance-workspace-private/AGENTS.md`（全文，尤其「Git Branch Safety Rules」「开工前必查」「提交纪律」「合并纪律」「用户纠偏必落 correction」）。
2. 工单全文。
3. 设计稿 `docs/superpowers/specs/2026-09-04-methodology-backtest-structured-history-design.md` §10（尤其 §10.2 第一条——理性 / 非理性按过程定义，偏差目录只收能确定性算出的条目）。
4. 工单 §4 证据路径表列出的每个文件——先读再改，禁止臆测；行号以 `rg` 重定位。特别注意：`intelligence/services/checkpoints.py` docstring 承诺「只用标准库」，**不得**在它里面 import duckdb / methodology_backtest；偏差目录另开 `intelligence/services/checkpoint_bias.py`。

## 环境与树（严格照做）
- 主检出树 `/Users/a77/finance-workspace-private` **不要在里面动手**。树 `/Users/a77/fwp-wt-checkpoint-bias`（分支 `feat/checkpoint-rule-id-bias`）**已经建好**（上一轮从 `gitea/main@c6e702a6` 开的，干净、无提交）：先 `cd /Users/a77/fwp-wt-checkpoint-bias && git status --short && git branch --show-current && git fetch gitea --quiet && git log --oneline HEAD..gitea/main | wc -l`，落后就 `git merge --ff-only gitea/main`；之后所有工作都在这棵树内（每条命令显式 `cd` 或 `git -C`）。不要删了重建，不要另开第二棵。
- 解释器只用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。
- 基线应为 `gitea/main` = `c6e702a6`（若已更新以当时最新为准，记进交接）。
- 主库 `db/market_feature_store.duckdb` 与旁路库 `db/history_labels.duckdb`（都在主树 `/Users/a77/finance-workspace-private/db/`）**全程只读**（`read_only=True`）。旁路库现为 `LABEL_VERSION` v2（PR #585 后重建），标签名见 `methodology_backtest/labels.py`。
- 真人用户台账（`FORESIGHT_USERS_DIR` 解析出的大脑目录，本机 `~/.local/share/finance-workbench/users/<user>/checkpoints.jsonl`）**只读**；测试登记一律用 `--user replay-test` 或临时目录，不污染真人台账。

## 本机资源纪律（机器 16 GB 内存、swap 接近满，且同时有其他 agent 在跑）
- **任何 pytest 之前**先 `ps -eo command | rg -c 'python -m pytest|Python -m pytest'`，非 0 就 `sleep 30` 再查，最多等 30 分钟；等到 0 再跑。开发中只跑工单点名的定向测试文件；**全量门禁 `bash scripts/run_main_gate.sh` 只在最后跑一次**，同样先等到无其他 pytest。不要用 `-n auto`。不跑前端命令（本单前端零改动，交接写明）。
- 门禁收据不要只看 `~/.finance-runtime/test-receipts/latest.json`（其他 agent 会覆盖）；用你那次生成的 `<stamp>-<rev8>.json`，并跑 `python scripts/check_test_receipt.py <该文件> --expect-revision "$(git rev-parse HEAD)"`。
- 还要跑 `python scripts/layer_audit.py` 与 `python scripts/check_unread_fields.py`（工单验收项）。

## 提交与 PR
- 每步一个提交，一律 `git add -- <文件>` + `git commit -m "..." -- <明确文件列表>`；🚫 禁 `git add -A` / `git add .`；提交信息中文、仓内风格。`checkpoints.py` 新字段与其读者（`calibrate.by_rule` + `render_report`）**必须同一个提交**（unread-fields 棘轮门禁）。
- 不提交 `.env*`、密钥、`*.duckdb`、`*.jsonl` 台账、`.DS_Store`、缓存。
- 做完：`git push gitea feat/checkpoint-rule-id-bias`，然后在主树下 `python3 scripts/gitea_pr.py open --head feat/checkpoint-rule-id-bias --base main --title "<中文标题，含 INDEX #24>" --body-file <PR 正文 md>`。**绝对不要合并到 main，不要 push main，不要强推。**
- 在途交接 `docs/handoffs/inflight/feat-checkpoint-rule-id-bias.md`（分支做什么 / 决策与被否方案 / 当前状态 / 已验证（带数字与收据路径）/ 未验证与已知边界 / 下一步 / 踩过的坑）；INDEX `docs/superpowers/specs/2026-09-01-workorders-INDEX.md` #24 行「⏳ 待派」改为一句话现状（分支、PR 号、真库 bias-scan 读数）；`docs/learning/ledger-map.md` 第 14 行格式列补字段；设计稿 §10.2 第一条四个偏差名与实现对齐（若你的实现名与工单不同，以工单名为准，不要另起名）。

## 遇到问题
- 若某条验收确实做不到，不要伪造读数：交接「未验证 / 已知边界」逐条写原因。
- `themes` 文本 → `sector_ts_code` 映射（`dim_sector` / `config_theme_sector_link`）映射不到就 unverifiable，这是预期，不要硬猜。
- 用户不在线，不要停下来提问；判断写进交接「决策与被否方案」。

## 最终回复给我（简明，中文）
PR URL 与号；分支尖 SHA；每条工单验收项 ✅/❌ 及读数；真库 `bias-scan` 四条 flag 的命中 / unverifiable / 不适用计数；变异测试结果；定向测试与全量门禁读数（passed/failed/skipped，收据路径，`check_test_receipt.py` 退出码，`layer_audit` / `check_unread_fields` 结果）；未做与原因；交接文件路径。
```

## 附录 C · 工单 #25 派单口令（原文，贴给执行 agent；派前确认 LLM 预算窗口）

```text
你是仓库 /Users/a77/finance-workspace-private 的执行 agent，任务是**完整实施工单 INDEX #25**：`docs/superpowers/specs/2026-09-04-historical-replay-engine-workorder.md`（历史重放引擎：站 D0 出结构化判断 → 自动判分 → AI 校准读数；`pit_grade` 分档；模型截止日分栏；匿名化对照臂；与双盲台账对账；规则 schema 两加法）。工单自带背景、目标、非目标、证据路径表、步骤、验收、红线——以工单为唯一规格，逐条做完、逐条验收。这是三到五天量级的中单，按工单 §5 步骤顺序推进，每步一个提交。

## 开工前必读（按顺序）
1. `/Users/a77/finance-workspace-private/AGENTS.md`（全文）。
2. 工单全文，特别是 §1「PIT 现实」与「形态决策（写死）」、§3 非目标、§6 红线。
3. 设计稿 `docs/superpowers/specs/2026-09-04-methodology-backtest-structured-history-design.md` §10（六句理念对照、四条守门、§10.3 顺序）。
4. 工单 §4 证据路径表列出的每个文件——先读再改，禁止臆测；行号以 `rg` 重定位。`docs/learning/fidelity-replay-evaluation.md` 与 `docs/learning/pit-snapshot-inventory.md` 两条纪律（「`updated_at < as_of + 1 day` 才算 PIT」「后补数据不冒充 PIT」）是硬约束。

## 环境与树（严格照做）
- 主检出树 `/Users/a77/finance-workspace-private` **不要在里面动手**。树 `/Users/a77/fwp-wt-replay-engine`（分支 `feat/historical-replay-engine`）**已经建好**（上一轮从 `gitea/main@c6e702a6` 开的，干净、无提交）：先 `cd /Users/a77/fwp-wt-replay-engine && git status --short && git branch --show-current && git fetch gitea --quiet && git log --oneline HEAD..gitea/main | wc -l`，落后就 `git merge --ff-only gitea/main`；之后所有工作都在这棵树内（每条命令显式 `cd` 或 `git -C`）。不要删了重建，不要另开第二棵。
- 解释器只用 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`；先 `python -c "import duckdb"`。
- 基线应为 `gitea/main` = `c6e702a6`（若已更新以当时最新为准，记进交接）。
- 主库 `db/market_feature_store.duckdb`、旁路库 `db/history_labels.duckdb`（主树 `db/` 下，`LABEL_VERSION` v2）、快照目录 `/Users/a77/fidelity-replay/pit-snapshots/`、双盲台账 `docs/learning/forecast-review-ledger/` **全程只读**；台账目录一个字节都不写（`git status` 该目录必须无改动）。节点级产物落 `~/.finance-runtime/replay/<run_id>/`，不进仓。
- **schema 步骤的顺序约束**（工单 §2.10）：在途分支 `feat/methodology-backtest-p1-refuted`（树 `/Users/a77/fwp-wt-methodology-backtest-p1d`）已实现 `sharing / owner / source_perspective` 扁平字段与证伪库。开工时先 `git log gitea/main..feat/methodology-backtest-p1-refuted --oneline` 看它合没合：**没合就把 `rules.py` / `runner.py` / `receipts.py` 的 schema 加法（`discovered`、`windows` 双窗）放到最后做，且做之前再 fetch 一次**；若届时已合入 main，先 `git merge gitea/main` 再做。`_TOP_KEYS` 只追加 `windows`，不碰它们的键名。

## LLM 调用纪律（真钱、共享预算）
- 只走 `intelligence.services.llm_refine.complete`；尊重 `_budget_rejection`——被拒就停下记录，**不要循环重试、不要绕预算闸**。
- 先 `run --dry-run` 打印节点数 / 调用数 / 估算 token，再真跑；`--max-calls` 默认 200、本次真跑不得超过 200 次调用；默认 `--count-per-grade 20 --arms named,anonymized --lanes A,B`。若预算被拒或失败率 > 20%，缩到 `--count-per-grade 10` 再试一次，仍不行就把 dry-run 与部分结果写进交接，不要硬撑。
- 提示词、温度、模型在本单内一经确定不得为「让数字好看」而改（工单红线）。
- 模型训练截止日只认官方文档 / 模型卡 URL；查不到填 `null` 并写 `note`，不要用媒体转述。

## 本机资源纪律（机器 16 GB 内存、swap 接近满，且同时有其他 agent 在跑）
- **任何 pytest 之前**先 `ps -eo command | rg -c 'python -m pytest|Python -m pytest'`，非 0 就 `sleep 30` 再查，最多等 30 分钟；等到 0 再跑。开发中只跑工单点名的定向测试文件；**全量门禁 `bash scripts/run_main_gate.sh` 只在最后跑一次**，同样先等到无其他 pytest。不要用 `-n auto`。不跑前端命令（前端零改动，交接写明）。
- 门禁收据不要只看 `~/.finance-runtime/test-receipts/latest.json`（其他 agent 会覆盖）；用你那次生成的 `<stamp>-<rev8>.json`，并跑 `python scripts/check_test_receipt.py <该文件> --expect-revision "$(git rev-parse HEAD)"`。还要跑 `python scripts/layer_audit.py` 与 `python scripts/check_unread_fields.py`。

## 提交与 PR
- 每步一个提交，一律 `git add -- <文件>` + `git commit -m "..." -- <明确文件列表>`；🚫 禁 `git add -A` / `git add .`；提交信息中文、仓内风格（`feat(replay-engine): …`）。
- 不提交 `.env*`、密钥、`*.duckdb`、`*.jsonl` 台账、节点级产物、`.DS_Store`、缓存；`intelligence/eval/model_cutoffs.json` 与 `intelligence/eval/measurements/replay-*.{json,md}` 要提交。
- 做完：`git push gitea feat/historical-replay-engine`，然后在主树下 `python3 scripts/gitea_pr.py open --head feat/historical-replay-engine --base main --title "<中文标题，含 INDEX #25>" --body-file <PR 正文 md>`。**绝对不要合并到 main，不要 push main，不要强推。**
- 在途交接 `docs/handoffs/inflight/feat-historical-replay-engine.md`（分支做什么 / 决策与被否方案 / 当前状态 / 已验证（带数字与收据路径）/ 未验证与已知边界 / 下一步 / 踩过的坑）；INDEX `docs/superpowers/specs/2026-09-01-workorders-INDEX.md` #25 行「⏳ 待派」改为一句话现状（分支、PR 号、两车道关键读数、`memory_bucket` 分布）；`docs/learning/ledger-map.md` 加一行。

## 遇到问题
- 工单 §5 步骤 3 要求先在实施基线上重出「PIT 现实」的数字（`updated_at` 分布、快照份数与缺日），照做并写进交接；数字若与工单不同，以你重出的为准。
- 若某条验收确实做不到，不要伪造读数：交接「未验证 / 已知边界」逐条写原因。任何读数都必须带 `pit_grade / memory_bucket / arm` 三标签，格子 N<10 只给 N。
- 用户不在线，不要停下来提问；判断写进交接「决策与被否方案」。

## 最终回复给我（简明，中文）
PR URL 与号；分支尖 SHA；每条工单验收项 ✅/❌ 及读数；车道 A 两档两臂一致率、车道 B 分格表摘要、对账段摘要、`memory_bucket` 分布与截止日表内容；真跑 LLM 调用次数 / 失败次数；变异测试两条结果；selftest 结果；定向测试与全量门禁读数（收据路径，`check_test_receipt.py` 退出码，`layer_audit` / `check_unread_fields`）；schema 步骤是在第四刀合入前还是后做的；未做与原因；交接文件路径。
```
