# kb_search 超时的根因：except 子句顺序把两个超时处置器变成了死代码

日期 2026-09-03 · 树 `/Users/a77/fwp-wt-rag-abandon` · 部署快照 `f4c03b9a`（8792 当时的生效版）

## 结论先写

`kb_search` 66% 以 `tool_timeout` 收场，**不是** RAG 慢、不是预热形状不对、也不是 30s 工具窗太小。
是 `kb_rag.retrieve` 里 except 子句的顺序：

```
except (RuntimeError, OSError, json.JSONDecodeError)   ← 先匹配
except rag_worker.WorkerRequestAbandoned               ← 永远到不了
except TimeoutError                                    ← 永远到不了
```

`WorkerRequestAbandoned` 继承 `TimeoutError` → `OSError`，Python 按顺序匹配，
后两条是**死代码**。超时因此被判成 `persistent_worker_unavailable`，回退去起一个新 CLI
子进程、用 `timeout − 已耗` 的残窗重新加载 4.3G 模型 —— 必然二次超时。

`#544/#545` 保活省下的重载成本，在调用方当场被烧掉；对外报的还是"worker 不可用"，
而 readiness 上它明明 `state=ready`。

## 三条读数

**一、生产 8792（切流 0903e 后约一小时，`/api/readiness`）**

```json
{"state":"ready","model_load_count":1,"prewarm_latency_ms":64747,
 "counters":{"queries_served":1,"timeouts_abandoned_kept_warm":1,"timeouts_killed":0},
 "abandoned_in_flight":1}
```

`queries_served=1` 是预热那一次。即：**切流后常驻 worker 服务过的唯一一次真实查询，
就是被放弃的那次。**

**二、`probe_tool.py kb_search --repeat 2 --timeout 120`（修复前，快照 f4c03b9a）**

```
[1/2]  30.20s  status=error  → 降级 CLI 后仍超时；fallback_reason=persistent_worker_unavailable
[2/2]  30.20s  status=error  → 同上
```

给 120s 预算只拿到 30s —— `episode_tools.py` 的 `timeout=min(timeout, 30.0)` 硬顶。
两次读数一模一样、热不起来：每次都在烧 CLI 重载。

**三、修复后，同机同索引，先预热再按 `retrieve_kb` 的同一组参数（k=6 / hybrid / excerpt 240）连查**

```
prewarm            42.05s  state=ready model_load_count=1
query[1] k=6       11.93s  protocol=persistent_worker
query[2] k=6       13.58s  protocol=persistent_worker
counters: queries_served=3, timeouts_abandoned_kept_warm=0, timeouts_killed=0
```

## 因此被撤回的两条推断

1. **「预热后首查仍慢，要在预热后真查一次热身 / 藏 RAG N 秒」** —— 撤回。
   `kb_rag.prewarm` 本来就发真查询（`query "Workbench RAG 预热" --k 1 --mode hybrid`）；
   而修复后**第一次**生产形状查询就是 11.93s，没有藏在模型加载之外的一次性成本。
   30s 窗够用，`--k 1` 的预热形状也够用。

2. **「臂和预热不在同一进程」** —— 证伪。`run-reference-loop.sh` 直接起
   `$PYTHON -m shape_lib.reference_loop_arm`，臂就是自己的进程、自己预热，同进程。
   probe_tool 三次全 30s 是因为它**不预热**：冷 worker 模型加载 50–145s > 30s 窗，
   永远加载不完就被杀，下一次又从冷开始。

3. `scripts/probe_tool.py` docstring 引的 `research_owner.py:65`「即使 BGE-m3 已预热，
   首次真实查询仍要约 28s」—— **该文件在 main 上已不存在**，这条出处查不到，未采信。
   （仓里其它处的 28s 指的是中转 provider 的 P50，不是 RAG。）

## 顺带查到，不在本次修复范围

KB 索引建于 2026-08-31 19:01（`.rag_index/meta.json` 的 `built_at`；目录 mtime 19:27
是 BM25 落盘时间，本文前一版写的 19:27 是这个口径混了）。修复后那两次查询虽然完成，
但 24 条命中全被 `require_fresh=True` 判 stale 丢掉、`hits=0` / `ok=False`。

**`kb_search` 就算不超时，现在也拿不到证据。** 但 ~~需要重建索引，另立单~~ 这个判断是错的
——重建索引救不回来，见下。

