> 本文是 `finance-base-ab/out/budget-matrix-0904/REVIEW-NOTES.md` 的入库副本（`out/` 在那个仓被 gitignore；
> 当晚那目录里的文件还遭过会话回写截空，故把事实落到这里）。原始数据、探针日志与 JSON 在原目录。
> 配套代码：finance-base-ab `5e58dc9`（台架进程内预热 / 载荷对账 / 探针）；主仓 PR #574（B6 澄清门）。

# budget-matrix-0904 · 复核笔记（2026-09-04 晚）

对 `RECEIPT.md` 与其后那份 review 的核查结论。下面第一、二节是**从数据和代码里核出来的事实**，
不是判断；接手的 agent 不要再发现一遍。第三节是裁决，第四节是当晚已落地的改动，第五节是下一步。

数据源：`2d8eaea5/` `f4c03b9a/` 两个目录下 `users/*/runs/*/continuous-episode.json`（原始事件），
代码引用一律对应 `gitea/main = 2d8eaea5`（也就是被测快照本身）。

---

## 0. 先看这条：生产启动器被截空（与本矩阵无关，但会挡下一次重启）

`~/.local/bin/start-finance-workbench`（8792 的 launchd 入口，`KeepAlive=true`）当晚被反复**原地截成 0 字节**
（inode 不变）：17:27、17:54:08、18:04:22、18:49:19、19:08:17 ……每一次都与我这个 Cursor 会话收到一条
用户消息的时刻重合，同一秒被原地回写的还有 `finance-base-ab/shape_lib/env.py`（→0 字节）、
`reference_loop_arm.py`（→1 字节）、`project.py` / `README.md` / `run-reference-loop.sh`（内容不变）、
`~/.local/bin/start-finance-workbench-capability-sidecar`（内容不变）——正是 09-02/09-03 那条会话线改过的
那一组文件。形状像 Cursor 的 checkpoint 回写，写者没有 root 权限查不到 fs_usage，不再追。

- 8792 进程本体健康（pid 4587，09-03 16:14 起，`f4c03b9a`，`/api/health` healthy）。**风险只在下一次重启**：
  launchd 会执行一个空脚本，服务起不来。
- 已做：`~/.local/bin/start-finance-workbench.restore-20260904`（mode 700，`bash -n` 通过）=
  `bak-20260903-admission` + 四条 admission 导出（`WORKBENCH_MAX_ACTIVE_RUNS_PER_USER=1` /
  `WORKBENCH_MAX_QUEUED_RUNS=4` / `WORKBENCH_QUOTA_EXEMPT_USERS=linxiaoqi5111` / `WORKBENCH_RUN_WORKERS=4`）。
  这四条取自仍在跑的 8792 进程环境（`ps -E`），plist 无 EnvironmentVariables，只能来自启动器；
  与 09-03 12:57 备份的差就是它们。
- **要做（用户）**：先关掉/结束那条会回写的会话，再 `cp start-finance-workbench.restore-20260904 start-finance-workbench`；
  否则下一条消息又把它截空。`env.py` / `reference_loop_arm.py` 已用 `git checkout` 从 HEAD 恢复
  （pyc 头里的源码尺寸 7500 / 11237 与 HEAD blob 完全一致，工作副本当时就是 HEAD）。

---

## 1. 三个硬事实（改变下一步方向）

### F1 · 48 个 run、41 次 RAG 调用，RAG 层没有送到过一个字节

按载荷（`evidence` 非空）而不是按 `ok` 数：

| 臂 | kb_search | evidence_search | 命中 |
|---|---|---|---|
| 2d8 控 | 10 次，全 `tool_error: tool_timeout`（stage 级，授窗 16–17s） | 0（被菜单藏） | 0 |
| 2d8 开闸 | 14 次，`ok=True`，观察串全是「常驻 worker 超时(>30.0s)，进程已终止」，elapsed 30.34–30.51s | 8 次，`ok=True`，`observation=""`，`evidence=[]`，gap「尚未找到直接相关的可用证据」，elapsed **60.65–60.90s** | 0 |
| f4c 控 | 9 次，全 stage 级 `tool_timeout` | 0（被菜单藏） | 0 |

