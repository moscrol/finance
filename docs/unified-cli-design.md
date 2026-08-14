# Unified CLI Design：FDE 产品级命令入口设计

更新时间：2026-06-11

## 1. 目标

统一 CLI 的目标不是替代现有 `market_feature_store.cli`，而是在其上方增加一层产品级 orchestration 入口。

现有 CLI 主要解决：

```text
数据同步 / 数据查询 / 单模块报告生成
```

统一 CLI 解决：

```text
按业务工作流运行完整闭环，并输出统一 summary
```

第一阶段目标：

> 只封装已有脚本和模块，不重写底层逻辑，不改现有命令语义。

## 2. 命名与目录位置

建议新增包名：

```text
intelligence/
```

建议目录：

```text
intelligence/
├── __init__.py
├── cli.py                    # 产品级 CLI 入口
├── summary.py                # PASS/WARN/FAIL summary schema
├── paths.py                  # 三仓路径与输出目录
├── workflows/
│   ├── __init__.py
│   ├── daily_review.py       # 每日复盘 workflow 封装
│   ├── theme_radar.py        # Theme Radar workflow 封装
│   └── publish.py            # 网站发布 workflow，后置
├── adapters/
│   ├── __init__.py
│   ├── market.py             # MarketAdapter，只读封装 DuckDB/market_feature_store
│   └── knowledge.py          # KnowledgeAdapter，只读封装知识库 JSON/Markdown
└── services/
    ├── __init__.py
    ├── daily_review.py       # DailyReviewService，后续从 workflow 中抽出
    ├── theme_radar.py        # ThemeRadarService，后续从 workflow 中抽出
    └── strategy_matrix.py    # StrategyMatrixService，后置
```

命令入口：

```bash
python3 -m intelligence.cli <command>
```

不建议命名为：

```text
product/
app/
ai/
agent/
```

原因：

- `intelligence` 更贴合产品定位。
- 避免和网站 app、agent skill、通用 AI 概念混淆。
- 未来可以同时承载市场情报、题材情报和发布情报。

## 3. 与现有 CLI 的关系

### 3.1 现有 `market_feature_store.cli`

继续保留为底层 CLI。

职责：

- 初始化数据库。
- 同步单类数据。
- 回补区间数据。
- 生成每日复盘 Markdown。
- 查询个股/板块/新高/涨停。
- 提供 health/info。

典型命令：

```bash
python3 -m market_feature_store.cli daily-update --trade-date YYYY-MM-DD
python3 -m market_feature_store.cli daily-review --trade-date YYYY-MM-DD
python3 -m market_feature_store.cli daily-full --trade-date YYYY-MM-DD
python3 -m market_feature_store.cli sync-stock-high --trade-date YYYY-MM-DD
python3 -m market_feature_store.cli limit-heat --trade-date YYYY-MM-DD
```

### 3.2 新增 `intelligence.cli`

只做产品工作流封装。

职责：

- 串联多个底层命令。
- 执行质量闸门。
- 输出统一 summary。
- 约束失败时是否继续。
- 为后续 UI / Agent / 自动化调度提供稳定入口。

典型命令：

```bash
python3 -m intelligence.cli daily --date YYYY-MM-DD
python3 -m intelligence.cli adapter-smoke --date YYYY-MM-DD --entity ASML
python3 -m intelligence.cli theme --term 商业航天 --mode deep-dive
python3 -m intelligence.cli theme-readiness --term 商业航天
python3 -m intelligence.cli theme-regression --themes 商业航天 固态电池
python3 -m intelligence.cli market-triggered-themes --date YYYY-MM-DD
```

## 4. 命令分组

### 4.1 `daily`

每日复盘闭环。

命令：

```bash
python3 -m intelligence.cli daily --date YYYY-MM-DD
```

参数：

