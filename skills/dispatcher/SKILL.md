---
name: dispatcher
metadata:
  pattern: meta
  also: [router]
description: 技能路由器：把一句自然语言请求按触发词匹配到 skills/ 下的 SKILL.md，并附带 intelligence.cli prime 的检索前缀（校准 + 个人库 + 图谱）。当请求像某个技能的活但拿不准是哪一个、想确认某能力是否已有技能、或要给金融问答加 grounding 前缀时用。触发词：路由、哪个 skill、有没有 skill、dispatcher、route。注意：请求已明确对应某技能时直接用该技能；单表查询、单股行情不必经它。
---

# Dispatcher（技能路由器）

harness 会把每个技能的 description 放进上下文，多数请求靠它就能选对技能。本 skill 补两个缺口：
一是 `skills/` 里有一批带副作用的技能（`daily-full-review`、`duckdb-backfill` 等）标了 `disable-model-invocation`，
不在你的技能列表里，路由器能把它们找出来；二是金融问答作答前的检索前缀（`prime`）。

## 什么时候用

- 请求像某个技能的活，但拿不准是哪一个（例：「把 6.24 的复盘补完」→ `daily-full-review` 还是 `duckdb-backfill`）。
- 想确认「我们有没有做 X 的技能」——先路由再回答，不凭印象说没有。
- 金融问答开口前要 grounding：`python3 -m intelligence.cli prime "<问题>"`（只读、可离线、秒级），把返回的校准 / 纠偏原则 / 图谱证据前置到推理里；证据不足就明说缺口。

请求已经明确对应某技能，或只是单表查询、单股行情，直接做，不必经路由。

## 命令

```bash
python3 skills/dispatcher/scripts/route.py "完成6.24的全量复盘"          # 最佳匹配 + 默认附带 prime 前缀
python3 skills/dispatcher/scripts/route.py --show-skill "题材发酵怎么追溯" # 附 SKILL.md 全文
python3 skills/dispatcher/scripts/route.py --json --top 3 "研报搜索"      # 供程序调用
python3 skills/dispatcher/scripts/route.py --list                          # 全部可路由技能及触发词
python3 skills/dispatcher/scripts/route.py --no-prime "..."                # 只路由，不做检索前置
```

匹配三层，优先级从高到低：精确触发词命中 → 触发词子串命中 → description 关键词命中。

## 路由之后

- 匹配到技能：读它的 SKILL.md 按流程执行。标了 `disable-model-invocation` 的技能，提示用户输入 `/<skill>` 手动调用，不要用别的方式复现它的步骤。
- 命中批量 / 高风险关键词（批量、批处理、大回填、全量回补、多天、跨日期、开新题材、新概念图谱）：先走 `task-planner` 采访，通过后再交给匹配到的技能。
- 未匹配：纯数据查询直接读 DuckDB；市场问答先查 DuckDB 再补知识库；新功能需求走 `task-planner`；意图不明就问用户，并列出最相关的 2–3 个技能。

## 维护

- 新技能只要 frontmatter 的 description 里有「触发词：」段就会被自动识别，不用改这里。
- 某技能经常漏匹配，就往它的 description 补触发词；`ifind`、`lib` 是工具库，`dispatcher` 自身不参与路由（见 `route.py` 的 `EXCLUDED`）。
