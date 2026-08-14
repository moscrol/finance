# 2026-08-14 题材证据断流 + 新鲜度门禁假绿 — 交接

承接 `agent-memory/20_projects/finance-workspace-private.md` 的 2026-08-14 条目遗留项
「题材证据摄入仍停在 08-04」。**该遗留项的表述本身不准确**，本轮把它拆成了三件独立的事。

一句话：**题材线断流的真因是上游没料（微信抓取从未启动），不是管线故障**；而
`check_kb_freshness.py` 在整个断流期间一直报绿。先修门禁，补数等人解锁。

## 结论：三件事，按可执行性排序

### C1. 需要改代码 — `check_kb_freshness.py` 假绿（建议先做，不依赖任何人）

`scripts/check_kb_freshness.py` 当前输出：

```
知识库证据正常：最新批次 2026-08-14（0 天前），共 4535 篇 source note，阈值 7 天   rc=0
```

**这是假的。** 两个独立缺陷叠加：

1. **mtime 参与取 max**。判定口径是 `wiki/sources/*.md` 取 `max(文件名日期, 文件 mtime)`
   （docstring 明写）。[实测] 没有任何 source 文件名含 `08-14`，最新文件名是
   `disc-cninfo-20260813-*`；那个「0 天前」来自 mtime——08-14 01:17 有一批**文件名日期是
   `2026-04-29`** 的年报 baseline 被重写，mtime 变成今天。
   → **任何一次批量 frontmatter 改写 / git checkout 都能把这个门刷绿**，与是否真有新证据无关。
2. **全库取最大值，不分线**。公告线活着就能盖住题材线断更 11 天（见下方台账）。

建议改法：按 `source_quality`（或至少按 sources 文件名前缀分族）分账各自报龄，
且**不拿 mtime 当新鲜度证据**——文件名日期缺失时应报 `unknown` 而不是回落 mtime。

⚠️ 改完的验收断言要钉**生效值**不是配置值：构造一个「只 touch 老文件、不加新文件」的
场景，断言它**仍然报红**。只跑一次现状然后看见红了就收工，证明不了修好了。

### C2. 立刻可做，不依赖任何人 — RAG 索引增量 update

`.rag_index` 已 stale，且这份 stale **与题材补数无关**——是 08-13/08-14 那批公告和年报
入库造成的。也就是说不用等 C3 解锁，现在 update 就能让 `evidence_search` 看见 08-13 的
公告证据。[实测]

```
$ python3 scripts/rag_index.py stats     # 在 knowledge-base-private 下
  model=bge-m3 built_at=2026-08-13T08:59:16Z dim=1024 chunking_version=rag-chunking-v3
  freshness=stale (indexed source files changed（manifest 指纹不一致，跑 rag update）)
$ python3 scripts/rag_index.py check
  indexed=142004 current=146595 stale=8349 (added=4667 changed=3606 removed=76)
```

**增量足够，不要全量 build。** `update` 按 chunk `id` + `content_hash` 复用旧向量，只重嵌
变更/新增块——8,349 块 vs 全量 146,595 块。策略被索引 meta 锁住（`model` / `dim` /
`chunking_version` / `chunk_profile`），换模型或换维度时它**自己拒绝复用、退回全量 build**
（`skills/lib/rag/store.py:11`，理由是「否则矩阵会被静默污染」），不需要人记得。

⚠️ **并发红线：`RagStore.save()` 是原地非原子写**（`store.py:142`——`chunks.jsonl` 直接
`"w"` 截断后逐行写，再写 `dense.npy` / `meta.json`，没有 tmp+rename）。8792 在线时直接对
`.rag_index` 原地 update，会给它开一个**撕裂读窗口**。[实测：读代码]

安全做法是旁路建好再换目录（`RAG_INDEX_DIR` 同时覆盖读和写，`config.py:26`）：

```zsh
cd /Users/a77/knowledge-base-private
cp -a .rag_index .rag_index.new
RAG_INDEX_DIR="$PWD/.rag_index.new" python3 scripts/rag_index.py update
RAG_INDEX_DIR="$PWD/.rag_index.new" python3 scripts/rag_index.py stats   # 必须 freshness=fresh 才换
mv .rag_index .rag_index.old && mv .rag_index.new .rag_index
```

换目录那一瞬间索引短暂不存在——`kb_rag.py` 对「索引缺失」是**优雅降级**（docstring 明列
no built index 为 unavailability 之一），比撕裂读安全得多。`.rag_index.old` 留着回滚。

### C3. 阻塞在用户 — 微信抓取从未启动，本地没有 08-04 之后的题材原料

**这一步做不了，不是没做。** 题材/卖方线（`broker_research_high`）的上游是微信公众号
「调研纪要miracle」。两条通道**都不出货**：

