# 2026-08-31 Wiki 单次 hybrid ≤25s

台账 `R-20260831-02`（`HARNESS_FIX`）。工单
`docs/superpowers/specs/2026-08-31-wiki-hybrid-25s-workorder.md`（INDEX #21）。
前置：#19 现网 90s 无资格（2/6）；#20 把评测加到 240s 后 L0 6/6，答案对照档 4。
本单只回答：现网 90s 装不下三铲，是因为单次 hybrid 太慢。
树 `perf/wiki-hybrid-25s`，不合 `main`，不切生产。

## 预注册结论

**worker 热路径复用已 load 的 store 之后，预热后单次 hybrid p50=12.9s（门限 ≤25s），
现网 90s 下 L0 6/6。** 不是「三铲无用」。#19 的无资格是当时每问都重读 17 万块索引。

未改 `MAX_TOTAL_SECONDS=90.0`，未改三铲默认，未开 rerank/agentic，未改 BM25-only，
未提交知识库里他人的未提交 wiki。

## 钉死条件

| 项 | 值 |
|---|---|
| as_of | 2026-08-28（最新 daily-agent 导出；不是 2026-07-22） |
| 索引 | 结构版 `.rag_index`，`fresh`，`include_raw=False`，`built_at=2026-08-31T11:01:16Z`，169003 chunks（开工时 stale +2，结构版增量 `reused=169001 embedded=2`） |
| 模式 | `wiki_rag_mode=hybrid` |
| 语义闸 | `ASK_EVIDENCE_JUDGE=off` |
| 预算 | `ASK_WIKI_TOTAL_SECONDS` 未设；评测脚本 `--wiki-seconds 90`。`MAX_TOTAL_SECONDS=90.0` 字面量未改 |
| 题 | 与 #19 同一 6 题 |

## 改前五段墙钟（预热后）

预热 ready 40.5s。收据
`intelligence/eval/runs/20260831T110605Z-wiki-hybrid-25s-baseline.json`。

| 题 | load | freshness | encode | search | 合计 |
|---|---:|---:|---:|---:|---:|
| 液冷服务器现在处于什么阶段 | 5.35 | 0.19 | 0.28 | 7.13 | 12.98 |
| 申菱环境液冷订单落地了没有 | 5.21 | 0.18 | 0.24 | 4.00 | 9.66 |
| 英维克和液冷管路的关系 | 4.20 | 0.18 | 0.23 | 3.20 | 7.83 |
| 玻璃基板和陶瓷基板的区别 | 4.57 | 0.20 | 0.24 | 9.42 | 14.45 |
| 科创50支撑位在哪 | 4.56 | 0.18 | 0.58 | 3.19 | 8.54 |
| 中际旭创和1.6T光模块的关系 | 6.43 | 0.19 | 0.24 | 7.96 | 14.84 |
| **p50 / p95** | 4.89 / 6.43 | 0.19 / 0.21 | 0.24 / 0.58 | 5.57 / 9.42 | **11.32 / 14.84** |

首嫌部分证伪：`rag check`≈19s 是 `stale_report` 全库对照，不是 query 热路径。
`cmd_query` 的 `freshness_report` 在 stat-cache 热了之后只有 ~0.2s。
知识库主树仍脏，git 短路不成立，但 manifest 走了 `file_stat_cache`。

最贵的**可避免**段是每次丢掉的 `RagStore.load`（~5s）：worker 只缓存了
retriever/模型，`cmd_query` 仍每问重读 `chunks.jsonl` + `dense.npy`，然后把新
store 扔掉。search（dense+BM25，3–9s）是检索本身，本单不靠降 k / 改 mode 去砍。

闭环每铲最多 3 次 retrieve（首个非空即停）。9×11s 会顶穿 90s；3×(5+6) 也贴门。
所以即便单次合计已经 ≤25s，仍要拿掉重复 load。

## 改了什么

只动金融仓 worker，知识库仓脚本未改、未提交他人 wiki。

1. `IndexReuseCache`：按 `dense.npy` / `meta.json` / `chunks.jsonl` 的 mtime 复用
   已 load 的 store；任一文件变了必须重载，并清空 retriever 缓存。