`evidence_search` 那 8 次「成功」是**空成功**：`kb_search` 与 `evidence_search` 底下同一个
`episode_tools.retrieve_kb`（`episode_tools.py:904–910`，硬编码 `timeout=min(timeout, 30.0)`）；
`evidence_search` 外面套闭环检索 narrow → broad → counter（`closed_loop_retrieval.py:214–249`），
每个口径 `status == "timeout"` 就 `break`（`:350–353`），counter 因「剩余预算 < 已观察到的单次成本」被
`can_start()` 跳过（`:288–304`）。30 + 30 + 开销 = 60.65–60.90，8 次锁死在这个区间就是「两次定长超时」
的指纹，不是「检索跑了 61 秒」。

review 给 T120/R20 的「机制地板」过线标准（可见 ∧ elapsed≈61 ∧ 观察里没有超时字样）会被这个空成功**满足**：
观察串是空的、`ok=True`、elapsed 正好 61。按那把尺子跑出来会全绿，然后把地板钉在一个失败模式上。
这和 `CLAUDE.md` 里 `fast_daily_sync` 那条（行数正常、值是空壳、覆盖率审计永远发现不了）是同一个形状。

补一条更重的：**整个 `finance-base-ab/out/` 树的历史上（09-01 起所有 attempt / t-budget / reference-loop / live-probe），
RAG 层一次命中都没有过**（扫描全部 `continuous-episode.json`：kb_search 全部 `tool_timeout` 或「进程已终止」，
evidence_search 全部超时或空成功）。

### F2 · 台架让每个 run 都冷启动 worker——矩阵结构上测不到 RAG

`PersistentRagWorker`（`rag_worker.py:45–`）是 `subprocess.Popen` 起的子进程，stdin/stdout 管道，句柄在
父进程内存 `rag_worker._WORKERS` 里；worker 脚本 `scripts/rag_query_worker.py:97` 是 `for line in sys.stdin`，
父进程一退出它读到 EOF 就退出。`run-budget-matrix.sh:51–60`（以及 `run-budget-open.sh` / `run-t-budget.sh` /
`run-reference-loop.sh` / `compare.sh` / `repeat-live-probe.sh` 同样的块）在 shell 里单独
`python -c "kb_rag.prewarm(...)"`，打印完 JSON 进程退出，worker 跟着死；`rag-prewarm.json` 里的 `state=ready`
是那个已死进程的遗言。每道题新起的 `python -m shape_lib.budget_open_arm` 进程里 `_WORKERS` 是空的，
第一次 kb 查询现场加载 bge-m3，30s 帽必超时，冷 worker 超时处置是「杀」（`_on_query_timeout`，
`rag_worker.py:236–251`：`warm = model_load_count > 0 and healthy()`，冷时直接 `_stop_process()` +
`raise TimeoutError`），下一次又冷——确定性死循环。

证据与代码一致：14 条 kb_search 观察全是「进程已终止」= `kb_rag.py:999–1006` 的 `except TimeoutError` 分支；
热 worker 才会走的「请求已放弃、worker 保留」（`WorkerRequestAbandoned`，`:992–998`）**一条都没有**。
16 个开闸 run 里 worker 一次都没热过。

生产不是这样：8792 是长驻进程，`app.py:2208–2216` 在 lifespan 里 `kb_rag.prewarm(runtime_paths.knowledge_wiki)`
一次，之后所有请求共用热 worker。台架 `kernel.run_via_adapter` 直接调 `_run_conversation_turn` 绕过了 lifespan，
所以要自己补这一步（见第四节）。

结论：矩阵能证明「预算闸清干净后模型能自然收束」（`model_finish` 3→14 是真的），**对 RAG 不能下任何结论**，
包括 review 说的「kb 工人 30s 墙是 RAG 能力上限」（那是台架伪影）和「RAG 修好了也没给时间跑」。

