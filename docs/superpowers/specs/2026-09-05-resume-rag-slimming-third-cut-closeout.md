# 2026-09-05 接手单 B：RAG 瘦身第三刀收口（金融 PR #587 合入）→ 让三刀在生产 8792 上生效 → 工单 #22 步骤 1「干净 p95」

可独立分发。执行方无需读聊天记录，本单自带现状核实、证据路径、步骤、验收与红线。
接的是 2026-09-04 深夜中断的 Cursor session（用户最后一句口令：「合并，然后你按照最优推进」）。
中断原因是 Cursor 模型不可用，上一轮 agent 最后一段动作没有留在转录里；下面「现状」全部以 git / Gitea / 收据文件 / 进程表重新核实。

> **派单口令（贴给新 agent）**：你是仓库 `/Users/a77/finance-workspace-private`（金融仓）与 `/Users/a77/knowledge-base-private`（KB 仓）的执行 agent。读 `/Users/a77/fwp-wt-resume-specs-0905/docs/superpowers/specs/2026-09-05-resume-rag-slimming-third-cut-closeout.md` 全文并逐条执行；用户不在线，判断写进交接。**合并 `main` 要用户确认**（本口令含「合并」即视为确认金融 PR #587）；**动生产 8792 要用户确认**（本口令含「重启」= 允许步骤 5 选项一；含「切」= 允许步骤 5 选项二；两个字都没有就停在步骤 5 之前报告）。

## 1. 这条线是什么、停在哪

工单 `docs/superpowers/specs/2026-09-04-rag-worker-resident-memory-workorder.md`（INDEX #22）：生产 RAG 常驻 worker 足迹 7.3 GB，在 16 GB / swap 满的机器上请求之间被整个换出，每次查询先付 20–60 s 换入，30 s 工具帽必超时。工单「内存画像」把选项 B（瘦身）升为主刀，拆三段，现在三段都已合入 KB 仓 `gitea/main`：

| 刀 | KB PR | 省什么 | 状态 |
|---|---|---|---|
| dense.npy fp16 只读 memmap | #141 | 0.7 GB | 已合、已部署 |
| BM25 换纯 numpy 倒排 `bm25_csc.*`（只读 memmap） | #142 → `gitea/main@9f9bfe77a` | 1.86 GB，打分 3–18 s → ms | 已合、已部署：生产索引 `/Users/a77/knowledge-base-private/.rag_index/bm25_csc.*` 已落（280 MB，09-04 22:40，指纹与 `meta.json` 三方一致） |
| chunks.jsonl 懒读 `chunk_table.py`（只留行偏移、正文按需解析 + 4096 行 LRU） | #143 → `gitea/main@24ef52a22` | 1.4 GB | **已合**（上一轮最后动作之一）；KB 主树 `skills/lib/rag/` 已同步到 `gitea/main`（`git archive gitea/main skills/lib/rag` 与主树 `diff -rq` 逐字节同） |

第三刀有**金融侧配套**：金融 worker `scripts/rag_query_worker.py` 加载时把 `store.chunks` 整份复制进 `state["chunks"]` 做 enrich，KB 懒读后老 worker 会把 169k 行全解析攥着（不退化但 1.4 GB 一分不省）。配套 PR **#587 还开着**：

