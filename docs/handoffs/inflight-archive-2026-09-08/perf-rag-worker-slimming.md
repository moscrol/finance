# perf/rag-worker-slimming（RAG 常驻 worker 瘦身三刀 · 工单 #22）

> **2026-09-05 状态**：三刀全部合入（KB #141 / #142 / #143 → KB `gitea/main@24ef52a22`；金融配套 #587 → `gitea/main@094f67c9`）。
> 生产 8792 于 **2026-09-05 01:43:42 走「重启」（选项一，不换快照）生效**：worker 物理足迹 **7.1 GB → 3.3 GB**，
> 预热 64.7 s → 32.4 s，8 次真实 kb_search **p50 838 ms / p95 1140 ms / 0 超时**（此前生产 66% 撞 30 s 帽）；35 分钟空闲后首查 5.3 s。
> 工单 #22 步骤 1 探针**已跑完**（237 样本 / 02:01:57–06:01:17，产物 `~/.finance-runtime/rag-mem-probe-20260905/`）：4 小时空闲曲线平坦无回胖；
> 补测 **7.2 小时空闲后首查 8.13 s**（09-05 09:46，未超时）。步骤 5（回预算闸）**已立单 #26**（`2026-09-05-retrieval-budget-refill-workorder.md`）。
> **仍未切快照**（选项二要用户说「切」）——#587 的 1.4 GB 与 #577 观测面尚未生效。
> 接手单：`docs/superpowers/specs/2026-09-05-resume-rag-slimming-third-cut-closeout.md`。

工单 `docs/superpowers/specs/2026-09-04-rag-worker-resident-memory-workorder.md`（INDEX #22）。
金融解释器 `.venv-workbench/bin/python`；KB 解释器 `/Users/a77/knowledge-base-private/.rag_venv/bin/python`（生产 worker 用的就是它）。

## 这条线做什么

生产 RAG 常驻 worker（`scripts/rag_query_worker.py` 子进程，加载 KB 仓 `skills/lib/rag/`）足迹 7.3 GB，在 16 GB / swap 满的机器上
请求之间被整个换出，每次查询先付 20–60 s 换入，`episode_tools.py` 的 30 s 帽必超时。工单「内存画像」把选项 B（瘦身）升为主刀，拆三段：

| 刀 | 仓 / PR | 做法 | 省 |
|---|---|---|---|
| dense.npy fp16 只读 memmap | KB #141 | `np.load(mmap_mode="r")`，计算时按块升精度 | 0.7 GB 匿名 → 文件页 |
| BM25 换纯 numpy 倒排 `bm25_csc.*` | KB #142 | (词, 文档) 贡献 build 时算好压成 posting list，query 二分查词 + 切片散加；只读 memmap，不引 scipy | 1.86 GB；打分 3–18 s → ms |
| chunks.jsonl 懒读 `chunk_table.py` | KB #143 | 内存只留行偏移 `[start,end)`（2.7 MB），正文按行 `json.loads` + 4096 行 LRU | 1.4 GB |
| 金融配套：worker 不再整份复制 `store.chunks` | 金融 **#587** | `state["chunks"]` 不再填；enrich 用 `_chunk_by_id` 按 `retriever.row_by_chunk_id` + `retriever.chunks[row]` 现取 top-k 行；索引级字段与块级字段解耦 | 让第三刀在金融侧真省下来（老 worker 会把 169k 行全解析攥着） |

## 读数表

### 合入（金融 #587）

| 项 | 值 |
|---|---|
| 分支尖 | `perf/rag-worker-lazy-chunks@1c6fa9de` → 合 `gitea/main@c6e702a6` = `892a6ec2` → 合 `gitea/main@6cc238df`（PR #588 期间落地）= **`b2284e7f`** |
| diff | `scripts/rag_query_worker.py` +60/−16、`intelligence/tests/test_rag_worker.py` +137；与 #588 零交集 |
| 定向 | `test_rag_worker.py` 44/44 绿 |
| 有前科的红 | `test_agent_review_worker.py::test_worker_shutdown_terminates_reviewer_process_group` 单独跑 **3/3 绿**（0.57–0.61 s）；09-04 那张 7714P/1F 是三个门禁并行、swap 20/21 GB 下的时序假红 |
| 全量门禁 ① | `892a6ec2`：ruff 0；**7715P / 0F / 15S / 1x**，323 s，`dirty=false`；收据 `~/.finance-runtime/test-receipts/20260904T172908Z-892a6ec2.json`，`check_test_receipt.py --expect-revision` 退出码 0（PR 评论 #3340） |
| 全量门禁 ②（main 动了重跑） | `b2284e7f`：ruff 0；**7715P / 0F / 15S / 1x**，299 s，`dirty=false`；收据 `20260904T174103Z-b2284e7f.json`，退出码 0（PR 评论 #3345） |
| 合并 | `conflict-check` clean → `gitea_pr.py merge 587 --yes` → **`gitea/main@094f67c9`**；主树 `--ff-only` 同步；worktree `fwp-wt-rag-worker-lazy-chunks` 与远端分支已删 |