### F2' · 热 worker 也救不了 30s 帽：hybrid 单查询 p50 ≈ 41s，且仍零命中

当晚在同一个进程里 `kb_rag.prewarm` 之后（`state=ready, model_load_count=1`），用矩阵里模型真实发出的
kb_search / evidence_search 检索词逐条跑 `kb_rag.retrieve(k=6, mode="hybrid", timeout=90)`
（`shape_lib/rag_hot_worker_probe.py`；日志 `rag-hot-probe-0904.log`，探针进程在第 17 条后被上面那次
checkpoint 回写连带杀掉，JSON 没落盘，日志是原始读数）：

- n=17：min 22.97s，**p50 41.23s，p95 49.68s**，max 54.01s，mean 40.5s；17/17 > 20s，16/17 > 30s。
- 17/17 `status=empty, hits=0`，`mode=hybrid`（没降 bm25）。

两个推论（第 1 条在「补充 · 更正」里有修正）：
1. `episode_tools.py:910` 的 30s 帽在**今晚这台机器的**热 worker 下也几乎必超时；控制臂 16–23s 的授窗更是结构性不可达。
   但这组数是在 swap 14.4/15.4 GB、两份 bge-m3 挤 16 GB 的条件下量的，大头是换页不是检索（08-31 分段实测检索本身
   3–18s）。它能解释 09-03 生产 66% 超时率的机制是「worker 在请求间被换出」，与 #566/#571 无关。
2. **给足 90s、worker 热、也一个命中都没有**——RAG 空不只是冷启动。为什么空见 `rag-why-empty-0904.json`
   （`require_fresh` 真/假、bm25 对照，本笔记末尾「补充」段）。

### F3 · B6：模型稿要求了澄清，是发布层把它换成了模板——尺子是对的，改尺子会盖住 bug

开闸臂 B6 两次 `outcome.draft`（模型自己写的稿）开头分别是
「**无法执行提纯：卖方材料原文缺失。**…需用户提供原文后才能产出逐条归档结论」和
「直接回答：本轮无法完成具体提纯——对话中没有提供任何卖方材料原文…在拿到材料原文前…故不给出具体条目」，
完全满足 `pass_rule`（要求澄清、指出缺材料、不假装完成）。发布出去的却是同一句 98 字模板
「…现有证据不足，暂不能可靠回答。仍需核验：直接回答用户问题、说明证据覆盖范围、数据日期与缺口。」

路径：`task_frame` 的 LLM 对齐步已经识别出来了——两次 `ambiguities` 分别是
「'这份卖方材料'所指文档完全缺失，需用户提供原文或粘贴内容」和
「'这份卖方材料'具体指哪份：需用户提供材料原文、文件、标题或来源链接，当前上下文中不存在任何可指代的对象…」，
`confidence=0.4`，但 `clarification_question=null`。把 ambiguity 转成澄清问句的是代码侧正则
`task_frame._clarification_for`（`task_frame.py:449–463`），只认「主体|市场|数据源|工具|结论|对象」×
「不明|冲突|改变|可能」，两句都不含 → `None` → `turn_controller.py:1232` 不走 clarify → 研究车道。
模型诚实地在两个 required_outputs 上都声明 gap → `structural.verified_status=partial` 且无 slot 兑现 →
`episode_semantic_verifier.py:921–943` 不放行 → `_gap_answer` 模板。认不出来就放行 = fail open。

判决：不是预算（review 对）、不是输出门（收据错）、也不是尺子（review 错）。按 review 改尺子让「证据不足」
算通过，就把「模型写对了、产品把它扔了」盖住了。修法在第四节。

---

## 2. 两个软伤（结论要降级）

### S1 · 「#566/#571 单上会更差」没有配对证据

f4c 控 vs 2d8 控不是背靠背跑的：2d8 控 10:20–11:24，f4c 控 12:01–12:24（污染重跑之后）。
首轮模型延迟的代理量（第一次 `tool_request.turn_elapsed_at_dispatch`）：

