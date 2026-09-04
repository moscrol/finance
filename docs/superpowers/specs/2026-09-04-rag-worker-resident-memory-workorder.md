# 2026-09-04 RAG 常驻 worker 内存层工单：请求之间不被换出，先量干净的 p95 再谈任何预算闸

> 可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
> 出处：`docs/verification/2026-09-04-budget-matrix-0904-review.md`（F2' 与「补充 · 更正」两节）。
> 与 `perf/wiki-hybrid-25s`（算法层，未合）并行不冲突；与 KB 仓 `fix/rag-page-level-freshness`（新鲜度层，用户 09-03 拍「先不合」）是不同的层。

## 背景与动机

生产 8792（`f4c03b9a`，09-03 16:14 起）跑了 27.5 小时，`/api/readiness` 的 worker 计数：
`queries_served=1`（预热那次）、`timeouts_abandoned_kept_warm=1`、`abandoned_in_flight=1`——期间唯一一次真实
kb 查询在 30s 帽处被放弃。09-03 的生产读数是 kb_search 66% 以 `tool_timeout` 收场。

当晚这台机器的状态（09-04 19:50，`sysctl vm.swapusage` / `vm_stat` / `ps`）：

| 项 | 值 |
|---|---|
| 物理内存 | 16 GB |
| swap | **14.4 / 15.4 GB 已用**，`Pages free` ≈ 55 MB，load 5–6 |
| 8792 常驻 RAG worker（pid 4665） | **RSS 3.7 MB**，VSZ 454 GB —— bge-m3 + 346 MB `dense.npy` + 169,003 chunks 整个在磁盘上 |

两组实测放在一起看：

- 08-31 `perf/wiki-hybrid-25s`（R-20260831-02）预热后**背靠背**分段计时：load 5s（每问重读索引，该分支归零）/
  freshness 0.2s / encode 0.3s / **search 3–18s**，合计 p50 11–13s。这是检索算法本身的成本。
- 09-04 晚同一份索引、同一台机器、同进程预热后逐条查：**23–89s**，同一条查询两次 23s 与 62s，bm25 单词也 63s。
  差额就是把几 GB 模型/索引从 swap 换回来的时间，方差就是换页方差。

所以「RAG 送不到一个字节」在生产形态下是三层叠加，每层各有各的修法，**修掉一层只会暴露下一层**：

1. 台架冷启（09-04 已修，`finance-base-ab@5e58dc9`）；
2. **内存层**：worker 在两次请求之间被整个换出，下一次先付 20–60s 换入，`episode_tools.py:910` 的 30s 帽必超时 ——**本单**；
3. 新鲜度层：整库 verdict=stale × `require_fresh=True` 把 24 条命中全丢（KB 检出无 `page_freshness`）——用户决策，另一条线。

在 2 没解决之前，任何「抬 30s 帽 / 加 T / 减 reserve」都是在给换页时间买单，而且量出来的 p95 是脏的。

## 目标

1. worker 的常驻集在请求间隔（分钟到小时）内**不被整个换出**，或者换入成本有上界且低于工具窗。
2. 在**不换页**的条件下拿到单次 hybrid 的 p50 / p95（用 `perf/wiki-hybrid-25s` 的 `scripts/profile_wiki_hybrid_phases.py`
   五段口径），作为 `min_window_seconds` 与 T/R 的申报依据。
3. readiness 能直接看见这件事：worker RSS、上次查询墙钟、上次查询距今秒数——不用再靠 `ps` 现场抓。

## 非目标（写死认领，别顺手做）

- ❌ 不抬 `episode_tools.py:910` 的 30s 帽、不改 `for_tier` / reserve / `ASK_TOOL_BATCH_TIMEOUT`（去处：本单第 5 步之后、有干净 p95 再立单）。
- ❌ 不跑预算矩阵 T120/R20、T90/R20（去处：同上；且 RAG 载荷层没通之前跑出来是空成功）。
- ❌ 不合 / 不改 KB 仓新鲜度判据（去处：用户裁决，`fix/rag-page-level-freshness`）。
- ❌ 不为了快跳过 `freshness_report`（08-31 单的红线原样继承）。
- ❌ 量测期间**不在这台 16 GB 机器上起第二个 bge-m3 进程**（09-04 晚探针就是这样把自己和生产一起压进 swap 的）。

## 选项与取舍（先讲清楚再选）

