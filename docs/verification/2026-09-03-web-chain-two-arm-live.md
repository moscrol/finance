# 库里没有的题跑两臂：web 链路 live 首读（2026-09-03，快照 `8864e92d2592`）

能力放大线交接「下一步 ①」。题：**「2024年腾讯控股全年营业收入是多少亿元？」**——港股，`financial_data` 只认 A 股六位代码、
KB 无该数，本地一手链为空，答案只能从 web 来。真值 6602.57 亿元（腾讯 2025-03-19 业绩公告）。
配方：`finance-base-ab/run-reference-loop.sh`，`SHAPE_SNAPSHOT_OVERRIDE` 指含 `web_search` 修复（PR #553）的干净快照，
`SHAPE_QUESTION_FILE` 换题不覆盖茅台参考题。产物 `finance-base-ab/out/reference-loop-0903b-web/`。

**先说前提**：这份读数在 #553 之前跑不出来——`web_search` 那一环此前返回的是 Bing 缓存壳
（`docs/verification/2026-09-03-web-search-bing-rdr-shell.md`）。

## 1. 两臂硬门

| 项 | Episode | 参考 loop |
|---|---|---|
| `source_revision` | `8864e92d` | `8864e92d` |
| `task_frame_hash` | 同 | 同 |
| 首轮 `input_tokens` | 13658 | **13658**（#542 摘 task_id 后 ±3 门第一次真过） |
| `served_models` | glm-5.3 ×3 | glm-5.3 ×2 |
| `question_type` / tier | `general_finance_qa` / standard | 同 |
| 授权集 | market_data, news_search, memory_lookup, kb_search, web_search, web_fetch, finance_query, evidence_search（无 financial_data / l3_lookup：非 A 股主体） | 同 |

`compare.json` 的 hard_failure「首轮缺 `financial_data`」是茅台题专用门，对本题不适用，忽略。

## 2. 两臂发生了什么（一手事件）

**参考 loop**（66.8s，`model_finish`）：
1. 菜单 `would_grant 29.7`，藏 `evidence_search`（要 30）。
2. 模型点 `web_search`（「腾讯控股 2024年 全年 营业收入 年报 亿元」）+ `kb_search`。
3. `web_search` → `bing_web success; no rdr redirect; results stable`，5 条（亿欧 / 36氪 / 腾讯官方公告 PDF / Reportify / 头条）。
4. `kb_search` → **`tool_timeout`**（授 23.6s）。
5. 第二轮菜单 `would_grant 0.0`，模型不再点工具，直接写。
6. **答 6602.57 亿元**，正文自标「公开网页/媒体报道…属高一致性二手材料而非公告一手核验」。

**Episode**（78.1s，`repair_model_stop`）：
1. 菜单 `would_grant 29.5`，同上。
2. 模型点 `news_search` + `kb_search`（没点 web）。
3. `news_search` → 东财标题检索 6 条，全是 09-01～09-03 回购/南向资金新闻，与年报无关。
4. `kb_search` → **`tool_timeout`**（授 23.6s，派发时 remaining 83.6）。
5. 第二轮菜单 `would_grant 0.0`：藏 `kb_search` / `evidence_search`，**`web_search` 仍可见**（无 `min_window_seconds`）。
6. 模型点 `web_search`（查询词「腾讯控股 2024年 全年 总收入 **6602亿元** 年报」——它知道答案、想核实）→ **授 0.0s → 立即 `tool_timeout`**（派发时 remaining 50.6 < reserve 60）。
7. `deadline_exhausted` → 修复轮一次（无工具）→ 诚实弃权：「本轮无法给出已核验的精确数字…不把外部记忆中的数字当作已核验事实输出」。

## 3. 判官对 `public_web` 句的处置（交接问的第二件事）

参考臂 5 条证据全部 `evidence_tier=public_web`（`web_search`）。`direct_answer` 绑定 5 个 hash、`basis=evidence`；
`semantic_verifier.judge_status=repaired`，`rejected_claim_indexes=[]`，公开稿 = 草稿去掉两个空行——**一句没删**。
判官列了 4 条 issue，都是**标注不是删除**：「同比约 8%」证据里没有；「2024 财年（1–12 月）」扩写；「IFRS 确认」证据未给口径；
「用户任务框架默认按 A 股理解」编造用户前提。四条全是真问题（其中 8% 恰好是真的，但证据里确实没有）。

**结论**：当前判官对 `public_web` 不是「整片删」，是放行 + 文字 issue。P2「先量后改」的第一步（issue 结构化落盘）有对象了：
今天的 issue 是「第 N 句…」自由文本，没有 `bound_evidence_ids` / `source_tier` 字段可统计。

## 4. 这一轮钉下的结构性事实（不写量级）

1. **web 链路端到端能通**：`web_search`（修后）→ 模型从 snippet 取数 → `admit_finish` 绑定 `public_web` 证据 → 判官放行 → 发布正确数字。
2. **`web_fetch` 两臂零调用**：snippet 里就有 6602.57，模型不需要取页。`web_fetch` 环节仍无 live 读数。
3. **`kb_search` 2/2 超时**：worker 刚 `prewarm` 成功（48.1s，`state=ready`）后的第一次真实查询仍超 23.6s。这不是「worker failed」，是「worker ready 但首查慢」——交接 ② 「worker failed → 藏 RAG」按今天的形状**不会触发**。
4. **零授予实锤**：第二轮 `would_grant=0` 时 `web_search` 因无地板仍在菜单上，模型点了、拿 0 秒、白烧一轮。这就是交接「不要做」里写的那个「另一个决定」（`would_grant<1s` 时无地板工具照旧可见）在 live 上的样子。
5. **弃权的样子**：Episode 臂模型查询词里写着 6602 亿却拒绝输出——「正确但无用」的第二种成因（预算），茅台题是第一种（授权）。
6. `as_of` 取页面日期的风险实锤一例：一条证据 `source_date=2026-03-19`（2025-03-19 的报道，页面日期解析错）。

## 5. 不成立的结论

- **不能读成「参考 loop 比 Episode 强」**：两臂唯一分叉是首轮模型选 `web_search` 还是 `news_search`，n=1 就是采样噪声。要读 loop 差得多题多次，且按 spec §3.5.3 拆四项。
- 不能读 66.8s vs 78.1s 的速度。
- 「判官不删 public_web」只在这一道题、一次判官调用上成立；P2 要在题集上量占比。
- kb_search 2/2 超时不足以说保活（#545）无效——`counters` 在臂进程内，退出后不可见，本轮没有读到保活账。

## 6. 回滚 / 复现

- 快照树 `~/.finance-runtime/finance-workspace-8864e92d2592`（detached），8792 **未切**。
- 复跑：`SHAPE_SNAPSHOT_OVERRIDE=… SHAPE_OUT_NAME=<新名> SHAPE_QUESTION_FILE=finance-base-ab/question-web-tencent.txt bash run-reference-loop.sh episode|reference-loop|compare`。
- 两臂 run_id：Episode `run_20260903_142417_573363`，参考 loop `run_20260903_143017_006894`（`out/reference-loop-0903b-web/users/…`）。