| 通道 | 状态 | 证据 |
|---|---|---|
| 旧：wechat2rss（:8090 + `~/wechat2rss-data/res.db`） | **已死** | 端口无响应、无进程；`com.finhot.wechat2rss-sync` 在 launchd 里**未加载**（plist 在 `~/Library/LaunchAgents/` 但 `launchctl print` 报 not found）；库内 12 个 feed **全部**冻在 `2026-08-04 16:28`，miracle feed(`3865156629`) 末条 `2026-08-03 22:18` |
| 新：wechat-download-api（:5050，本会话 `wechat-rss` MCP 桥接的就是它） | **活着但零产出** | 进程常驻（08-06 起）、`/api/health` healthy；但 `repo/data/rss.db` 里 **`articles: 0` / `subscriptions: 38`**，库文件 08-06 14:16 后再没写过；订阅 08-02 已迁入（`Mzg2NTE1NjYyOQ==` base64 解出正是旧 feed_id `3865156629`） |

[实测：查表 + 探端口 + launchctl]

**解锁动作（只有用户能做）**：服务带 `/login.html` 与 `/verify.html`，需微信登录态才能抓
（`app.py:223/229`）。访问 `http://127.0.0.1:5050/login.html` 完成登录 → 确认
`sqlite3 ~/wechat-download-api/repo/data/rss.db "select count(*) from articles"` 不再是 0。
「零产出是因为没登录」是[推断]，未实测；也可能是抓取任务从未被调度。**登录后仍为 0
就别硬补，回头查抓取调度。**

原料到位之后才谈得上入库，且入库**不是自动化的**：miracle 那条线的既有工序中间有一道
人工四问复核（挑公告级 L2 硬增量，展望/测算类留 synthesis-only），11 天要逐日做。
工序见 KB 仓 daily-ops 与 `skills/lib/ingest_field_standards.py` 的合规枚举
（`update_type=review_candidate` + `fact_hardness=hard_fact_candidate` + `evidence_layer=L2`
+ `source_quality=broker_research_high`）。**红线：sellside 观点永远不进个股正文**，
只挂 concept_graph / entity_exposures / evidence_index。

## 分线新鲜度台账（本轮实测）

`wiki/relations/evidence_index.json` 按 `source_quality` 分组取 max(`source_date`)：

| 线 | 最新 source_date | 条数 | 状态 |
|---|---|---|---|
| `official_disclosure`（巨潮公告） | **2026-08-13** | 4775 | 活的 |
| `broker_research_high`（卖方/题材） | **2026-08-03** | 1512 | **断流 11 天** |
| `policy_document` | 2026-07-22 | 1 | — |
| `ima_composite` | 2026-06-26 | 5622 | — |
| `curated_research` | 2026-06-24 | 759 | — |
| `theme_radar_deep_dive_report` | 2026-06-07 | 54 | — |

公告线 8/03–8/12 的积压**已经补过了**（KB `92dba8a2`，2026-08-13 10:06，manifest +109、
9 个 review queue）。**别重复补公告线。**

## 已排除的假设（别再查这条）

上一轮 cursor session 怀疑断流是 finance 仓那条
`夜跑 RAG 关闭 + kb-ingest 归档` 改动导致的。**已证否**[实测：读 commit + 脚本]：

- commit `b5e7ad16` 时间是 **2026-08-14 03:19**，比断流（08-03）晚 10 天，不可能是因；
- 它关的是**夜跑分桶时用 wiki RAG**（`--semantic-rag-top-n 0`，避免 3×120s 索引超时），
  关的是「用」不是「摄」；
- 它新增的 `receive_kb_ingest_queue.sh` 明写**只归档进 `wiki/raw`、不 apply、不改 relations**，
  这是设计如此，不是退化。

## 坑

- **`wiki/raw/cross-repo-ingest-queue/2026-08-13/` 里那 8 条是工单不是证据**
  （4 条 `concept_ingest` + 4 条 `disclosure`，status 全 `received`）。KB 侧
  `scripts/kb_ingest_queue.py` 子命令只有 `validate/preview/receive/mark/receipt`——
  **没有 apply**，`mark` 明写「人工处置后回写状态」。它本来就不会自己变成证据，
  别当成「管线卡住了」去修。
- 补完题材线之后 **RAG 要再 update 一次**，否则 `evidence_search` 看不见新料。
- 「证据新鲜度」在两层含义不同：库级门禁（`check_kb_freshness.py`）说 08-14，
  运行时答案绑定的证据最大日期是 08-04。**以后者为准**，前者现在是坏的（见 C1）。

## 复核命令

```zsh
# 分线新鲜度（唯一可信的库级口径）
python3 - <<'EOF'
import json, collections, pathlib
d = json.loads(pathlib.Path("/Users/a77/knowledge-base-private/wiki/relations/evidence_index.json").read_text())
items = [x for v in d.values() if isinstance(v, list) for x in v if isinstance(x, dict)]
by = collections.defaultdict(list)
for it in items:
    sd = str(it.get("source_date") or "")[:10]
    if sd: by[str(it.get("source_quality") or "?")].append(sd)
for q, ds in sorted(by.items(), key=lambda kv: max(kv[1]), reverse=True):
    print(f"{q:32s} max={max(ds)} n={len(ds)}")
EOF

# 上游是否出货
sqlite3 ~/wechat-download-api/repo/data/rss.db "select count(*) from articles;"   # 期望 >0
curl -fsS http://127.0.0.1:5050/api/health

# 索引陈旧量
cd /Users/a77/knowledge-base-private && python3 scripts/rag_index.py check
```