| 选项 | 做什么 | 治什么 | 代价 / 风险 | 判断 |
|---|---|---|---|---|
| A. keepalive 轻查询 | worker 侧后台线程每 N 分钟发一条 `k=1` 查询（与预热同 argv），让模型/索引页保持 active | 请求间被换出 | 每 N 分钟一次 I/O 与 CPU；在 swap 已满的机器上是「按周期把别人换出去」，治症不治本；N 太小抢生产，太大没用 | **先做**，最小改动，可关（默认 off，env 开） |
| B. `dense.npy` / chunks 走 mmap | KB 侧 `RagStore.load` 用 `np.load(mmap_mode="r")`，chunks 不整份驻内存 | 匿名内存 → 文件页；被驱逐后重读文件而不是 swap，且不用先写 swap | KB 仓改动；`search` 首次触页会慢一点；BM25 结构仍在内存 | **第二刀**，长期正解之一 |
| C. 嵌入模型 fp16 / 更小模型 | bge-m3 半精度或换小模型 | 常驻集减半 | 分数分布变、需要重建索引 + 召回对照；换模型是产品级决策 | 立单不在本单做 |
| D. 机器减负 / 加内存 | 停掉同机常驻大户（Devin.app、Virtualization VM 等）或换机 | 一切 | 不是代码；用户的事 | 写进交接，不替用户决定 |
| E. 直接抬帽 | 30s → 60/90s | 症状 | 每次超时多烧一倍窗口，且在换页机器上 60s 也不够 | ❌ 已被 09-04 数据否掉 |

## 步骤

1. **先量再改（零配额）**：写一个只读探针，每 60s 采一次 `ps -o rss= -p <worker pid>`、readiness 的
   `last_latency_ms`、距上次查询秒数，跑 2–4 小时；同时用 `profile_wiki_hybrid_phases.py` 在**只有生产 worker 在跑**
   的时段量 6 题五段（不要再起第二个模型进程：把该脚本改成走 8792 的 worker，或在 8792 停机窗口量）。
   产物：RSS 随时间曲线 + 五段 p50/p95。这一步就能把「换页占几成」量成数字。
2. **A. keepalive**：`intelligence/services/rag_worker.py` `PersistentRagWorker` 加后台线程，`RAG_WORKER_KEEPALIVE_SECONDS`
   （默认 0 = 关）；间隔到且 `_lock` 空闲时发预热同款 `k=1` 查询；计数 `keepalive_sent` / `keepalive_timeouts` 走 `status()`。
   单测：间隔未到不发；锁被占不插队；worker 冷时不发（预热负责）；`close()` 能停线程。
3. **readiness 露出**：`status()` 加 `rss_bytes`（`resource`/`psutil` 或 `ps`）、`last_query_at`、`idle_seconds`；
   `/api/readiness` 原样透出。这是第 1 步探针的正式版。
4. **B. mmap**（KB 仓，单独 PR）：`skills/lib/rag/store.py` `load` 的 `dense.npy` 改 `mmap_mode="r"`，对照 `search`
   首次/稳态耗时与召回逐字节同（同一 query 同一 top-k）。
5. **拿干净 p95 后再回预算**：`min_window_seconds`（kb_search 20 / evidence_search 30）与 `episode_tools.py:910`
   的 30s 帽按「p95 + 首轮模型延迟（GLM 时段 7–13s）」重填，另立单；此时 09-04 review 里的 T120/R20 设计可复用，
   过线标准换成 `rag_hits > 0`（对账脚本已按载荷判：`finance-base-ab/shape_lib/budget_matrix_compare.py`）。

## 验收

- 第 1 步产物存在，RSS 曲线能指出「多久没请求就掉到 <100 MB」。
- 开 keepalive 后：生产 worker 在任意 10 分钟窗内 RSS 不低于加载后的 60%；下一次真实 kb 查询的 `last_latency_ms`
  p95 ≤ 干净五段 p95 × 1.5。
- 生产 kb_search 以 `tool_timeout` 收场的比例从 66% 降到 ≤ 20%（按切换后前 20 次真实调用算，来源 `users/*/runs/*/continuous-episode.json`）。
- 全程零 LLM 配额；未改任何预算数字；`freshness_report` 每问仍跑。

## 红线

- 不切 8792 除非走既定切换仪式（账本 record/check、回滚锚）。
- 量测期间不并行起第二个 bge-m3；不在 swap > 80% 的时段读 p95 当申报值。
- 不改 `MAX_TOTAL_SECONDS` / 三铲默认 / `require_fresh` 默认。
- 台账另立（按 `docs/prediction-ledger.md` 现行编号），不要沿用 `R-20260831-02`（那是算法层的单）。