### KB 侧部署核实（只读，2026-09-05 01:27）

| 项 | 值 |
|---|---|
| `skills/lib/rag/` vs `gitea/main@24ef52a22` | `git archive` + `diff -rq` **为空**（逐字节同） |
| 倒排指纹 | `bm25_csc.meta.json.source_fingerprint == meta.json.source_fingerprint` → **True** |
| `store.load_bm25(Path('.rag_index'))` | **`SparseBM25` 25 ms**（走 mmap，没进重建路径） |
| KB 主树 | 本地 `main@e4c9a9390` 落后 `gitea/main` 13 个提交、有他人未提交改动（`.claude/hooks/*`、`AGENTS.md`、entities、ingest queue 等）——**未 pull、未碰**；`skills/lib/rag/` 新代码按惯例只在工作区、不暂存 |

### 生产生效（选项一「重启」，2026-09-05 01:43:42）

| 项 | 重启前（worker pid 4665，老代码，跑 1 天 9 小时） | 重启后（worker pid **71779**，8792 pid **71761**） |
|---|---|---|
| 快照 | `f4c03b9a`（`/Users/a77/finance-workspace-runtime`） | **同一快照**——重启只换进程，不换代码 |
| `ps -o rss` | 3.7 MB（整个在 swap） | 加载 6 s：904 MB；40 s：1.61 GB；55 s：1.28 GB；空闲 2 分钟后 13 MB → 8.8 MB |
| `vmmap --summary` Physical footprint | **7.1 GB**（峰值 8.9） | **3.3 GB**（峰值 3.8）；空闲 3 分钟后 2.5 GB 并稳住（`top` CMPRS 1.5 GB——模型权重进了压缩器而非磁盘 swap） |
| 可写区（Writable regions） | Total 9.4 GB / written 5.3 / swapped_out 7.1 | Total 4.6 GB / written 1.6 / swapped_out 2.8 |
| `prewarm_latency_ms` | 64,747 | **32,364** |
| readiness `checks` | 仅 `market_data_consistency=false`（本线无关，重启前后一样） | 同 |
| `timeouts_abandoned_kept_warm` | 1 / `abandoned_in_flight` 1 | **0 / 0**（7 个真实 run 后仍 0） |
| 机器 swap | 13.0/14.3 GB（91%） | 8.6/10.2 GB → 后又涨到 97%（别的进程） |

**为什么足迹降的比「两刀 2.5 GB」多**：老足迹 7.1 GB 里除了 dense fp32 副本 + `rank_bm25` 的 169k 个 dict，还有它们加载期间的临时对象；新 worker 里 dense / 倒排 / chunks 全是干净文件页（被驱逐后从文件重读、**不进 swap**），可写区只剩 bge-m3 fp32（≈2.5 GB）+ 老 worker 脚本仍会解析的 169k 行 chunk dict。**#587 的 1.4 GB 在生产上还没省**——生产快照的 `rag_query_worker.py` 还是老版；切到 `gitea/main` 尖才生效。

### 工单 #22 步骤 1（探针）

产物目录 `~/.finance-runtime/rag-mem-probe-20260905/`（不入仓）：

| 文件 | 内容 |
|---|---|
| `probe.py` / `samples.csv` | 60 s 一采：`ps rss/vsz`、`vmmap` Physical footprint（峰值）、可写区 resident/swapped、`vm.swapusage`、readiness `rag.counters`。02:01:57 起跑 4 小时（pid 见 `probe.pid`；`samples.first-broken.csv` / `samples.second-1row.csv` 是两次夭折的残片） |
| `run_kb_probe.py` / `kb-cases/q*.json` | 经 8792 `/api/runs`（`scripts/workbench_probe.py`，每题一个探针 user `ragp0905-q1..q6`）发 6 题 kb 向研究题；记 readiness 计数前后差 + `continuous-episode.json` 里 `tool_result.elapsed_ms` |