| 臂 | 时段 | 首次派发时刻（≈首轮模型延迟） | 首次实授窗 |
|---|---|---|---|
| 2d8 控 | 10:20–11:24 | mean 13.5s / median 12.0（7.1–39.3） | 16.2s |
| 2d8 开闸（同时段交错） | 10:22–11:27 | mean 12.0s / median 9.7 | 185.4s |
| f4c 控 | 12:01–12:24 | mean 6.9s / median 6.5（3.1–16.9） | 22.8s |

两个 2d8 臂互相一致（配对成立），f4c 中午跑时 GLM 快了一倍。控制臂研究窗只有 30s（90−60），首轮吃 7s 还是
13s 直接决定工具拿到 23s 还是 16s，超时数、修复轮数、`model_finish` 全跟着动。「供应商时段延迟」就能解释全部差异。
收据说的机制（#566 让 kb_search「真的去跑不再快速失败」）事件里也找不到：两个控制臂 kb_search 都是
9/9、10/10 stage 级超时、都把授窗吃满。**这组数据判不了 2d8 与 f4c 谁更好**；「维持 8792 在 f4c」作为保守默认可留，
理由撤回；要判就交错背靠背重跑。

### S2 · 轴级 +6 里有 2 个是同义反复

B4 两次的「点到 evidence_search」轴在控制臂**按构造不可能过**：32/32 控制 run 的第一个 `tool_menu` 事件
都在第一次 `model_turn` 之前发出，`would_grant` 29.59–29.99 < 30（=90−60−开销），`hidden=['evidence_search']`。
不是模型快慢的事，是 90/60 下这个工具从菜单上就不存在。开闸后它出现、模型点了——机制指标，不是能力指标。
剩下 +4 是 B5 ×1、B7 ×3，而 B7 的量能数字在 f4c 控 p2 也拿到两个，本来就在 run 间抖。n=2 下 +4 在噪声内。
更准确的说法是**能力层这次什么都没测出来**，别把 19/28 写进任何结论。

---

## 3. 对 review 五步计划的裁决

| review 的步骤 | 裁决 | 原因 |
|---|---|---|
| 1. 跑 T120 R20 拔保险丝 | **先别跑** | 台架不修跑出来是 61s 空成功，会把地板钉在伪影上（F1/F2） |
| 2. 加 T90 R20 证伪「只降 reserve」 | 同上 | 且预测不准：57s 授窗下 narrow 30s 超时后 broad 被 `can_start` 跳过，会在 ~30s 处「成功」返回空 |
| 3. 先改 B6 尺子 | **不要** | 尺子是对的，改了盖住真 bug（F3） |
| 4. 16 次 kb_search 观察文本做分诊 | 不用 | 14 条全是「进程已终止」= 冷 worker 被杀，根因见 F2 |
| 5. 维持 8792 在 f4c | 结论可留、理由撤回 | S1 |

---

## 4. 当晚已落地（都未提交；生产仓的改动在独立树、独立分支）

1. **台架进程内预热** —— `finance-base-ab/shape_lib/kernel.py`：`run_via_adapter` 在跑题前调
   `prewarm_rag_in_process()`（= `kb_rag.prewarm(default_paths().knowledge_wiki)`，与 `app.py` lifespan 同一步），
   预热耗时不进 latency；预热失败直接 `SystemExit`，不留「跑完了、RAG 其实是死的」读数；臂结果 JSON 新增
   `rag_prewarm` 与 `rag_worker_after_run`（`queries_served` / `timeouts_killed` / `timeouts_abandoned_kept_warm`
   是「这次 RAG 真在热 worker 上跑了几次」的唯一账本）。pi-shape / dsh-shape / reference-loop / live-probe /
   t-budget / budget-open 全部经这一个 seam，一处修全覆盖。`run-budget-matrix.sh` / `run-budget-open.sh` 里
   失效的 shell 预热块已删并留注；其余四个脚本里的同款块（tracked）没动，现在只起「暖一下页缓存」的作用，无害但注释是错的。
