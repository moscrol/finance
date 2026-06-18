# Task Planner 采访清单（G1→G8，逐关问）

> 用法：在批量/会话级高风险任务（复盘批处理 / 批量回填 / 开新题材）动手前，按本清单**一次一关**地问用户，拿到答复再进下一关；**全部答完前不抓任何数、不写任何库**。每关末尾标注它最终落到 task-plan 的哪个字段——所有字段都要进 `check_task_plan.py` 的代码门。

不要一次把八关全抛出去，也不要替用户假设默认值（尤其是 `target_sink` 写哪、`branch`、凭证、无前视）。用户含糊时追问到能填进 JSON 为止。

---

## G1 · 这次到底要干什么（task_id / goal / task_type）

- 一句话目标是什么？（→ `goal`）
- 给这次任务起个短标识（便于留痕，如 `backfill-20260601-0615`）。（→ `task_id`）
- 属于哪类？**复盘批处理 / 批量回填 / 开新题材** 三选一。（→ `task_type`）
  - 复盘批处理：补/重算多天复盘。
  - 批量回填：duckdb 大区间补数、fact 重建、多表同步。
  - 开新题材：theme-radar 从零搭一个新题材。

## G2 · 范围（scope）

至少给一个，能给多个更好：

- **日期区间**：start / end 各是哪天？（→ `scope.date_range.start` + `.end`，两个都要）
- 或**标的清单**：具体哪些代码？（→ `scope.symbols`）
- 或**题材清单**：哪些题材/板块？（→ `scope.themes`）

> 提醒：区间越大风险越高。若区间很长，建议先跑一个小 `pilot` 子区间验证再放量（写进 goal 或 skip_rules 备注）。

## G3 · 数据从哪来（data_source）

这次会用到哪些数据源？（可多选，→ `data_source`，取值 `fupanhui` / `ifind` / `akshare` / `duckdb` / `feishu` / `wiki`）

> 提醒：fupanhui / iFinD / 飞书 都依赖凭证（见 G6）；本机 `shared` 软链断时这些跑不起来。

## G4 · 结果落到哪（target_sink）

结果写到哪？**单选**，必须显式：（→ `target_sink`）

- `feishu`：写飞书 Bitable / 电子表格。
- `duckdb`：写本地 `db/market.duckdb`。
- `readonly`：只读分析、只产报告/图表，不落任何库。

> 拒绝隐式写入：不允许"先跑跑看再说"。写 `feishu`/`duckdb` 会触发 G8 的 dry-run 强约束。

## G5 · 在哪个分支做（env.branch）

- 这次开哪个任务分支？（→ `env.branch`）
- **拒绝 `main` / `master`**：大任务必须开 `<type>/<short-task>` 分支（CLAUDE.md 强制）。

## G6 · 凭证齐不齐（credentials_ready）

- 飞书 / fupanhui / iFinD 用到的凭证、token、`shared` 软链是否都就位、能跑？（→ `credentials_ready`，bool）
- 若否：要么先解决凭证，要么把 `target_sink` 降为 `readonly` 走能跑的部分。

## G7 · 无前视确认（no_lookahead_ack）

- 是否确认整个流程**只用 D0 及以前的数据、绝不引用未来数据**？（→ `no_lookahead_ack`，bool）
- **复盘批处理 / 批量回填必须为 true**（涉及历史区间，前视=作弊）；开新题材若不涉时序可据实填，但仍建议确认。

## G8 · 异常与交接（require_dryrun_approval / skip_rules / on_missing_data / handoff）

- **dry-run**：落库前要不要先 dry-run 给你复核？（→ `require_dryrun_approval`，bool；写 `feishu`/`duckdb` 必须 true）
- **跳过规则**：哪些日期/标的/题材跳过？停牌、ST、节假日怎么处理？（→ `skip_rules`，列表，可空）
- **缺数据处置**：遇到缺数据/接口异常怎么办——`ask`（停下问你）/ `skip`（跳过记账）/ `pending`（标记待补）？（→ `on_missing_data`）
- **交接**：这份计划过门后交给哪些下游 skill 执行？（→ `handoff`，如 `["duckdb-backfill"]`、`["market-overview","advancers-chart"]`、`["theme-radar"]`）

---

## 答完之后

1. 用 `--template` 取空白 JSON，把 G1→G8 的回答逐项填进去。
2. 跑 `python3 skills/task-planner/scripts/check_task_plan.py /tmp/task-plan.json`，exit 0 才算采访完成。
3. 把计划复述给用户、拿一次明确「开始」，再进入 handoff 执行。