| 项 | 值（2026-09-05 00:40 核实） |
|---|---|
| PR | [finance #587](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/587) `perf/rag-worker-lazy-chunks`，Gitea 上的 head 仍是 `1c6fa9de`（该 rev 全量 7715P/0F/15S，收据 `20260904T151750Z-1c6fa9de.json`，已评论到 PR） |
| 树 | `/Users/a77/fwp-wt-rag-worker-lazy-chunks` 干净；本地 HEAD 是**未推的合并提交 `892a6ec2`**（`Merge remote-tracking branch 'gitea/main' into perf/rag-worker-lazy-chunks`，对 `gitea/main@c6e702a6` 0 落后）——上一轮按「合前若 main 又动了在合并树上重跑收据」的纪律做的 |
| 合并树门禁 | `~/.finance-runtime/test-receipts/20260904T153659Z-892a6ec2.json`：**7714P / 1F / 15S**，exit 1，`dirty=false`。红的一条 `intelligence/tests/test_agent_review_worker.py::test_worker_shutdown_terminates_reviewer_process_group`——进程组关停时序测试，与 diff 零交集；**有前科**（`docs/handoffs/inflight/feat-watchlist-digest-pack.md:20`：「唯一红 …process_group（进程组关停，单跑 0.69s 绿）」）；且 23:24–23:37 本机三个全量门禁并行、swap 20/21 GB。按合并纪律仍须重跑拿绿 |
| 冲突 | `gitea_pr.py conflict-check --head perf/rag-worker-lazy-chunks --base gitea/main` → clean |
| 生产 | 8792 = launchd `com.a77.finance-workbench`（pid 4587），运行时快照 `/Users/a77/finance-workspace-runtime -> ~/.finance-runtime/finance-workspace-f4c03b9ae610`（`f4c03b9a`，09-03 16:13 切的，**落后 `gitea/main` 90 个提交**）。RAG worker 子进程 pid 4665（`.rag_venv` python 3.14，脚本来自该快照的 `scripts/rag_query_worker.py`，KB 代码来自 KB 主树 `skills/lib/rag/`，索引 `.rag_index/`），已跑 1 天 8 小时**未重启**：RSS 3.7 MB（整个在 swap 里）。`/api/readiness` `workers.rag`：`queries_served=1, timeouts_abandoned_kept_warm=1`，无 `rss_bytes / idle_seconds`（那是 PR #577 加的，快照没有）。**三刀在生产上一刀都还没生效** |
| 记忆库 | `/Users/a77/agent-memory/20_projects/finance-workspace-private.md` 交接记录仍写「KB #143 + 金融 #587 未合、等用户确认」——过时，要改 |
| KB 主树 | `/Users/a77/knowledge-base-private` 本地 `main`=`e4c9a9390` 落后 `gitea/main` 13 个提交；工作区里 `skills/lib/rag/` 已是新代码但**按惯例只改工作区不暂存**（`git checkout gitea/main -- skills/lib/rag && git reset -q -- skills/lib/rag`；索引留在 HEAD，因为主树与别的 agent 共用、暂存会被别人的裸 `git commit` 带走）；另有他人未提交改动（`.claude/hooks/*`、`AGENTS.md`、`docs/superpowers/specs/2026-08-28-rss-l3-quality-repair.md`）——**不是我们的，不碰** |

工单 #22 五步的进度：步骤 2（keepalive，默认关）与 3（readiness 露出 `rss_bytes / last_query_at / idle_seconds`）已合 `main`（PR #577，`intelligence/services/rag_worker.py`）但**不在生产快照里**；步骤 4（mmap）做成了三刀；**步骤 1（RSS 曲线 + 干净 p95）没做**——上一轮判断要等机器安静；步骤 5（回预算闸）依赖步骤 1，另立单。

## 2. 目标（可验收）

1. 金融 PR #587 以绿门禁合入 `main`；主树 ff；记忆库与 INDEX #22 行回写。
2. 三刀在生产 8792 生效（按派单口令的授权走「重启」或「切」；无授权则把两种做法的代价写清停下）。生效的判据：新 worker 进程的 `ps -o rss,vsz`、`vmmap --summary <pid>` 的 Physical footprint，以及一次真实 kb 查询的 `last_latency_ms`。
3. 工单 #22 步骤 1：新 worker 上跑 2–4 小时只读探针（RSS / readiness 计数 / 距上次查询秒数，60 s 一采）+ 不换页条件下的 hybrid 五段 p50/p95（6 题），产物落 `~/.finance-runtime/rag-mem-probe-<date>/`，结论写进交接与记忆库；**swap > 80% 的时段不读 p95 当申报值**。
4. 交接落地：这条线此前只在记忆库与 PR 正文里，本单新建 `docs/handoffs/inflight/perf-rag-worker-slimming.md`（分支做什么 / 三刀读数 / 生产生效读数 / 步骤 1 读数 / 未验证 / 下一步），走 docs PR 或随主树小修补合入。

## 3. 非目标（写死认领）

- ❌ bge-m3 fp16 / 换小模型（工单选项 C，产品级决策，另立单；也是 worker 剩下最大的一块 ≈ 2.5 GB）。
- ❌ 抬 `episode_tools.py` 的 30 s 帽、改 `min_window_seconds`（kb_search 20 / evidence_search 30）、`for_tier` / reserve / `ASK_TOOL_BATCH_TIMEOUT`、`MAX_TOTAL_SECONDS`、`require_fresh` 默认——**拿到干净 p95 之后另立单**（工单步骤 5）。
- ❌ 跑预算矩阵 T120/R20 等。
- ❌ 重建 RAG 索引、跑 `rag_build_full.py`（三刀产物已在 `.rag_index/`，不需要）；量测期间**不在这台机器上起第二个 bge-m3 进程**（09-04 晚探针就是这样把自己和生产一起压进 swap 的）。
- ❌ 碰 KB 主树里他人的未提交改动；改 KB 新鲜度判据。
- ❌ 在 `.rag_index/` 里写任何东西。
- ❌ 把 8792 切到 `gitea/main` 的决定替用户做（见步骤 5）。

## 4. 证据路径表（先读这些，禁止臆测）

| 文件 / 命令 | 看什么 |
|---|---|
| `docs/superpowers/specs/2026-09-04-rag-worker-resident-memory-workorder.md` 全文 | 五步、验收、内存画像、红线（「不切 8792 除非走既定切换仪式」「量测期间不起第二个 bge-m3」） |
| `/Users/a77/agent-memory/20_projects/finance-workspace-private.md` 里 `rg -n "RAG 瘦身"` 命中的三条交接记录 | 三刀各自的读数、部署惯例、`vmmap` 教训（RSS 把干净文件页也算进去，看足迹用 `vmmap --summary` 的 dirty / Physical footprint） |
| `git -C /Users/a77/fwp-wt-rag-worker-lazy-chunks log --oneline -3 && git -C ... status --short && git -C ... diff --stat gitea/main...HEAD` | HEAD `892a6ec2`、干净、只改 `scripts/rag_query_worker.py` + `intelligence/tests/test_rag_worker.py` |
| `scripts/rag_query_worker.py`（分支上）`_chunk_by_id`、`_enrich_query_output` | 金融侧改法：`state["chunks"]` 不再填，按 `retriever.row_by_chunk_id` + `retriever.chunks[row]` 现取；索引级字段与块级字段解耦 |
| `intelligence/services/rag_worker.py`（`gitea/main`）`RAG_WORKER_KEEPALIVE_SECONDS`、`_process_rss_bytes`、`idle_seconds`、`status()` | 步骤 3 已合的观测面；切到新快照后 readiness 才会露出；生产快照 `f4c03b9a` 上没有 |
| `intelligence/services/kb_rag.py` `retrieve(...)`、`intelligence/services/episode_tools.py` `retrieve_kb`（30 s 帽） | 生产查询路径；步骤 1 的五段量测要走这条路（经 8792 的 worker），不要另起模型 |
| KB 仓 `skills/lib/rag/chunk_table.py`、`bm25.py`、`store.py::RagStore.load`、`README.md` | 三刀实现；`RAG_BM25_MMAP=0` / `RAG_CHUNKS_LAZY=0` 是回退旋钮 |
| `cd /Users/a77/knowledge-base-private && rm -rf /tmp/kb-rag-main && mkdir -p /tmp/kb-rag-main && git archive gitea/main skills/lib/rag \| tar -x -C /tmp/kb-rag-main && diff -rq /tmp/kb-rag-main/skills/lib/rag skills/lib/rag --exclude=__pycache__ --exclude=eval` | 部署完整性：应输出空（逐字节同） |
| `python3 -c "import json;print(json.load(open('/Users/a77/knowledge-base-private/.rag_index/bm25_csc.meta.json'))['source_fingerprint']==json.load(open('/Users/a77/knowledge-base-private/.rag_index/meta.json')).get('source_fingerprint'))"` | 倒排与 chunks 指纹一致（应 True） |
| `docs/workflows/acceptance-workflow.md` §4「切 8792（链切五步）」+ 三项验证 + 回滚 | 选项二的唯一规程；`~/.finance-runtime/cutover-20260825l-8792.md` 是一份写得全的切换记录范本 |
| `~/Library/LaunchAgents/com.a77.finance-workbench.plist`、`launchctl print gui/$(id -u)/com.a77.finance-workbench` | 服务标签、env、工作目录；选项一的重启对象 |
| `curl -s http://127.0.0.1:8792/api/readiness`、`/api/health` | 切前 / 切后读数；`workers.active` 为 0 才可重启 |
| `ps -eo pid,ppid,rss,etime,command \| rg rag_query_worker`、`vmmap --summary <pid> \| rg -i "physical footprint\|dirty"` | worker 进程与真实足迹 |
| `git -C /Users/a77/finance-workspace-private log --oneline f4c03b9a..gitea/main \| wc -l`（现 90） | 选项二会一起上线的提交数——这是它为什么需要用户拍板 |
| `/Users/a77/fwp-wt-wiki-aperture-ablation/scripts/profile_wiki_hybrid_phases.py`（分支 `perf/wiki-hybrid-25s`，**未合 main**） | 五段口径的现成脚本；它自己起模型，**不能直接跑**——只借它的分段定义（load / freshness / encode / search / 合计），改成经 8792 worker 或在 8792 停机窗口量 |
| `scripts/gitea_pr.py --help`；PR 评论走 Gitea API（token：`security find-generic-password -s gitea-local -a a77-token -w`，不落盘） | 合并与评论方式（上一轮 PR #587 的收据评论就是这么发的） |
| `docs/superpowers/specs/2026-09-01-workorders-INDEX.md` #22 行 | 要改成一句话现状 |

## 5. 步骤 + 验收

### 步骤

1. 开工三连（金融主树与 KB 主树各一次）`git status --short && git branch --show-current && git worktree list`。两棵主树都有他人足迹或落后，**都不在主树动手**；金融侧在 `/Users/a77/fwp-wt-rag-worker-lazy-chunks`，KB 侧只读核实。
2. **收口 #587**：`cd /Users/a77/fwp-wt-rag-worker-lazy-chunks && git fetch gitea --quiet && git log --oneline HEAD..gitea/main | wc -l`——非 0 就再 `git merge --no-edit gitea/main`。等本机无其他 pytest（`ps -eo command | rg -c 'python -m pytest|Python -m pytest'` 为 0，最多等 30 分钟），先定向 `.venv-workbench/bin/python -m pytest -q -p no:cacheprovider intelligence/tests/test_rag_worker.py`（44 绿）+ 那条红单独跑 3 次 `-k test_worker_shutdown_terminates_reviewer_process_group`；再 `bash scripts/run_main_gate.sh` 全量；收据 `<stamp>-<rev8>.json` + `python scripts/check_test_receipt.py <file> --expect-revision "$(git rev-parse HEAD)"`。**0 failed** 才继续。`git push gitea perf/rag-worker-lazy-chunks`；把收据评论到 PR #587（沿用上一轮的 API 写法）。
3. 合并（派单口令含「合并」）：主树下 `python3 scripts/gitea_pr.py conflict-check --head perf/rag-worker-lazy-chunks --base gitea/main` clean → `python3 scripts/gitea_pr.py merge 587 --yes` → `cd /Users/a77/finance-workspace-private && git pull --ff-only gitea main`（主树干净、只 ff）。`git worktree remove /Users/a77/fwp-wt-rag-worker-lazy-chunks`（分支已合，Gitea 会删远端）。
4. KB 侧核实（只读）：证据表里的 `diff -rq` 为空、指纹 True；`cd /Users/a77/knowledge-base-private && .rag_venv/bin/python -c "import time,sys; from pathlib import Path; sys.path.insert(0,'skills/lib'); from rag import store; t=time.time(); bm=store.load_bm25(Path('.rag_index')); print(type(bm).__name__, round((time.time()-t)*1000),'ms')"`（预期 `SparseBM25`、十几 ms；签名见 `rg -n "def load_bm25" -A4 skills/lib/rag/store.py`——只读、不重建；若返回的不是 `SparseBM25` 说明走了回退重建路径，停下查指纹）。**不要**跑 `RagStore.load` 全量、不要起 bge-m3。KB 主树本地 `main` 落后 13 个提交且有他人足迹——不 pull，记进交接。
5. **让三刀在生产生效——需要授权，二选一**：
   - **选项一「重启」（推荐先做，低风险）**：不换快照，只重启 8792，worker 子进程随之重生，加载 KB 主树新代码 → dense + BM25 两刀立即生效（≈ 2.5 GB 匿名常驻消失、打分从秒级到毫秒级）；chunks 懒读在 KB 侧生效，但老 worker 脚本仍会把 169k 行解析进 `state["chunks"]`（不退化，省不下那 1.4 GB）。做法：`curl -s :8792/api/readiness` 确认 `workers.active=0` 且 `queued=0` → `launchctl kickstart -k "gui/$(id -u)/com.a77.finance-workbench"` → 等 readiness `checks` 全 true（冷启最长 3 分钟）→ 记新 worker pid、`ps -o rss`、`vmmap --summary` 足迹、`workers.rag.prewarm_latency_ms`。回滚 = 再 kickstart 一次不会更坏；若 worker 起不来，KB 侧 `RAG_BM25_MMAP=0 RAG_CHUNKS_LAZY=0` 是回退旋钮（要写进 launchd env 才对子进程生效，先报告再动）。
   - **选项二「切」（全效，但是一次 QC 决策）**：按 `docs/workflows/acceptance-workflow.md` §4 五步切到 `gitea/main` 尖（含 #587 与 #577 的 readiness 观测面），三项验证 + 账本 record + 回滚锚 + gitea 备份。**代价**：`f4c03b9a..gitea/main` 90 个提交一起上线，其中大部分本单执行者没验过；这正是它要用户一句「切」的原因。若授权，切前先在主树 tip 确认最近一次全量门禁绿（`ls -t ~/.finance-runtime/test-receipts/ | rg $(git rev-parse --short=8 gitea/main)`，没有就先跑）。
   - 口令两个字都没有 → 到此停下，把两个选项的代价与读数写进交接与最终回复。
6. **工单 #22 步骤 1（生效后，机器安静时）**：只读探针脚本（写在 `~/.finance-runtime/rag-mem-probe-<date>/probe.py`，不入仓）每 60 s 记：`ps -o rss,vsz -p <worker pid>`、`sysctl vm.swapusage`、readiness `workers.rag.counters` 与（若已切新快照）`rss_bytes / idle_seconds / last_latency_ms`；跑 2–4 小时。同一窗口内，**在只有生产 worker 在跑的时段**，经 8792 的真实路径发 6 条 kb 查询（用 `intelligence.cli ask` 或直接 `kb_rag.retrieve`，走生产 worker，不起第二个模型），记每条的五段耗时（`load / freshness / encode / search / total`，口径照 `profile_wiki_hybrid_phases.py`；能从 worker 返回的 telemetry 拿就拿，拿不到的段标「未分段」不要编）→ p50 / p95。产物：RSS-时间曲线（csv + 一张 md 表）、五段 p50/p95 表、swap 曲线。结论要回答工单验收第一条：「多久没请求 RSS 掉到 <100 MB」在瘦身后是否还成立。
7. 回写：新建 `docs/handoffs/inflight/perf-rag-worker-slimming.md`（结构照 `docs/handoffs/inflight/feat-methodology-backtest-p1-stock-labels.md`：分支做什么 / 读数表 / 决策与被否方案 / 已验证（收据路径）/ 未验证 / 下一步 / 踩过的坑）；INDEX #22 行改成一句话现状（三刀已合、#587 已合、生产生效方式与读数、步骤 1 读数、步骤 5 待立单）；记忆库 `20_projects/finance-workspace-private.md` 加一条并把「#143 + #587 未合」那条改状态；这些是纯文档，可在主树 `main` 上 pathspec 提交推送（本线惯例），或开 docs PR。
8. 步骤 5 的后续（**不做，只立**）：若干净 p95 拿到了，在交接「下一步」写清 `min_window_seconds` 与 30 s 帽的重填依据（p95 + 首轮模型延迟 7–13 s），并注明「另立单、号从 INDEX 取（下一空号 #26）」。

### 验收

- [ ] PR #587 已合（`gitea/main` 含 `scripts/rag_query_worker.py::_chunk_by_id`）；合并树全量门禁收据 `counts.failed==0`、`check_test_receipt.py` 退出码 0；那条进程组测试单独 3/3 绿的记录在交接。
- [ ] 金融主树 `git log --oneline -1` == `gitea/main`；`fwp-wt-rag-worker-lazy-chunks` 已移除。
- [ ] KB 主树 `skills/lib/rag/` 与 `gitea/main` 逐字节同；倒排指纹 True；`load_bm25` 走 mmap 毫秒级。
- [ ] 若授权重启 / 切：新 worker pid ≠ 4665；`vmmap --summary` Physical footprint 记录在交接（对照旧 worker 7.3 GB 足迹）；一次真实 kb 查询 `last_latency_ms` 记录在交接；若切，acceptance-workflow 三项验证读数 + 账本 + 回滚锚 + 备份文件齐。
- [ ] 步骤 1 产物目录存在，含 RSS 曲线与五段 p50/p95；每个 p95 都标了采样时段的 swap 占比。
- [ ] `docs/handoffs/inflight/perf-rag-worker-slimming.md` 存在且已入 `gitea/main`（或 PR 已开）；INDEX #22 行与记忆库已更新。
- [ ] 全程零 LLM 配额（步骤 6 的 6 条查询若走 `intelligence.cli ask` 会调 LLM——改用 `kb_rag.retrieve` 直连 worker，或在交接写明用了几次）。

## 6. 红线（抄 AGENTS.md 与工单 #22，不新发明）

- 开工先 `git status --short && git branch --show-current && git worktree list`；两棵主树都有他人足迹，**不在主树动手**（主树只做 `--ff-only` 与纯文档 pathspec 提交）。
- 🚫 禁 `git add -A` / `git add .`；一律 `git commit -- <明确文件列表>`；不强推；**合并 `main` 与动 8792 都要用户一句话**。
- 🚫 禁提交 `.env*` / 密钥 / `*.duckdb` / `.rag_index/*` / 探针原始输出 / `.DS_Store`；Gitea token 只从 keychain 读，不写进任何文件。
- 不切 8792 除非走 `acceptance-workflow.md` §4 的链切五步（账本 record / check、回滚锚）；重启前确认无在跑 run。
- 量测期间不并行起第二个 bge-m3；不在 swap > 80% 的时段读 p95 当申报值；每个 pytest 前先确认本机无其他 pytest。
- 不改任何预算数字、不改 `require_fresh` 默认、`freshness_report` 每问仍跑。
- 解释器：金融仓 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`；KB 仓 `/Users/a77/knowledge-base-private/.rag_venv/bin/python`（生产 worker 用的就是它）。
- 用户纠偏必落 correction（`python3 -m intelligence.cli record-correction ...`）。

## 7. 成立条件

- 现状读于 2026-09-05 00:30–00:45：金融 `gitea/main@c6e702a6`，KB `gitea/main@24ef52a22`，生产快照 `f4c03b9a`，worker pid 4665。任一变了以现场为准，记进交接。
- 「三个门禁并行导致假红」是嫌疑不是结论；结论以本单步骤 2 的隔离重跑 + 干净全量为准。
- 步骤 1 的读数只对「本机当时的 swap 占比 + 只有生产 worker 在跑」成立，表里每行带采样时段。

## 8. 最终回复给派单人（简明，中文）

PR #587 是否合入与 `gitea/main` 新 SHA；合并树门禁读数与收据路径、`check_test_receipt.py` 退出码；KB 部署核实三项结果；生产是「重启 / 切 / 未动」哪一种及依据；新 worker 足迹与一次真实查询延迟；步骤 1 是否完成、产物路径、五段 p50/p95 与 RSS 曲线结论；交接 / INDEX / 记忆三处回写的提交号；未做与原因。

## 9. 可迁移知识点（教学备注）

- **「上游省了、下游一个复制又吃回去」**：KB 把 chunks 换成偏移表，金融 worker 却在加载时把整表复制成 dict，1.4 GB 一分不省。任何带缓存层的系统在瘦身时都要沿数据流把每个消费者核一遍——ETL 里叫 materialization 审计。
- **RSS 不是足迹**：只读 memmap 的干净文件页也算进 RSS，被驱逐后从文件重读、不进 swap；真正会进压缩器和 swap 的是脏页 / 匿名页。macOS 看 `vmmap --summary` 的 Physical footprint，Linux 看 `smaps` 的 `Private_Dirty`。这也是为什么本单验收用足迹而不是 RSS。
- **重启 vs 切换是两种风险**：重启只换进程不换代码（KB 侧代码在主树、随重启生效），可回滚性极高；切换把 90 个提交一起带上线，风险来自「没验过的那 89 个」。把两者分开授权，是运维里「配置变更」和「版本发布」分权的同一形状。
- **倒排索引就是稀疏矩阵**：BM25 每个 (词, 文档) 的贡献只依赖语料常数，build 时算完落盘，query 只是取切片累加——搜索引擎的 posting list、scipy 的 CSR/CSC、列式存储的偏移表，都是「预计算 + 按需取页」这一个念头。
