# 2026-08-30 Wiki 闭环三铲对照

台账 `R-20260830-06`（EVAL_ONLY）。工单
`docs/superpowers/specs/2026-08-30-wiki-aperture-ablation-workorder.md`。
收据 `intelligence/eval/runs/20260830T154622Z-wiki-aperture-ablation.json`。
树 `eval/wiki-aperture-ablation` @ 本报告同批提交。不合 `main`，不切生产。

## 预注册结论

**现网预算撑不满三铲，质量对照无资格。**

不是「三铲没帮助」。6 道题的 A2 都没有把 counter 跑完（`executed=True`），
后铲是 `budget_exhausted`。按工单：后两铲没跑的题整题作废，可用题 0 < 4，
停在 L0，不谈 L1 增益均值，不跑 L2。

| 档 | 是否本轮 |
|---|---|
| 现网预算撑不满三铲，质量对照无资格 | **是** |
| 默认勿吹三铲，考虑默认 narrow 或加预算 | 否（L0 未过，不上这档） |
| 预算够时三铲值得保留 | 否 |
| 检索有/无增量，答案无显著差，保持现状 | 否（L2 未评） |

## 钉死条件

| 项 | 值 |
|---|---|
| as_of | 2026-08-28（最新 daily-agent 导出；不是 2026-07-22） |
| 索引 | 结构版 `KNOWLEDGE_WIKI/.rag_index`（`built_at=2026-08-22T07:36:22Z`） |
| 模式 | `wiki_rag_mode=hybrid` |
| 语义闸 | `ASK_EVIDENCE_JUDGE=off`（三臂同一值，变量只留给三铲） |
| 预热 | `kb_rag.prewarm` 成功：`state=ready`，`model_load_count=1`，53.8s |
| 墙钟 | `retrieve_closed_loop(total_seconds=90)` = 模块 `MAX_TOTAL_SECONDS` |
| 缓存 | 每臂独立 `cache_scope` |

## L0 激活（过不了不准谈后面）

预热后再扫 A2。判据：narrow / broad / counter 各至少一次 `executed=True`，且无
`status=budget_exhausted`。

| 题 | A2 激活 | 原因 | narrow 实跑 | broad 实跑 | counter 实跑 |
|---|---|---|---|---|---|
| 液冷服务器现在处于什么阶段 | 否 | 缺 broad+counter | 3×empty | budget_exhausted | budget_exhausted |
| 申菱环境液冷订单落地了没有 | 否 | 缺 counter | 2×empty | 2×empty + 1 skip | budget_exhausted |
| 英维克和液冷管路的关系 | 否 | 缺 counter | 2×empty | 2×empty + 1 skip | budget_exhausted |
| 玻璃基板和陶瓷基板的区别 | 否 | 缺 counter | 3×empty | 1×empty + 1 skip | budget_exhausted |
| 科创50支撑位在哪 | 否 | 缺 counter | 3×empty | 1×empty + 1 skip | budget_exhausted |
| 中际旭创和1.6T光模块的关系 | 否 | 缺 counter | 2×empty | 3×empty | budget_exhausted |

激活率 **0/6**。可用题 0 → 整单停。

墙钟 p50（记账，不作上线门）：A0 45.8s / A1 107.7s / A2 94.3s。三铲更慢是预期，
但本轮慢的主因是空结果换句，不是后铲在贡献页。

## 为什么检索全空（机制，不是质量分）

hybrid 并不是「库里没页」。17 次检索器告警同一句：

> 丢弃 24 条非 fresh 命中（新鲜度=stale）；formal 证据要求 fresh

`require_fresh=True` 是生产 W 的契约。索引停在 08-22，活库 08-22 之后还在 ingest，
命中被判 stale 后整桶清空，闭环按「空结果换句」最多再打 3 次。三次空查询把 90s
预算吃掉，后铲 `can_start` 失败 → `budget_exhausted`。

这和工单点名的反面教材同形（`remaining budget below observed query cost`），
只是触发物从「冷启动 60s 被当成每查询成本」换成了「stale 清空后的换句烧预算」。
冷启动预热螺丝本轮是生效的（预热 53.8s 后 worker ready；warmup 不计入
`observed_seconds` 的既有单测仍绿）。

## L1 / L2

未做。工单写死：可用 <4 不准进 L1 增益均值、不准进 L2。下面三张表因此为空，
不是「增量 0」。

| L1 预注册项 | 本轮 |
|---|---|
| 后铲增量均值 `\|C_A2−C_A0\|` / `\|K_A2−K_A0\|` | 无资格，不报 |
| 反方出现率 A2 `\|K\|≥1` | 无资格，不报 |
| 挤窗 `mean\|C_A0−C_A2\| > mean\|C_A2−C_A0\|` | 无资格，不报 |
| L2 盲评 A2−A0 | 未跑（无可用题，也无模板答案） |

## 旋钮与默认行为

`ASK_WIKI_APERTURES=narrow|narrow_broad|all`，未设 = `all`。跳过的铲记
`executed=False` / `status=disabled`，不伪装成 `budget_exhausted`。

`intelligence/tests/test_closed_loop_retrieval.py` **21 passed**（含既有接线 +
未设 env 仍调三次 retrieve + `narrow` 只打收窄问句）。默认路径没有为评测加日志。

## 复跑条件（下一轮才能谈质量）

结构版索引重建到 `fresh` 之后，用同一脚本、同一题、同一 `as_of`、闸仍 `off`
再跑。L0 可用 ≥4 才允许写 L1 表和 L2 均值。在此之前任何「三铲更好/更差」都是
把没跑的铲写进质量分。