2. `freshness_report` **每次仍跑**。不设 TTL，不为了快跳过新鲜度。
3. `_enrich_query_output` 不再用预热时的 `stale_report` 盖掉本轮 CLI
   `index_freshness`。否则索引事后变 stale，`require_fresh` 会把过期命中当正式证据。

单测 `intelligence/tests/test_rag_store_reuse.py`：缓存命中不再调用 loader；
索引 mtime 变了必须重载；freshness 计数仍每问 +1；CLI stale 不被 state=fresh 覆盖。
邻域 `test_rag_worker` / `test_closed_loop_retrieval` / `test_kb_rag` 共 75 过。
未设任何新加速 env。

## 改后五段墙钟（预热后）

预热 ready 42.4s。收据
`intelligence/eval/runs/20260831T111130Z-wiki-hybrid-25s-after.json`。

| 题 | load | freshness | encode | search | 合计 |
|---|---:|---:|---:|---:|---:|
| 液冷服务器现在处于什么阶段 | 0.00 | 0.22 | 0.26 | 11.93 | 12.43 |
| 申菱环境液冷订单落地了没有 | 0.00 | 1.67 | 0.43 | 15.01 | 17.14 |
| 英维克和液冷管路的关系 | 0.00 | 0.25 | 0.59 | 12.43 | 13.28 |
| 玻璃基板和陶瓷基板的区别 | 0.00 | 0.24 | 0.51 | 11.62 | 12.40 |
| 科创50支撑位在哪 | 0.00 | 0.25 | 0.46 | 6.11 | 6.83 |
| 中际旭创和1.6T光模块的关系 | 0.00 | 0.24 | 0.29 | 17.80 | 18.36 |
| **p50 / p95** | 0.00 / 0.00 | 0.25 / 1.67 | 0.45 / 0.59 | 12.18 / 17.80 | **12.86 / 18.36** |

load 归零，证实缓存命中。合计 p50 **12.9s ≤ 25s**，p95 **18.4s ≤ 35s**。
search 比改前基线慢一截（机器争用 / 方差），仍低于门；剩余大头就是检索本身。

## 现网 90s L0 / L1

`--wiki-seconds 90 --phase l0l1`。预热 ready 45.8s。
收据 `intelligence/eval/runs/20260831T112441Z-wiki-aperture-ablation.json`。

| 题 | A2 激活 | narrow | broad | counter | A2 墙钟 |
|---|---|---|---|---|---:|
| 液冷服务器现在处于什么阶段 | 是 | ok | ok | ok | 66.9s |
| 申菱环境液冷订单落地了没有 | 是 | ok | ok | ok | 32.7s |
| 英维克和液冷管路的关系 | 是 | ok | ok | ok | 66.3s |
| 玻璃基板和陶瓷基板的区别 | 是 | ok | ok | timeout | 90.2s |
| 科创50支撑位在哪 | 是 | ok | ok | ok | 16.4s |
| 中际旭创和1.6T光模块的关系 | 是 | ok | ok | ok | 63.0s |

L0 **6/6**（门限 ≥4）。A2 **无** `budget_exhausted`。
玻璃基板的 counter 是 `timeout` 且 `executed=True`，按脚本仍算激活；反方桶为空。
墙钟 p50：A0 10.9s / A1 36.8s / A2 64.6s。#19 轮 2 同口径是 A0 19.3 / A1 88.0 / A2 100.3。

L1（本单不重开 #20 质量对照，只记账）：C +3.833 / K +4.167 / 反方 5/6 /
不挤窗。脚本在 L2 未跑时结论码是 `NO_SIGNIFICANT`，附注「不上线门缺答案分」——
答案对照仍以 #20 档 4 为准。

## 阳性对照

人为把 `.rag_index/meta.json` 的 `built_at` 改到 `2020-01-01T00:00:00Z`（mtime 变，
store 必重载），同一题 `require_fresh=True`：

- 改前：`ok=True`，6 条，`index_freshness=fresh`
- 超龄：`ok=False`，0 条正式命中；丢弃 24 条 `stale`（age=）
- 还原 meta 后：`ok=True`，6 条 fresh；`rag check` 仍 `fresh` / stale=0

没有为了快跳过 freshness。没有靠 `git add` 别人的 wiki。

## 红线核对

- `MAX_TOTAL_SECONDS = 90.0` 未改
- 默认 mode 仍是 hybrid
- 知识库仓无本单提交
- 两仓都不合 main、不切 8792
