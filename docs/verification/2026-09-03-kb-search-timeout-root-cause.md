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

KB 索引建于 2026-08-31 19:27，知识库仓已前移。修复后那两次查询虽然完成，
但 24 条命中全被 `require_fresh=True` 判 stale 丢掉、`hits=0` / `ok=False`。

**`kb_search` 就算不超时，现在也拿不到证据。** 需要重建索引，另立单。

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