**真实 kb_search 端到端耗时（8792 进程量到，含 worker 往返；生产 worker 不返回五段分段，`load / freshness / encode / search` 标「未分段」）**：

| 题 | run | kb_search 次数 | `elapsed_ms` | ok | hit_count |
|---|---|---:|---|---|---|
| q1 固态电池上游材料 | `run_20260905_014952_549742` | 2 | 700.1, 401.1 | ✓✓ | 0, 0 |
| q2 铅锌边际变化（第一次） | `run_20260905_015220_411486` | 1 | 1118.6 | ✓ | 0 |
| q2（脚本 bug 重跑） | `run_20260905_015337_590153` | 1 | 609.7 | ✓ | 0 |
| q3 人形机器人灵巧手 | `run_20260905_015456_672893` | 0（模型没选 kb_search） | — | — | — |
| q4 国产算力产业链 | `run_20260905_015601_250702` | 1 | 992.2 | ✓ | 0 |
| q5 低空经济上下游 | `run_20260905_015729_969894` | 2 | 976.5, 405.2 | ✓✓ | 0, 0 |
| q6 光模块 CPO | `run_20260905_015850_546597` | 1 | 1152.2 | ✓ | 0 |

- **N=8：p50 = 838 ms，p95 = 1140 ms，min 401 / max 1152 ms；超时 0**（readiness `queries_served` 1 → 9 逐次对得上）。
- **成立条件**：采样时段 01:49–02:00，机器 swap **89–92%**（> 80%）、load ≈ 3、同机 Docker VM 1.6 GB + Cursor helpers ≈ 3.5 GB、无其他 pytest。**按红线不作申报值**，但它是**脏条件下的上界**——比 30 s 帽低 25 倍以上。每 run 首次查询（前面 60–90 s 空闲）0.7–1.15 s、同 run 第二次 0.4 s：一分钟级空闲的换入代价 ≈ 0.3–0.7 s。
- `hit_count` 全 0：观察文本「wiki-rag 丢弃 24 条非 fresh 命中（新鲜度=stale）」——是工单里的**第三层（新鲜度）**，KB 仓 `fix/rag-page-level-freshness` 用户 09-03 拍「先不合」；本线不碰。检索本身有 24 条命中、快。
- LLM 用量（工单要求写明）：**8 个 run（q1–q6 + q2 重跑 + q7），全走 GLM-5.3 主链（zhipu），每 run 约 3 轮模型调用**；`hit_count=0 < KB_JUDGE_MIN_HITS` 故证据裁判没触发。
- **工单验收第一条「多久没请求 RSS 掉到 <100 MB」**：瘦身后**仍成立且更快**——最后一次查询后 ≈ 2 分钟 RSS 13 MB、3 分钟 8.8 MB（swap 97% 的机器）。区别在于**换出去的东西变了**：老 worker 换出的是 7 GB 匿名页（回来要读 swap），新 worker 可写区只有 1.6 GB written，索引全是文件页（回来读文件、且只读被碰到的页）。RSS 掉到个位数 MB 不再等于「下次要付 20–60 s」。
- **长空闲后首查（q7，02:35:10 发，距上次 kb 查询 35 分钟，发前 worker RSS 12.4 MB、足迹 2.5 GB、swap 86.4%）**：`run_20260905_023510_186425`，kb_search **5,341.6 ms**，ok、未超时、`hit_count` 0（同样是新鲜度丢弃）。即**整个被换出后的首查代价 ≈ 4.5 s**（对照热态 0.4–1.1 s），瘦身前同条件是 20–60 s。查后 RSS 565 MB → 3 分钟后 367 MB。合计 LLM 用量更新为 **8 个 run**（q7 `status=partial`，是 LLM 侧部分完成，与 kb 无关）。

### 4 小时曲线的结论（09-05 09:40 补，探针已跑完；工单 #22 步骤 1 验收）

`samples.csv` 237 个样本，02:01:57 → 06:01:17，60 s 一采，全窗口 `rag_state=ready`：

| 量 | 首 | 末 | min | max |
|---|---|---|---|---|
| `rss_mb` | 13.4 | 11.1 | 5.4 | 565.3（q7 查询瞬间） |
| `footprint_gb` | 2.7 | 2.5 | 2.5 | 2.7 |
| 可写区 resident (GB) | 1.1 | 1.1 | 1.1 | 1.2 |
| 可写区 swapped (GB) | 2.5 | 2.5 | 1.4（q7 换入时） | 2.6 |
| `swap_pct` | 97.0 | 91.4 | 85.9 | 97.1 |

