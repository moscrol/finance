# 2026-08-31 Wiki 单次 hybrid ≤25s 工单

> 可独立分发。执行方无需读聊天记录，本单自带背景、证据路径、步骤、验收与红线。
> 前置：#19 现网 90s 无资格；#20 把评测墙钟加到 240s 后 L0 6/6，答案对照落档 4。本单回答**另一问**：现网 90s 装不下三铲，是因为单次 hybrid 太慢。
> 台账：`R-20260831-02`（`HARNESS_FIX`，分支 `perf/wiki-hybrid-25s`）。金融仓与知识库仓可并行开分支，禁止抢同一文件提交。

## 背景与动机

生产闭环是 narrow → broad → counter，每铲一次 hybrid，总预算钉死
`MAX_TOTAL_SECONDS=90`。#19 轮 2（索引 `fresh`）A2 可用 2/6，警告都是
`remaining budget below observed query cost`。#20 把评测加到 240s：L0 6/6，
A2 墙钟 p50=78.3s（三铲），单铲大约 16–40s。3×40s 必然撑破 90s。

#20 的档 4 是「预算够时答案也没更好」。那不否定「现网该让三铲有机会跑完」——
后铲没跑的 turn 和「跑完但没增益」不是同一件事。本单只把**单次 hybrid** 压到
大约 ≤25s（预热后），让 90s 稳装下三铲。不重开 #20 的质量对照，除非 L0 复跑另说。

形态已定：**先分段计时，再改最贵的那一段**。禁止先改 mode / 先加预算。

## 目标

1. 预热后，对 #19 同一 6 题各打一次 `kb_rag.retrieve(..., mode=hybrid, require_fresh=True)`，报 **load / freshness / encode / search / 合计** 五段墙钟。收据 JSON。
2. 改完后同一测法：单次合计 **p50 ≤25s**，且 **p95 ≤35s**（3×35=105 仍紧；p95 超标必须在报告写清剩哪一段）。
3. 现网 90s、`ASK_WIKI_TOTAL_SECONDS` 未设，复跑 `scripts/run_wiki_aperture_ablation.py --phase l0l1`：L0 可用 **≥4**。这是本单是否及格的产品门。
4. 新鲜度语义不放松：索引真 stale 时，`require_fresh=True` 仍丢非 fresh 命中或按现网 `stale-policy` 告警。禁止「为了快，query 不再判 freshness」。
5. 未设任何新 env 时，既有 closed-loop / kb_rag 单测仍绿。默认 mode 仍是 hybrid。

## 非目标（写死认领）

- ❌ 不改 `MAX_TOTAL_SECONDS = 90.0`，不加长生产 wiki 阶段——那是 #20 明确没做的产品决策。
- ❌ 不重跑 #20 的 L2 盲评，不改三铲默认，不打开 rerank / agentic。
- ❌ 不把「知识库工作区有别人未提交 ingest」当成修复（禁止 `git add` 别人的 wiki）。生产也会脏；要用缓存/失效，不要靠工作区干净。
- ❌ 不切 8792，不合 `main`（金融仓与知识库仓都是）。
- ❌ 不把 BM25-only 或降 k 写成「加速成功」——那是换质量，另开单。
- ❌ 不准用 hash embedder 冒充 hybrid 读数。

## 首嫌（先验证，再动手）

`knowledge-base-private/scripts/rag_index.py` `cmd_query` **每次**都：

1. `RagStore.load`（169001 chunks + `dense.npy`）
2. `store.freshness_report(vault)`（本机 08-31 `rag check` 约 19s）

常驻 worker（`scripts/rag_query_worker.py`）只缓存 `_load_retriever`（模型），
**不缓存 store，也不跳过 freshness**。freshness 在 git 证不了「没变」时会落到
全库 manifest 哈希；知识库主树长期脏，这条慢路径就是现网。

3×19s freshness 已经吃掉 90s 的大半，搜索本身再慢也装不下第三铲。
**先用计时证实或证伪这一段，再改。** 证伪了就往 encode / dense / BM25 / IPC 走，
不要死守这个假设。

允许的修法（择一或组合，改完要有单测）：

- worker 热路径复用已 load 的 store；`dense.npy` / `meta.json` mtime 变了再重载。
- freshness verdict 按索引 mtime + 短 TTL 或 stat-cache 复用；索引重建必须失效。
- 把「git 脏 → 每次全库哈希」从 query 热路径拿掉，改成与 `file_stat_cache` 同级的增量。

## 证据路径

| 文件 | 看什么 |
|---|---|
| `docs/verification/2026-08-30-wiki-aperture-ablation.md` + `20260830T171032Z-wiki-aperture-ablation.json` | #19 轮 2：fresh 后仍 2/6 |
| `docs/verification/2026-08-31-wiki-aperture-budget.md` + `20260831T044047Z-wiki-aperture-ablation.json` | #20：240s 下 A2 p50=78.3s、单铲 16–40s |
| `knowledge-base-private/scripts/rag_index.py` `cmd_query` | 每 query 的 load + `freshness_report` |
| `knowledge-base-private/skills/lib/rag/store.py` `freshness_report` / `_content_freshness` | git 短路失败 → 全库 manifest |
| `scripts/rag_query_worker.py` | 只缓存 retriever，不缓存 store/freshness |
| `intelligence/services/kb_rag.py` `retrieve` / `prewarm` | 金融侧入口；复用勿重造测法 |
| `scripts/run_wiki_aperture_ablation.py` | 90s L0 复跑，闸 `off`，同一 6 题 |

## 步骤

1. 开工三连。金融仓从当前评测树开 `perf/wiki-hybrid-25s`（已含 #19/#20 旋钮与脚本）。知识库若要改代码：主树若脏则另开 worktree，**只 pathspec 自己的文件**。
2. `python3 scripts/claim_ledger_id.py claim --branch perf/wiki-hybrid-25s`（已取 `R-20260831-02`）。
3. 结构版索引须 `rag_index.py check` = `fresh`。不要 `--include-raw`。
4. 预热后对 6 题打 hybrid，写下五段墙钟（改前基线）。没有分段读数不准改。
5. 按最贵一段改。补单测：缓存命中不再全库哈希；索引 mtime 变了必须重判；未设 env 行为与改前一致。
6. 同一 6 题再打五段墙钟（改后）。
7. `ASK_WIKI_TOTAL_SECONDS` 未设、`--wiki-seconds 90`、`--phase l0l1` 复跑。可用 <4 → 本单未完成，禁止写成「三铲无用」。
8. 报告 `docs/verification/2026-08-31-wiki-hybrid-25s.md`。回写 INDEX #21 与台账。推分支，不合 main。

## 验收

- [ ] 改前 / 改后都有五段墙钟 JSON，题与 as_of 与 #19 相同。
- [ ] 改后单次 hybrid p50 ≤25s（预热后）。
- [ ] 90s L0 可用 ≥4；收据里 A2 无 `budget_exhausted` 的题数写进报告。
- [ ] 人为把索引 `built_at` 或源文件改到 stale 时，`require_fresh` 仍不把过期命中当正式证据（阳性对照）。
- [ ] 未设加速相关 env 时既有 `test_closed_loop_retrieval` 与 kb_rag 相关单测绿。
- [ ] 台账已登记；分支已推；两仓都不合 main；pathspec 提交。

## 红线

- 禁 `git add -A`；不合 `main`；不强推。
- 解释器：金融仓 `.venv-workbench`；知识库仓 `.rag_venv`。
- 台账禁手工取号。
- 不提交 `.env` / duckdb / 密钥；不打印 key。
- 不清理、不提交知识库里他人的未提交 wiki/ingest。
