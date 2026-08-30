# 2026-08-30 Wiki 闭环三铲对照

台账 `R-20260830-06`（EVAL_ONLY）。工单
`docs/superpowers/specs/2026-08-30-wiki-aperture-ablation-workorder.md`。
树 `eval/wiki-aperture-ablation`，不合 `main`，不切生产。

| 轮 | 索引 | L0 | 收据 |
|---|---|---|---|
| 1 | 结构版 stale（`built_at=2026-08-22T07:36:22Z`） | 0/6 | `intelligence/eval/runs/20260830T154622Z-wiki-aperture-ablation.json` |
| 2 | 结构版 fresh（`built_at=2026-08-30T16:43:00Z`，169001 chunks，`include_raw=False`） | **2/6** | `intelligence/eval/runs/20260830T171032Z-wiki-aperture-ablation.json` |

## 预注册结论

**现网预算撑不满三铲，质量对照无资格。**

不是「三铲没帮助」。工单写死：可用题 <4 停在 L0，不准写 L1 增益均值，不准跑 L2。
两轮都没过这道门。

| 档 | 轮 1 | 轮 2 |
|---|---|---|
| 现网预算撑不满三铲，质量对照无资格 | **是**（0/6） | **是**（2/6） |
| 默认勿吹三铲，考虑默认 narrow 或加预算 | 否 | 否（L0 未过，不上这档） |
| 预算够时三铲值得保留 | 否 | 否 |
| 检索有/无增量，答案无显著差，保持现状 | 否 | 否（L2 未评） |

轮 2 换了机制，没换结论：stale 清空已经消失，90s 墙钟本身仍撑不满三铲。

## 轮 2：索引 fresh 后同一脚本复跑

钉死条件与轮 1 相同，只换索引新鲜度：

| 项 | 值 |
|---|---|
| as_of | 2026-08-28（最新 daily-agent 导出；不是 2026-07-22） |
| 索引 | 结构版 `.rag_index`，增量 `rag update`：`reused=149383 embedded=19618 removed=26 total=169001`；`check` → `freshness=fresh stale=0`；`include_raw=False` |
| 模式 | `wiki_rag_mode=hybrid` |
| 语义闸 | `ASK_EVIDENCE_JUDGE=off` |
| 预热 | `state=ready`，`model_load_count=1`，44.9s |
| 墙钟 | `retrieve_closed_loop(total_seconds=90)` = `MAX_TOTAL_SECONDS` |
| 缓存 | 每臂独立 `cache_scope` |
| 题 | 与轮 1 同一 6 题 |

### L0 激活

| 题 | A2 激活 | 原因 | narrow | broad | counter | A2 墙钟 |
|---|---|---|---|---|---|---|
| 液冷服务器现在处于什么阶段 | 否 | 缺 counter | ok ×6 | ok ×6 | `budget_exhausted` | 104.2s |
| 申菱环境液冷订单落地了没有 | **是** | — | ok ×6 | ok ×6 | ok ×6 | 76.5s |
| 英维克和液冷管路的关系 | **是** | — | ok ×6 | ok ×6 | ok ×6 | 70.8s |
| 玻璃基板和陶瓷基板的区别 | 否 | 缺 counter | ok ×6 | ok ×6 | `budget_exhausted` | 96.4s |
| 科创50支撑位在哪 | 否 | 缺 broad+counter | timeout ×0 | `budget_exhausted` | `budget_exhausted` | 155.2s |
| 中际旭创和1.6T光模块的关系 | 否 | 缺 broad+counter | ok ×6 | `budget_exhausted` | `budget_exhausted` | 109.7s |

激活率 **2/6**。可用题 2 < 4 → 整单仍停。

墙钟 p50（记账，不作上线门）：A0 **19.3s** / A1 **88.0s** / A2 **100.3s**。
A0 比轮 1 的 45.8s 快一截，因为第一铲现在有命中、不再空结果换句。
A2 的 p50 仍 >90s：后两铲经常还没轮到就被 `can_start` 裁掉。

### 为什么还是撑不满（机制，不是质量分）

收据里 **0 条** stale /「非 fresh」告警。`require_fresh=True` 这轮放行了命中。

4 道未激活题的 A2 警告都是同一句：

> remaining budget below observed query cost

加上科创 50 的 `wiki-rag worker 降级 CLI 后仍超时`。

单铲 hybrid 现在经常 15–20s 就有页（A0 五题如此），但放宽问句更贵：
A1 两铲 p50=88s，贴着 90s 预算。第三铲（counter）只有两题挤进门
（申菱 76.5s、英维克 70.8s）。液冷主题 / 玻璃陶瓷两铲就 96–104s；
中际一铲 110s；科创 50 第一铲直接 timeout。

这不是「库里没页」，是 **现网 90s 总预算 × 当前 hybrid 墙钟** 装不下三铲。
和工单点名的反面教材同形，触发物从「stale 清空后换句」换成了「有命中也烧得太慢」。

### L1 / L2

未做。工单写死：可用 <4 不准进 L1 增益均值、不准进 L2。
脚本虽给两道已激活题算了集合差，**不报均值、不当对照**。下面三张表仍为空，
不是「增量 0」。

| L1 预注册项 | 轮 2 |
|---|---|
| 后铲增量均值 `\|C_A2−C_A0\|` / `\|K_A2−K_A0\|` | 无资格，不报 |
| 反方出现率 A2 `\|K\|≥1` | 无资格，不报 |
| 挤窗 `mean\|C_A0−C_A2\| > mean\|C_A2−C_A0\|` | 无资格，不报 |
| L2 盲评 A2−A0 | 未跑（可用 <4，也无模板答案） |

## 轮 1（索引 stale，2026-08-30 15:46Z）

当时索引 `built_at=2026-08-22T07:36:22Z`，`check` 报指纹不一致。
预热 ready 53.8s。6 题 A2 都没跑完 counter。hybrid 17 次告警
「丢弃 24 条非 fresh 命中」；空结果换句烧光 90s。
墙钟 p50：A0 45.8s / A1 107.7s / A2 94.3s。

那轮的「无资格」成立条件是 stale + `require_fresh`。轮 2 已经拆掉这个条件，
结论仍停在同一档。

## 旋钮与默认行为

`ASK_WIKI_APERTURES=narrow|narrow_broad|all`，未设 = `all`。跳过的铲记
`executed=False` / `status=disabled`，不伪装成 `budget_exhausted`。

`intelligence/tests/test_closed_loop_retrieval.py` **21 passed**（含既有接线 +
未设 env 仍调三次 retrieve + `narrow` 只打收窄问句）。默认路径没有为评测加日志。

## 若还要谈质量

本单变量是三铲，墙钟钉死现网 90s。在这套约束下，档 1 已经是合格交卷。

要再跑出 L1/L2，必须先改约束之一（那就是另一张单，不是本单复跑）：

- 加长生产 `MAX_TOTAL_SECONDS` / wiki 阶段预算，或
- 把单次 hybrid 墙钟压到大约 ≤25s，让三铲稳进 90s

在此之前任何「三铲更好/更差」都是把没跑的铲写进质量分。