- **空闲期不回胖，也不继续变瘦**：4 小时里足迹恒定 2.5 GB、可写驻留恒定 1.1 GB。老 worker 那种「常驻集自己慢慢长回去、
  然后被整个换出」的形状消失了；`queries_served` 只在 q7 那一刻 9 → 10，其余时间零活动。
- **单次查询的驻留脉冲是个尖峰不是台阶**：q7 把 RSS 打到 565 MB、可写换出从 2.5 → 1.4 GB（换入约 1.1 GB），
  3 分钟内回落到 ~12 MB。**代价按次付、不累积**，这正是「文件页 + 按需解析」相对「匿名页常驻」的行为差别。
- **0 `timeouts_abandoned` / 0 `timeouts_killed` / 0 `recoveries`**，四小时无一次自愈事件。
- **`rss_bytes` / `idle_seconds` / `last_latency_ms` 三列全窗口为空**——这是 #577 的 readiness 观测面，
  它在 `gitea/main` 上但**不在生产快照里**。这三列什么时候有值，就是「快照切了」的机器可判信号。

### 小时级空闲后首查（q8，09-05 09:45:59 发）

发前状态：距上次 kb 查询（q7 02:35）**7 小时 11 分**，worker RSS **6.4 MB**、足迹 2.5 GB（可写区 2.5 GB 已换出、
resident 仅 1.1 GB），机器 swap **90.1%**。产物 `kb-cases/q8.json`，run `run_20260905_094559_238749`。

- kb_search **8,128.1 ms**（`queued_ms` 0.8），**ok、未超时**，`hit_count` 0（同样是新鲜度层丢弃，非检索失败）。
- 查后 worker RSS 6.4 MB → **362 MB**，足迹 2.5 → 2.7 GB；机器 swap 90.1% → 88.9%。
- **空闲时长 → 首查代价的三点曲线**：热态 0.4–1.1 s（间隔秒级）→ 5.34 s（35 分钟）→ **8.13 s（7.2 小时）**。
  次线性、**远未逼近 30 s 帽（3.7 倍余量）**；瘦身前同条件是 20–60 s 必超时。工单 #22「换入成本有上界且低于工具窗」这条目标，
  在脏机器（swap 90%）上也成立。
- LLM 用量：本次 +1 个 run（GLM-5.3，`status=partial`），全线合计 9 个 run。探针脚本加了 `q8` case（不入仓，脚本在 runtime 目录）。

## 决策与被否方案

- **生产走「重启」不走「切」** / 否直接切 `gitea/main` 尖 / 派单口令是「合 #587 + 生产生效」，没有「切」字；切会把 `f4c03b9a..gitea/main` 90+ 个提交（含本单执行者没验过的绝大多数）一起上线，是一次 QC 决策，按接手单必须用户拍。重启只换进程：KB 侧两刀（dense / BM25）立即生效，代价是 #587 那 1.4 GB 暂不省、readiness 没有 #577 的 `rss_bytes / idle_seconds / last_latency_ms`
- **main 动了就重跑全量** / 否「#588 只改文档和 yaml，沿用上一张收据」/ 收据要对准最终落地那棵树，5 分钟换一个不用解释的合并；两张收据读数一致本身也是信息
- **六题经 `/api/runs` 发、接受烧 LLM** / 否 `kb_rag.retrieve` 直连 / 后者的 `rag_worker` 单例在**调用进程内**，从 CLI 调等于再起一个 bge-m3（红线：量测期间不起第二个模型），`intelligence.cli ask` 同理；生产快照没有不经 LLM 的检索路由，只有 `/api/runs`。接手单允许「写明用了几次」
- **五段只报合计** / 否借 `profile_wiki_hybrid_phases.py` 量分段 / 那脚本自己起模型（第二个 bge-m3），或要 8792 停机窗口——两者都超出「重启」授权。生产 worker 的返回里没有分段字段，编不出来就不编
- **探针另起会话** / 否 `nohup … &` / 工具 shell 在命令返回时清整个进程组，`nohup` 拦不住，第一版探针只活了一个采样周期；`subprocess.Popen(start_new_session=True)` 后跨命令存活

## 已验证