2. **对账脚本按载荷判检索** —— `shape_lib/budget_matrix_compare.py`：新增 `rag_calls` / `rag_hits`（evidence 非空）/
   `rag_hollow_success`（ok=True 且载荷空）/ `rag_timeout_killed` / `rag_timeout_abandoned` / `rag_stage_timeout`，
   报告新增 `rag_worker_proof`（读臂结果里的预热证据，没有就打 `COLD-WORKER-MATRIX`）与 `rag_layer_verdict`。
   对本矿阵复算：41 calls / 0 hits / 8 hollow / 14 killed / 19 stage_timeout，两个目录都判 COLD-WORKER-MATRIX。
3. **热 worker 成本探针** —— `shape_lib/rag_hot_worker_probe.py`（用法见文件头）。读数见 F2'。
4. **B6 修在澄清门，不改尺子** —— 生产仓新树 `/Users/a77/fwp-wt-task-frame-clarify`
   @ `fix/task-frame-missing-material-clarify`（基线 `gitea/main=2d8eaea5`，**未提交、未推**）：
   - `task_frame._clarification_for` 增加第三类识别：材料名词（材料|文档|原文|附件|文件|研报|纪要|公告|链接|正文…）×
     缺失状态（缺失|未附|未提供|不存在|需用户提供/粘贴/上传…），且**排除模型自己已给默认处置的句子**
     （含「先按|暂按|默认|假定|假设|按…处理」），命中返回固定问句 `MISSING_MATERIAL_CLARIFICATION`
     （「这题要处理的材料…我这边没有拿到——请把内容贴进来或给出来源链接」）。
   - `resolve_task_frame_clarification`：追问是材料时，回答（贴进来的材料）**不**走主体/市场归一——否则一段研报正文会被
     `_safe_subject` 判掉再默认成「A股市场 / market_pattern」，把提纯题改写成盘面题；主体/类型保留，记 assumption
     「用户在唯一一次澄清中补充了材料原文（约 N 字）」。
   - 测试 `test_task_frame.py` +6（用 B6 两条真实 ambiguity 做正例；「未提供，先按…」「观察窗口未明确」等做反例；
     材料回答保主体；原反弹澄清路径不变）。`test_task_frame.py + test_turn_controller.py` **125 passed**；
     两个变异（删识别分支 / 关 resume 分支）分别只让对应测试变红；ruff 全过。
   - 这是止血。第二条路（让对齐 LLM 直接产出 `clarification_question` 字段、代码只守「有就走澄清车道」）要动
     `align_task_frame` 合同，另开工单。

---

## 5. 下一步（顺序不能反：先让 RAG 在台架里活过来，再谈预算）

1. **零命中已查清**（见「补充」）：整库 stale + `require_fresh=True` 丢光；KB 检出没有 `page_freshness`。
   要么合 KB 仓 `fix/rag-page-level-freshness`（09-03 用户拍「先都不合」，需重新裁决），要么在矩阵里显式接受
   `require_fresh=False` 的探索模式读数并如实标注 degraded——但那不是生产形态。不烧 LLM 配额。
2. **单查询成本先分两层再谈**（见「更正」）：内存层——worker 在请求间被整个换出，每次先付换入成本；算法层——
   检索本身 3–18s（08-31 分段实测）。先做内存层（keepalive 轻查询 + `mmap` + fp16，或者干脆给这台 16 GB 机器减负），
   再在**不换页**的条件下量 p95；`perf/wiki-hybrid-25s` 的 store 复用（load 5s → 0）是算法层现成的一刀。
   量到干净的 p95 之前不要再拧预算闸，也不要再在这台机器上并行起第二个 bge-m3 进程。
3. 有了热 worker 的 p95 再回来算 T/R：授窗 ≥ p95 + 首轮模型延迟（GLM 时段 7–13s），reserve 20 起。
   review 的 T120 R20 / T90 R20 设计可以直接复用，过线标准换成 `rag_hits > 0`。
4. #566/#571 要不要上 8792：把 f4c 控和 2d8 控**交错背靠背**重跑一次再判。
5. B6 分支合并前跑全量 + 交接；第二条路开工单。

---