| 参数 | 默认 | 说明 |
|---|---:|---|
| `--date` | 必填 | 交易日 |
| `--skip-sync` | false | 跳过数据同步，只重新渲染 |
| `--skip-long` | false | 透传给 `daily-update` |
| `--skip-theme` | false | 不生成盘面触发题材简报 |
| `--skip-workbench` | false | 不刷新工作台 |
| `--start-date` | 空 | 透传给 daily review |
| `--summary-json` | 空 | 写出 summary JSON |
| `--dry-run` | false | 只打印计划，不执行命令 |
| `--from-step` | 空 | 从指定步骤开始执行 |
| `--only-step` | 空 | 只执行指定步骤 |
| `--continue-on-warn` | false | 可恢复失败降级 WARN 后继续执行 |

封装现有步骤：

```text
1. python3 -m market_feature_store.cli daily-update --trade-date DATE
2. python3 -m market_feature_store.cli daily-review --trade-date DATE
3. python3 scripts/check_daily_review_data.py DATE
4. python3 scripts/render_daily_review_briefing.py DATE
5. python3 scripts/render_market_triggered_theme_brief_html.py DATE
6. python3 scripts/render_review_workbench.py
```

第一阶段边界：

- 不自动编辑策略矩阵人工判断。
- 不自动 commit。
- 不自动发布网站。

### 4.2 `adapter-smoke`

Adapter 只读自检。

命令：

```bash
python3 -m intelligence.cli adapter-smoke --date YYYY-MM-DD --entity ASML
```

参数：

| 参数 | 默认 | 说明 |
|---|---:|---|
| `--date` | latest | 交易日；为空则由 Adapter 使用最新可用日期 |
| `--entity` | ASML | 知识库实体名 |
| `--concept` | 空 | evidence 可选过滤词 |
| `--summary-json` | 空 | 写出 summary JSON |

封装现有 Adapter：

```text
1. MarketAdapter.health()
2. MarketAdapter.get_capacity_sectors(date)
3. MarketAdapter.get_double_red_themes(date)
4. KnowledgeAdapter.get_entity_exposures(entity)
5. KnowledgeAdapter.get_evidence(entity, concept)
```

约束：

- 只读。
- 不触发 `daily-update`。
- 不读取 wiki 正文。
- 用于 service/workflow 集成前的快速健康检查。

### 4.3 `theme`

单题材雷达或深拆。

命令：

```bash
python3 -m intelligence.cli theme --date YYYY-MM-DD --market-triggered
python3 -m intelligence.cli theme --term 商业航天 --mode radar
python3 -m intelligence.cli theme --term 商业航天 --mode deep-dive
```

参数：

| 参数 | 默认 | 说明 |
|---|---:|---|
| `--date` | 空 | 交易日；用于 `--market-triggered` |
| `--market-triggered` | false | 构建市场触发候选；当前已实现的最小模式 |
| `--top` | 50 | 市场触发候选数量上限 |
| `--out-json` | 空 | 写出市场触发候选 JSON |
| `--out-md` | 空 | 写出市场触发候选 Markdown 简报 |
| `--term` | 雷达模式必填 | 题材、新词、新闻事件；当前最小 `--market-triggered` 模式不需要 |
| `--mode` | `radar` | `radar/deep-dive/map/front-map/brief` |
| `--vault` | 知识库默认路径 | wiki vault |
| `--definition` | 空 | 外部定义摘要 |
| `--definition-file` | 空 | 外部定义文件 |
| `--context-json` | 空 | 新词画像 JSON |
| `--theme-info-jsonl` | 空 | 题材信息池 |
| `--theme-direction-pool` | 空 | 方向池 JSON |
| `--theme-supplement-pool` | 空 | 补充数据池 JSON |
| `--out-dir` | `market_feature_store/exports/theme-radar` | 输出目录 |
| `--summary-json` | 空 | 写出 summary JSON |
| `--dry-run` | false | 只打印计划 |

封装现有命令：

