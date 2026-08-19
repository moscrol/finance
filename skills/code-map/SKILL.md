---
name: code-map
metadata:
  pattern: tool-wrapper
description: 编码任务先查本地代码地图门面，避免空图总览和造轮子。触发词：代码地图、code-map、code-review-graph、deepwiki、造轮子、现有实现。注意：dispatcher 不是 Grok 默认第一步；本 skill 不替代 AGENTS.md 指针。
---

# 本地代码地图

实现或宣称「我们没有 X」之前，先跑门面，不要同时调 DeepWiki MCP 和 CRG MCP 当架构结论。

```bash
python3 scripts/code_map.py query "<问题>"
python3 scripts/code_map.py status --one-line
```

顺序已经写进门面：先设计正门，再结构图，再叙事页。空图会说结构层不可用；不要把空壳写成架构总览。

## 禁止

- 禁止 `code-review-graph init|install`
- 禁止把空图 `get_architecture_overview` 写成架构结论
- 禁止 DeepWiki `generate_wiki` / 对本仓 private index
- 禁止把本仓源码交给 Cognition
- 不要把本 skill 里的话当成第二份能力清单；稳定能力只回写 vault 图谱

## 到达率

跨 harness 主通道是 `AGENTS.md` / `CLAUDE.md` 那一行指针。`.claude/skills/code-map` 软链只是发现根。SessionStart 一行只增强 Claude/Devin。Grok / 子 agent 不保证看得到 hook。

查询契约正文只在 `scripts/code_map.py`，这里不复制。