## 补充（当晚 19:20 后）：热 worker 为什么零命中、时间花在哪

`rag-why-empty-0904.json`（2d8eaea5，同进程预热后 4 条查询）与 `rag-why-empty-0904-f4c03b9a.json`（f4c03b9a 现役，同脚本）：

| 快照 | 查询 | 模式 | `require_fresh` | 墙钟 | 结果 |
|---|---|---|---|---|---|
| 2d8 | 光刻胶 国产替代 KrF ArF 产业链 公司 | hybrid | True（生产默认） | 22.9s | `empty`，**检索到 24 条、全部按 stale 丢弃** |
| 2d8 | 同上 | hybrid | False | 28.6s | 6 命中（南大光电 / 光刻胶 / 南大光电_个股逻辑卡_20260603…），`index_freshness=stale` |
| 2d8 | 光刻胶 | **bm25** | True | **63.6s** | `empty`，18 条全按 stale 丢弃 |
| 2d8 | 固态电池 硫化物 电解质 | hybrid | False | 88.8s | 6 命中（固态电池产业新格局…/ 贝特瑞 / 固态电池深度研究报告） |
| f4c | 光刻胶 国产替代 KrF ArF 产业链 公司 | hybrid | True | **62.2s** | `empty`，24 条全按 stale 丢弃 |

worker 计数：`queries_served=5, timeouts_killed=0, timeouts_abandoned=0` —— 这几次 RAG 是真的在热 worker 上跑完的。

三条事实：

1. **零命中的直接原因是整库新鲜度 verdict = stale，`require_fresh=True` 把每一条命中都丢了**。索引 `built_at=2026-08-31`，
   KB 侧 `store.freshness_report` 判「indexed source files changed（manifest 指纹不一致）」；KB 检出（`main@e4c9a9390`）
   **没有 `page_freshness`**（`hasattr → False`，KB 仓 `fix/rag-page-level-freshness` 未合），所以 2d8 里 #571 的
   `_page_verdicts` 返回空字典、回落到整库 verdict——#571 单独上并没把「kb_search hits=0」修完，这正是 09-03 台账
   那条说的「两张可独立合并」的另一半。`require_fresh=False` 能拿到相关命中，说明索引内容本身是有的。
   与 #566/#571 无关的部分：f4c 上同样 24 条全丢。
2. **每条查询 23–89s 的成本不在 freshness 计算上**（`freshness_report` 直接计时 0.6–0.9s/次），也不在模型加载上（热）。
   索引 169,003 chunks（`meta.json`），BM25 是 `rank_bm25.BM25Okapi`（`skills/lib/rag/retrieval.py:127/207`）；
   纯 bm25 模式一条单词查询 63.6s，说明大头不在稠密侧。**f4c 与 2d8 同样慢（62s vs 23s，方差极大）——#571 没让它变慢**，
   成本在 KB 侧检索路径，`perf/wiki-hybrid-25s` 那棵树是该看的地方。生产 `episode_tools.py:910` 的 30s 帽在这个成本下
   对热 worker 也是必超时。
3. 因此「RAG 送不到一个字节」在生产形态下是**三层叠加**：台架冷启（已修）× 单查询成本 ≫ 30s 帽 × 整库 stale 丢光。
   修掉前一层只会暴露下一层；下一步第 1、2 条（第五节）分别对应后两层，顺序不分先后但**都在预算矩阵之前**。

告警文案里「可恢复：在知识库仓跑 rag_index.py update 重建索引」按 09-03 分析救不回来（一页变了整库又 stale），
2d8 版文案已改、f4c 版还在说 post-commit 会自动重建（钩子已死）。

### 更正（19:50）：23–89s 的大头很可能是内存换出，不是检索算法

上面「成本在 KB 侧检索路径」下得太快。核对两处事实后要改口：