```text
market-triggered -> ThemeRadarService.build_market_triggered_candidates(date)
python3 skills/theme-radar/scripts/radar.py --term TERM --mode MODE --out OUT
```

当前最小实现只接入 `--market-triggered`，不调用大模型，不触发数据同步；`--out-json` 显式提供时才写候选 JSON，`--out-md` 显式提供时才写 Markdown 简报。候选 JSON/Markdown 已包含 `market_evidence`、`matched_concepts`、`candidate_companies`、`knowledge_evidence` 与 `knowledge_status`；Markdown 只做结构化呈现，不包含买卖指令。

如提供方向池或补充数据池，则透传给 `radar.py`。

### 4.4 `theme-readiness`

题材证据准备度检查。

命令：

```bash
python3 -m intelligence.cli theme-readiness --term 商业航天
```

封装：

```bash
python3 scripts/build_theme_evidence_readiness.py --theme 商业航天
```

参数：

| 参数 | 默认 | 说明 |
|---|---:|---|
| `--term` | 必填 | 题材 |
| `--out-dir` | 知识库 readiness 默认目录 | 输出目录 |
| `--summary-json` | 空 | 写出 summary JSON |

### 4.5 `theme-regression`

Theme Radar 回归检查。

命令：

```bash
python3 -m intelligence.cli theme-regression --themes 先进封装 商业航天 固态电池 人形机器人
```

封装：

```bash
python3 scripts/run_theme_radar_regression.py --themes ...
```

参数：

| 参数 | 默认 | 说明 |
|---|---:|---|
| `--themes` | 典型题材列表 | 多个题材 |
| `--summary-json` | 空 | 写出 summary JSON |

### 4.6 `market-triggered-themes`

日终盘面触发题材简报。

命令：

```bash
python3 -m intelligence.cli market-triggered-themes --date YYYY-MM-DD
```

封装：

```text
1. python3 scripts/build_market_triggered_theme_brief.py DATE
2. python3 scripts/render_market_triggered_theme_brief_html.py DATE
3. python3 scripts/render_review_workbench.py
```

参数：

| 参数 | 默认 | 说明 |
|---|---:|---|
| `--date` | 必填 | 交易日 |
| `--json-only` | false | 只生成 JSON |
| `--skip-gate` | false | 仅调试 |
| `--skip-html` | false | 不生成 HTML |
| `--skip-workbench` | false | 不刷新工作台 |
| `--summary-json` | 空 | 写出 summary JSON |

### 4.7 `validate`

统一质量闸门。

命令：

```bash
python3 -m intelligence.cli validate --date YYYY-MM-DD
python3 -m intelligence.cli validate --theme 商业航天
```

第一阶段分两类：

```text
validate daily
validate theme
```

建议命令：

```bash
python3 -m intelligence.cli validate-daily --date YYYY-MM-DD
python3 -m intelligence.cli validate-theme --term 商业航天
```

封装：

```text
validate-daily -> scripts/check_daily_review_data.py DATE
validate-theme -> scripts/build_theme_evidence_readiness.py --theme TERM
```

## 5. 参数规范

### 5.1 日期参数

产品级 CLI 统一使用：

```text
--date YYYY-MM-DD
```

底层命令如使用 `--trade-date`，由 wrapper 转换。

### 5.2 题材参数

产品级 CLI 统一使用：

```text
--term 商业航天
```

底层命令如使用 `--theme`，由 wrapper 转换。

### 5.3 输出目录

统一支持：

```text
--out-dir
--summary-json
```

其中：

- `--out-dir` 控制业务输出目录。
- `--summary-json` 控制 workflow summary 输出路径。

### 5.4 dry-run

所有 workflow 命令都应支持：

```text
--dry-run
```

行为：

- 打印将执行的命令序列。
- 检查输入参数和路径。
- 不写业务输出。
- 不调用底层写入命令。

## 6. Summary Schema

所有产品级命令统一输出 summary。

