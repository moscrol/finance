---
name: dispatcher
metadata:
  pattern: meta
  also: [router]
description: 金融 Agent 顶层路由器——每个新 session 的第一步。接收用户输入，自动扫描 skills/ 目录下所有 SKILL.md 的触发词，匹配最佳 skill 并加载其流程。解决"skill 明明存在但 agent 没用"的问题。触发词：所有请求默认经过本 dispatcher；不需要显式触发。
---

# Dispatcher（顶层路由器）

## 为什么需要这个

2026-06-24 教训：用户说"完成全量复盘"，agent 没有去找 `skills/daily-full-review/SKILL.md`，
而是手动逐步跑 sync 命令，踩了 12 个坑（参数错误、DuckDB 锁冲突、Cloudflare 超时、漏跑 agent-daily……）。
**编排层和防坑文档早就写好了，但 agent 不知道去用。**

dispatcher 解决的就是这个问题：**每个新 session 进来的第一个请求，先过路由器，找到对应 skill 再按 skill 的流程走。**

## 使用规则（硬性）

1. **每个新 session 的第一步**：加载 dispatcher，对用户的首个请求跑 `route.py`
2. **匹配到 skill → 加载该 skill 的 SKILL.md，严格按其流程执行**
3. **未匹配 → 走 fallback 路径**（见下方）
4. **检测到批量/高风险关键词 → 先走 task-planner 采访，再 handoff 到匹配的 skill**
5. **不要绕过 dispatcher 直接手动跑命令**——这是 6.24 踩坑的根本原因

## 路由流程

```
用户输入
  ↓
route.py 扫描 skills/*/SKILL.md frontmatter
  ↓
三层匹配：
  1. 精确触发词命中（最高优先）
  2. 触发词子串命中
  3. description 关键词命中
  ↓
┌─ 匹配到 skill ────────────────────────┐
│                                        │
│  检查是否批量/高风险？                  │
│  ├─ 是 → task-planner 采访 → handoff   │
│  └─ 否 → 直接加载 SKILL.md 执行        │
│                                        │
└────────────────────────────────────────┘
┌─ 未匹配 ──────────────────────────────┐
│                                        │
│  fallback:                             │
│  1. 纯数据查询 → DuckDB read-only      │
│  2. 市场问答 → DuckDB + 知识库         │
│  3. 新功能/新题材 → task-planner        │
│  4. 不确定 → 问用户确认意图             │
│                                        │
└────────────────────────────────────────┘
```

## 命令

### 路由匹配

```bash
# 匹配单个请求
python3 skills/dispatcher/scripts/route.py "完成6.24的全量复盘"
# → ✅ 最佳匹配: daily-full-review (得分:100)

# 匹配并显示 SKILL.md 全文
python3 skills/dispatcher/scripts/route.py --show-skill "题材发酵怎么追溯"
# → ✅ 最佳匹配: theme-fermentation-tracer + SKILL.md 全文

# JSON 格式（供程序调用）
python3 skills/dispatcher/scripts/route.py --json "研报搜索"

# 列出所有可路由 skill
python3 skills/dispatcher/scripts/route.py --list
```

### Devin 远程执行场景

```bash
# 通过 rx.py 在 Mac 上跑路由
python3 rx.py -- "cd '/Users/lbq/Desktop/c c/金融' && python3 skills/dispatcher/scripts/route.py '用户的请求'"
```

## skill 路由表（自动生成，概览）

