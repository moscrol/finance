# 在途交接 · main

更新：2026-08-12 · Claude

## 这个分支做什么

逐层修缮 agent（工具接口/压缩/RAG），已合并并部署。**卡点已定位到根，且最外层
不是代码问题。** 展开见 `docs/handoffs/2026-08-12-tool-interface-and-rag-fixes.md`。

## 当前状态

生产 `code_matches_repo=True rag_runtime=True`。脏文件**全不是本轮的**，别提交别 stash。

**根因：盘面快照与 DuckDB 差一天。**

| 来源 | 值 | 谁用 |
|---|---|---|
| `market_snapshot/` `served_trade_date` | 08-12 | 新鲜度门禁（**要求方**） |
| DuckDB `fact_*_daily` `max(trade_date)` | 08-11 | 结构化查询（**供给方**） |

要求方与供给方读**不同的源** → 每次结构化查询被判「数据仅更新到 08-11，早于
当前所需 08-12」→ 取回的 24–60 条证据全作废 → binding `hashes=0` 全是 gap →
fail-closed 忠实执行 → citations 空 → 不写 retrieval trace → `evidence_bound=0`
→ 「证据不足」。**验收 28 题真值通过 0，这一条单独就能解释。**

## 下一步

1. **跑今天的 daily-full**（需 CDP proxy + 登录态，我做不了）。零代码，先通链路。
2. **加对账门禁**：快照 `served_trade_date` 必须等于 DuckDB `max(trade_date)`。
   现有 `check_market_snapshot_contract.py` 只校验快照自身格式、**不和 DuckDB
   对账**——这个洞让上述失效完全静默。零配额、可变异验证。
3. `deadline_exhausted` 与 `repair_model_unavailable` 是独立问题，等 1/2 后再看。

## 踩过的坑

- **起临时实例做对照必须复刻 `ASK_CONTINUOUS_RUNTIME`**。漏了它我误判成
  「自己造成回归」并回滚了生产——两臂差的不只是代码。
- **双根要分开**：代码根用 cwd/worktree，数据根 `FINANCE_WS` 指主树。
- **`loaded_code_root: None` 只说明从哪加载，不说明何时加载**（canary 跑了 6 天）。
- 工具调用记在 `continuous-episode.json`（300KB+），**不在 trace/stream.jsonl**。
- 变异验证要**先确认真的落盘**，且**删整句别改一半**。

## 未验证 / 已知边界

- **`timeframe` 不进 `information_cutoff` 是刻意的，别去"修"**：cutoff 是「允许知道
  到何时」，timeframe 是「被问哪天」。理由在 `_default_information_cutoff` 注释。
- 回灌 / 拆包 / 降级告知三条**没触发条件**，效果未测，属长尾保险。
- `probe_tool_arguments.py` 用 `capabilities=ALL_TOOLS` **绕过路由**，其
  「87.9% 合法率」只在「工具已授权」前提下成立。
- 组件 4（记忆）/ 5（多 agent）检索源未精读，**不得下结论**。
- `api.app` 导入有副作用；两个大脑目录数据分裂；`agent_review/` 无人读过语义。

## 已验证

全量 4520 passed / 0 failed @ `.venv-workbench/bin/python`，9 道 pre-commit 全过。
生产实测 finance_query 24/24 参数合法（改前 55.9%）。本轮两件已归位：
`probe_tool_arguments.py`（TOOLKIT B）、`check_unread_fields.py`（第 9 道门禁）。