建议结构：

```json
{
  "workflow": "daily",
  "status": "PASS",
  "started_at": "2026-06-11T01:50:00+08:00",
  "finished_at": "2026-06-11T01:53:00+08:00",
  "inputs": {
    "date": "2026-06-10"
  },
  "steps": [
    {
      "name": "daily-update",
      "status": "PASS",
      "command": "python3 -m market_feature_store.cli daily-update --trade-date 2026-06-10",
      "returncode": 0,
      "duration_sec": 12.3,
      "stdout_tail": [],
      "stderr_tail": []
    }
  ],
  "outputs": [
    "market_feature_store/exports/2026-06-10-daily-review.md"
  ],
  "warnings": [],
  "errors": [],
  "next_actions": []
}
```

状态枚举：

```text
PASS   全部关键步骤通过
WARN   关键输出存在，但有缺证、跳过长任务、弱覆盖等风险
FAIL   关键步骤失败或质量闸门未通过
SKIP   用户显式跳过或 dry-run 未执行
```

## 7. 执行策略

### 7.1 小步执行

遵守用户偏好：

- 不跑大而全长命令。
- 长任务拆成小单元。
- 日期矩阵一个日期一个日期处理。
- 每个步骤输出明确状态。

### 7.2 失败即阻断

默认策略：

```text
关键步骤 FAIL -> 后续依赖步骤不执行
```

例如：

- `check_daily_review_data.py` 失败，不渲染正式 HTML。
- readiness 显示强缺证，不输出强结论。
- regression 失败，不进入发布。

### 7.3 不自动 commit / push

第一阶段 CLI 不做：

- git add
- git commit
- git push
- deploy
- IndexNow

这些保留给人工确认或单独 publish workflow。

## 8. 第一阶段不重写的边界

不重写：

- `market_feature_store.cli`
- `daily_review.py`
- `radar.py`
- `build_market_triggered_theme_brief.py`
- `render_review_workbench.py`
- strategy matrix HTML 逻辑

只新增：

- 产品级 wrapper。
- summary 结构。
- 路径管理。
- workflow 编排。

## 9. 第一阶段实现顺序

建议实现顺序：

1. `intelligence/summary.py`
2. `intelligence/paths.py`
3. `intelligence/cli.py` 空壳和参数解析
4. `intelligence/workflows/daily_review.py`
5. `daily` 命令 dry-run
6. `daily` 命令真实执行
7. `adapter-smoke` 命令
8. `market-triggered-themes` 命令
9. `theme` 命令
10. `theme-readiness` 命令
11. `theme-regression` 命令

最小可交付版本：

```text
python3 -m intelligence.cli daily --date YYYY-MM-DD --dry-run
python3 -m intelligence.cli daily --date YYYY-MM-DD --skip-sync
python3 -m intelligence.cli adapter-smoke --date YYYY-MM-DD --entity ASML
```

## 10. 验收标准

### 10.1 文档验收

- 命令列表清楚。
- 参数命名统一。
- 与现有脚本关系清楚。
- 明确哪些不做。
- 明确 summary schema。

### 10.2 未来代码验收

- `python3 -m intelligence.cli daily --date YYYY-MM-DD --dry-run` 能打印步骤。
- dry-run 不写文件。
- 真实运行能生成 summary。
- 关键步骤失败时返回非零退出码。
- 不破坏现有 `market_feature_store.cli`。

## 11. 后续文档衔接

本设计完成后，下一步建议：

```text
docs/adapters-design.md
```

内容：

- `KnowledgeAdapter` 只读接口。
- `MarketAdapter` 只读接口。
- 路径、缓存、错误处理。
- 与 CLI / service 的关系。

再下一步：

```text
docs/theme-radar-json-schema.md
```

内容：

- Theme Radar 标准 JSON schema。
- 市场信号 schema。
- evidence item schema。
- validation checklist schema。