### 更正（2026-09-03 复核）：这不是「索引该重建了」，是两个独立缺陷

**① 门的粒度错，不是索引太旧。** `index_freshness` 是 `RagStore.freshness_report` 给的
**整库**结论：manifest 把全部入索引文件的哈希揉成一个指纹，任何一个文件增删改，整库判
stale，于是每条命中都被盖上 stale、被 `require_fresh` 逐条丢光。实测（对着索引自己的
建索引期哈希比，`file_stat_cache.jsonl`）：**14412 个入索引文件里只有 35 个改了内容、
2 个新增，合计 0.26%**；另外 **99.74% 的页逐字节相同**，却被那 0.26% 连坐。

> 交接前一版写的「已提交改 132 个 + 未提交 47 个 ≈ 20497 的 1%」是 `git diff wiki/`
> 数出来的，分母和分子都不对：`include_raw=False`，`wiki/raw/`、`log.md` 这些根本不进
> 索引。真实口径是 14412 分之 37。

真实查询验证（`中国船舶 造船 军工`，k=12，真索引真 vault）：**修前 12 条全 stale 全丢；
修后 11 fresh / 1 stale**，那 1 条正是真改过的 `wiki/entities/中国船舶.md`。

**② 就算重建了索引，热路径也不会变。** `kb_search` 的热路径是常驻 worker
（`scripts/rag_query_worker.py`，在**本仓**不在 KB 仓）。它在预热时算一次整库 verdict
存进 `state["freshness"]`，之后每条命中都盖这个值，**且再也不重算**——`cached_loader`
命中缓存后那段代码不会再执行。所以 `rag update` 跑完，不重启 worker，命中照样标 stale。
它还用的是 `stale_report` 而不是 `freshness_report`——那是 KB 早已收敛掉的第二套并行
判据，重切整库 14k 文件，且不判 `chunk_profile` 与索引年龄。

**③ 自动重建早就死了，告警文案在说假话。** `require_fresh` 丢弃时给的补救提示是
「在知识库仓提交改动后 post-commit 会自动重建索引，届时这些证据即可进入」
（`kb_rag.py:1269`）。实际：`/tmp/kb_rag_update.log` 显示 08-19 之前每次一分钟内
`exit=0`；**08-22 起五次启动（08-22×2 / 08-27 / 08-31 / 09-01）没有一次记到 exit**。
09-01 00:44 那次死时没跑 `trap ... EXIT`（说明是被 SIGKILL，不是正常退出），
`/tmp/kb_rag_update.lock` 残留至今、无对应进程、机器 29 天未重启，之后每次 post-commit
都在 `mkdir "$LOCK"` 上静默退出。

**修复**（两张 PR，可独立合并、顺序无关）：
- KB 仓 `fix/rag-page-level-freshness` — 新增 `RagStore.page_freshness`，把整库一票否决
  收窄到每页；`chunk_profile`/年龄两道整库门原样保留，拿不到参照系一律 unknown 绝不发
  fresh。218 条测试绿，4 个变异各自证伪。
- 本仓 `fix/rag-worker-page-freshness` — worker 每次请求按页现算（同时解掉「重建后不
  重启不生效」），整库兜底 verdict 改走 KB 单一事实源。26 条绿 + `intelligence/tests`
  6860 passed，4 个变异各自证伪。

`kb_rag.py` 的 `require_fresh` 一行未动——它的语义正好从「库里有页变了就全丢」变成
「这一页变了才不作证据」。那句已成假话的补救文案仍需修，见下一节。

## 可迁移

- **专用异常处置器排在宽子句之后 = 死代码**，而且症状会伪装成「下游那条路太慢」。
  写「先试快的、失败降级到慢的」这类结构时，降级分支捕的异常集合必须与上游**实际会抛**的
  类型逐个对过 —— 尤其当上游新增了一个继承自内建异常的自定义类。
- **两层各自自洽、靠异常类型传话，中间没有对账**：保活层的「放弃但保温」与调用层的
  「worker 不可用」是两个词表，继承关系让它们静默串线。这一条与
  `2026-08-26` 的 sw_l1 撞名、`fix-episode-slot-fill-numbers` 的读口错位同族。
- **诊断顺序**：先读运行时 counters（免费、且是生产真值），再上探针。本次
  `queries_served=1 / abandoned=1` 一条就把「worker 从没成功服务过」钉死了，
  比跑探针快得多也准得多。