1. **`perf/wiki-hybrid-25s`（08-31，R-20260831-02）已经分段计时过**：预热后单次 hybrid 五段墙钟
   load 5s（worker 每问重读 17 万块索引，该分支用 `IndexReuseCache` 归零）/ freshness 0.2s / encode 0.3s /
   **search 3–18s** / 合计 p50 11.3s → 改后 **p50 12.9s / p95 18.4s**。同一份索引（`built_at=08-31`，169003 chunks），
   同一台机器，检索本身是 3–18s，不是 23–89s。分支未合 main。
2. **今晚这台机器在深度换页**：16 GB 物理内存，`vm.swapusage` **14.4 / 15.4 GB 已用**，`Pages free` ≈ 55 MB，
   load 5–6；8792 的常驻 RAG worker（pid 4665）**RSS 只剩 3.7 MB**——bge-m3 + 346 MB `dense.npy` + chunks 整个被换到磁盘。
   我的探针每次再起一个 worker（又一份模型），两份模型挤 16 GB。所以：今晚 23–89s = 检索 3–18s + 把几 GB 模型/索引从 swap
   换回来；同一条查询 23s 与 62s 的方差就是换页方差；「bm25 单词 63s」也是同一回事（bm25 路径同样要把 store 换回来）。
   `p50 41s / p95 50s` 这组数**只在今晚的内存状态下成立**，不能当 RAG 的算法成本写。

对生产的含义更直接：8792 起来 27.5 小时，readiness 显示 worker `queries_served=1`（预热那次）、
`timeouts_abandoned_kept_warm=1`、`abandoned_in_flight=1`——唯一一次真实 kb 查询超时被放弃。请求之间隔几分钟到几小时，
worker 在两次请求之间被整个换出，下一次查询先付 20–60s 的换入成本，30s 帽必超时；这比「#566/#571」「算法慢」都更能解释
09-03 的 66% 超时率，且与代码版本无关（f4c / 2d8 一样）。

修法因此分两层：**内存层**（让 worker 常驻页不被换出：定时 keepalive 轻查询、`dense.npy` 用 `np.load(mmap_mode="r")`、
模型 fp16、减少同机其他常驻大户；`feat/rag-window-gate-and-worker-keepalive` 那棵树只有名字没有实现）和
**算法层**（合 `perf/wiki-hybrid-25s` 的 store 复用，search 3–18s 再往下压）。量 p95 要在内存不换页的条件下量，
今晚不再起任何新的 bge-m3 进程——再起一个就是在拿生产的稳定性做实验。

## 6. 可迁移的知识点

- **空成功（hollow success）**：`ok=True` 但载荷为空，比报错更危险——报错会触发修复，空成功会被当作「跑完了」。
  判据永远落在载荷上（hits>0 / rows>0 / bytes>0），不落在状态位上。数据管道（`fast_daily_sync`）、HTTP 200 空 body、
  只查不抛异常的 assert，同一形状。liveness ≠ readiness ≠ correctness。
- **冷启动与进程生命周期**：子进程的生命跟着父进程，「预热」只对同一进程有效。凡是「我预热了但为什么还慢」，
  第一问是「预热和使用在同一个进程 / 连接池 / 容器里吗」。Serverless、连接池、模型服务同一道题。
- **配对设计与混杂变量**：两臂不同时段交错跑，任何随时间漂移的东西（供应商延迟、缓存、负载）都会伪装成处理效应。
  矩阵脚本自己写了配对纪律，但只在 2d8 内部执行了，跨快照没有。
- **fail open vs fail closed**：正则认不出来就放行的门是 fail open；识别器越窄漏放越多且静默。设计门时决定「认不出来」
  往哪边倒，把倒向写在注释里。
- **「信息生成了但没送到」**：正确答案在 `outcome.draft` 里，发布层丢了它。排查时逐层对比输入输出
  （模型稿 → 校验器 → 发布稿），不要只看最终输出。
- **测你以为在测的东西**：一个 A/B 台架跑了三天、几十个 run、写了收据和 review，RAG 层从头到尾没送过一个字节，
  没人发现——因为所有读数都是「机制层」的（授窗、菜单、报错数），没有一个读数落在「检索送到了什么」上。
  每个台架至少要有一个**载荷级**的健康读数。