- 上面读数表全部（收据路径、PR 评论号、readiness / vmmap / ps 原始读数在本文与 `kb-cases/*.json`）
- 重启后 `/api/health` `healthy`；`workers.active=0` 时重启，无在跑 run 被打断
- 7 个真实 run 全部 `status` 正常结束、`gate_rev` 为生产快照

## 未验证 / 已知边界

- **`#587` 在生产未生效**（快照仍是老 `rag_query_worker.py`）；1.4 GB 那部分要等切快照
- ~~长空闲（小时级）后首查是否仍 < 30 s~~ **已验（09-05 09:46，q8）**：7.2 小时空闲实测 **8.13 s**、未超时。仍未验的是**天级**空闲（隔夜 + 整个白天不查）以及它与 swap > 95% 的叠加
- p95 是 swap 89–92% 下量的；干净条件（swap < 80%）的申报值还没有——这台机器 swap 常年 > 80%，可能要选深夜停掉 Docker / IDE 的窗口
- `_describe_retrieval_degradation`（`agent_research.py`）在 `degraded=True` 来自**新鲜度过滤**时也打「语义检索未生效」——这次 hybrid 明明跑了（`requested==effective==hybrid`），文案误导模型；小修候选，不在本线
- 新 worker 加载 55 s 时可写区已有 2.8 GB `swapped_out`——机器压力大到模型权重一加载完就开始被压缩；这是机器不是代码（工单选项 D）
- KB 主树落后 13 个提交、有他人足迹，未 pull

## 下一步

1. **用户拍「切」**→ 按 `docs/workflows/acceptance-workflow.md` §4 链切五步切到 `gitea/main` 尖（含 #587 + #577）：切前在主树 tip 确认最近一次全量门禁绿；切后 readiness 应露出 `rss_bytes / idle_seconds / last_latency_ms`，worker 可写区应再少 ≈ 1.4 GB
2. ✅ **已立单 #26**（`docs/superpowers/specs/2026-09-05-retrieval-budget-refill-workorder.md`，INDEX 已登记）：`min_window_seconds`（kb_search 20 / evidence_search 30，`research_tool_registry.py:1254`）与 `episode_tools.py:910` 的 30 s 帽按「授窗 ≥ p95 + 首轮模型延迟 7–13 s，reserve 20 起」重填。**该单自带一条阻塞前置**：#22 指定的过线标准 `rag_hits > 0` 在当前生产恒 false（见第 3 条），要用户在「重新裁决新鲜度分支」与「矩阵臂走 `require_fresh=False` 探索模式」之间选一个
3. 新鲜度层：24 条命中全 stale 被丢——用户裁决 `fix/rag-page-level-freshness`（KB 仓）。**它现在卡着 #26 的验收标准**，不再只是「本线不碰」的旁支
4. 选项 C（bge-m3 fp16 / 小模型，剩下最大的 2.5 GB）：产品级决策，另立单
5. ✅ **已完成**：4 小时曲线与 7.2 小时空闲首查的结论已补进上面「读数表」两节；`samples.csv` 列含义见 `probe.py` 头部

## 踩过的坑

- **合并树跑门禁期间 main 又动了**（#588 合入）：按纪律再合一次重跑，两张收据都 7715P/0F；`gitea_pr.py merge` 前 `git fetch` 核 base SHA 不变
- **他人 pytest 并行**：开跑前 `pgrep -f '[P]ython -m pytest|[p]ython -m pytest'`（括号防自匹配；`rg -c` 会数到自己的命令行）；等了 3.5 分钟让另一棵树的全量跑完再起
- **readiness 有任一 check 为 false 就返 503**，`urllib.request.urlopen` 抛 `HTTPError`——body 仍是完整 JSON，`he.read()` 读出来即可；第一版探针因此第一行是 `err:HTTPError`
- **工具 shell 会清后台进程组**：`nohup … &` 起的探针在命令返回时被杀（日志空、无退出码）；改 `Popen(start_new_session=True)`
- **`kb_rag.retrieve` 不是「直连生产 worker」**：`rag_worker` 单例是进程级的，任何新进程调它都会起自己的 bge-m3；要走生产 worker 只能经 8792 HTTP
- **worker 五段耗时拿不到**：生产快照 `rag_query_worker.py` 不返回分段；只有 8792 侧 `tool_result.elapsed_ms`（工具墙钟）与 `kb_rag` 的 `telemetry.latency_ms`
- 探针脚本打印语句引用了改名前的键 → q2 重跑了一次（多烧一个 run），记录以第二次为准、第一次的耗时从 run 目录补抓
