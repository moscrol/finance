---
name: task-planner
description: 批量/会话级高风险任务前的「采访」前置（Inversion 反转模式）——在复盘批处理、DuckDB 大回填、开新题材前，先按顺序问清任务类型、范围（日期区间/标的/题材）、数据源、结果落库去向、分支、凭证、无前视、dry-run、缺数处置，把回答合成成 task-plan，经 check_task_plan.py 门控校验通过后才放行抓数/回填/写库，再交给 market-overview / duckdb-backfill / theme-radar / top-gainers-feishu 等下游执行。触发词：批量任务规划、开工前采访、批量回填前先问、开新题材前先问、运行前规划、采访前置、先问后做、task planner、batch plan、回填前先问。注意：仅批量/会话级高风险任务走本 skill；日常单日复盘、单股查询等已有固定流程的不需要。
metadata:
  pattern: inversion
  also: [pipeline]
---

# Task Planner（批量任务前的采访前置 · Inversion）

本仓绝大多数 skill 都是「拿到指令 → 抓数 → 算 → 写库」的**正向流**，靠各自的 dry-run / 三条铁律做软兜底。task-planner 把这个动态**反转**过来：在高风险批量任务动手前，Agent 先当采访者，问清约束再动手——这是全仓唯一的 Inversion 模式 skill，补上方法论里缺的那一块。

它**不是**某条具体管线（那是 market-overview / duckdb-backfill / theme-radar 自己的事），管的是**整批/整个会话级**的约束：这次到底覆盖哪段日期、数据从哪来、结果写飞书还是 DuckDB 还是只读、在哪个分支、凭证齐不齐、要不要先 dry-run——在用户答清前拒绝抓任何数、写任何库。

## 何时用

- **复盘批处理**：一次补多天历史复盘 / 批量重算某段区间。
- **批量回填**：`duckdb-backfill` 大区间补数、fact 表重建、多表同步。
- **开新题材**：`theme-radar` 开一个全新题材、从零搭概念图谱与覆盖。
- 日常单日复盘、单股查询、单次涨幅排行等**已有固定流程与门控的不走本 skill**。

## 不可协商的关卡（硬门，禁止跳过）

> 体例同知识库仓 `disclosure-archive` 的 `--apply` 菱形门、本仓 `opinion-cross` 的复核门：先过门才放行。

1. **采访未完成前，禁止任何抓数/写库动作**：不调 fupanhui / iFinD / AKShare 抓数，不写飞书 Bitable、不写 DuckDB、不跑任何 `--apply` / `sync` / `backfill`。
2. **逐关提问、等回答**：按 `references/interview-questions.md` 的 G1→G8 顺序问，一次一关，拿到答复再进下一关；不要一次抛八段，也不要替用户假设。
3. **答完才合成计划**：把 8 关回答填进 `task-plan`（模板见 `assets/task-plan.schema.json`，或下方 `--template`）。
4. **计划必须过代码门**：
   ```bash
   python3 skills/task-planner/scripts/check_task_plan.py /tmp/task-plan.json
   # exit 0 = 全部门控答全，放行；exit 1 = 有缺项，打印 GATE VIOLATIONS，回去补问
   ```
   退出码非 0 一律视为采访未完成，回到对应关卡补问，**不得绕过**。
5. **用户最终确认**：计划过门后，把它复述给用户拿一次明确「开始」，才进入抓数/写库。

## 流程

```
收到批量任务请求（复盘批处理 / 批量回填 / 开新题材）
  ↓
加载 references/interview-questions.md
  ↓
G1→G8 逐关提问（一次一关，等回答）              ← 关卡：未答完禁止抓数/写库
  ↓
合成 task-plan（assets/ 模板填空）
  ↓
python3 scripts/check_task_plan.py plan.json    ← 关卡：exit 0 才放行
  ↓ (exit 0)
复述计划 → 用户确认「开始」                      ← 关卡：拿到确认才动手
  ↓
按 handoff 交接：market-overview / duckdb-backfill / theme-radar / top-gainers-feishu 执行
（每个下游 skill 仍守自己的 dry-run / 三条铁律 / 无前视；本计划只是上层约束）
  ↓
收尾：按计划落库前先 dry-run 复核、提 PR 不合并（合并等用户确认）
```

## 产物：task-plan

会话内整理的一份 JSON（建议落到 `/tmp/task-plan.json` 便于校验，不入库）。字段与填写说明见 `assets/task-plan.schema.json`；先取空白模板再逐项填：

```bash
python3 skills/task-planner/scripts/check_task_plan.py --template > /tmp/task-plan.json
```

`check_task_plan.py` 校验的不可协商门控（任一缺失/非法即 exit 1）：

| 字段 | 门控含义 |
|---|---|
| `task_id` / `goal` | 这次任务是什么、要达成什么 |
| `task_type` | 复盘批处理 / 批量回填 / 开新题材（决定无前视是否强约束） |
| `scope` | 范围：`date_range`(start+end) 或 `symbols` 或 `themes` 至少一个 |
| `data_source` | 数据来源（fupanhui/ifind/akshare/duckdb/feishu/wiki 非空子集） |
| `target_sink` | 结果去向：飞书 / DuckDB / 只读（显式声明，拒绝隐式写入） |
| `env.branch` | 任务分支（**拒绝 main/master**） |
| `credentials_ready` | 飞书/fupanhui/iFinD 凭证是否就位（bool） |
| `no_lookahead_ack` | 是否确认无前视（bool；复盘批处理/批量回填**必须 true**） |
| `require_dryrun_approval` | 写入前是否 dry-run 复核（bool；写飞书/DuckDB **必须 true**） |
| `skip_rules` / `on_missing_data` | 跳过规则 + 缺数据/异常处置（ask/skip/pending） |
| `handoff` | 交接给哪些下游 skill |

## 与其它 skill 的关系

- **task-planner（本）**：会话/整批级——「这次批量任务的约束」（Inversion，先问后做）。
- **market-overview / duckdb-backfill / theme-radar / top-gainers-feishu**：具体管线级——「这一步怎么抓怎么算怎么写」（各守自己的 dry-run / 三条铁律）。
- 两层递进、可组合；本 skill 在最前面，把下游管线纳入 `handoff` 调度。

## 测试

```bash
# 目录名带连字符，按文件路径直接跑（不走 -m 点号导入）
python3 skills/task-planner/tests/test_check_task_plan.py
# 或装了 pytest：python3 -m pytest skills/task-planner/tests/ -q
```