| skill | 触发词（前 3） | 模式 | 有脚本 |
|---|---|---|---|
| daily-full-review | 全量复盘、今日全量复盘、跑全量复盘 | - | ✅ run_review_sync.py |
| task-planner | 批量任务规划、开工前采访、批量回填前先问 | inversion | ✅ check_task_plan.py |
| duckdb-backfill | 回补 duckdb、全量回补、补缺口 | tool-wrapper | ✅ audit_coverage.py |
| market-overview | 帮我复盘、复盘、看一下今天的市场 | pipeline | ✅ check_coverage.py |
| theme-radar | (描述匹配：新词、新闻事件、题材) | pipeline | ✅ radar.py |
| theme-fermentation-tracer | 发酵链路、发酵回溯、谁先启动 | pipeline | ✅ trace.py |
| strategy-evolve | 进化、evolve、自动进化 | pipeline | - |
| strategy1-matrix | 策略一生成、生成策略1、策略一矩阵 | generator | ✅ update_matrix.py |
| opinion-cross | (描述匹配：卖方观点、提纯、三重共振) | pipeline | ✅ |
| serenity-alpha | serenity、alpha、弹性预期差 | generator | ✅ serenity_context.py |
| report-search | 搜研报、找研报、研报搜索 | tool-wrapper | ✅ |
| hithink-market-query | 股票价格、ETF行情、涨跌幅 | tool-wrapper | ✅ cli.py |
| top-gainers | 涨幅排行、涨幅前N、区间涨幅 | pipeline | ✅ query_sectors.py |
| top-gainers-feishu | 强势股入库、涨幅入库、区间强势 | pipeline | ✅ |
| high-volume-gainers | 大成交排行、大成交涨幅、加权涨幅 | pipeline | ✅ write.py |
| advancers-chart | 涨家数折线图、涨家数走势、涨跌趋势图 | generator | ✅ sync.py |
| limit-advance | 晋级 | pipeline | ✅ scrape.py |
| sector-data | 边际量、板块数据、抓取板块 | pipeline | - |
| watchlist-ma | 自选股均线、自选股MA、自选股过滤 | tool-wrapper | ✅ query.py |
| up-line | UP线更新、up线、查UP | tool-wrapper | ✅ update.py |
| disclosure-archive | 补公告、补公司硬证据、查年报 | reviewer | ✅ archive.py |
| foresight-feedback | (自动触发：用户表达兴趣/否定) | tool-wrapper | - |
| 潜意识模式 | 开启潜意识模式、潜意识模式、进入潜意识 | - | - |
| checkpoint-recheck-mac-setup | 夜间回检、checkpoint recheck | tool-wrapper | ✅ |
| 公司画像页 | 公司画像、画像页、strip profile | generator | - |
| 行业概览 | 行业概览、板块全景、行业全景 | generator | - |

## 特殊路由规则

### 1. 批量/高风险任务 → task-planner 前置

检测到以下关键词时，**先走 task-planner 采访**（G1-G8 逐关提问），确认后再 handoff：
- 批量、批处理、大回填、全量回补、多天、跨日期、开新题材、新概念图谱

### 2. 隐式触发 skill

以下 skill 不需要用户显式触发，agent 应在合适时机自动调用：
- **foresight-feedback**：用户表达对题材/个股的兴趣或否定时自动记录
- **checkpoint-recheck-mac-setup**：只在设置 Mac 定时任务时触发

### 3. 工具库 skill（不可独立路由）

以下 skill 不直接路由，仅供其他 skill 内部调用：
- **ifind**：iFinD MCP API 封装
- **lib**：共享工具库

## fallback 路径

当 route.py 无匹配时：

1. **纯数据查询**（"XX 板块今天涨了多少"）→ 直接 DuckDB read-only 查询，不需要 skill
2. **市场问答**（"消费电子最近怎么样"）→ 先查 DuckDB 有无板块/题材数据，再用知识库 wiki 补充
3. **新功能需求**（"帮我做个 XX"）→ 走 task-planner 采访，确认需求后判断是否需要新建 skill
4. **意图不明**→ 直接问用户："你想做什么？我可以帮你 [列出最相关的 2-3 个 skill]"

## 迭代规则

- 新增 skill 后，只要 SKILL.md 有 frontmatter + 触发词，dispatcher 自动识别（无需手动更新路由表）
- 如果某个 skill 经常被漏匹配，在其 SKILL.md description 中补充更多触发词
- 每次路由失败（用户想用某 skill 但没匹配到）都要在该 skill 的 SKILL.md 里补触发词
