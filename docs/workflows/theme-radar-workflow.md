# Theme Radar Workflow：题材雷达产品化闭环

更新时间：2026-06-11

## 1. 目标

把当前 Theme Radar 相关能力沉淀成一条可执行、可复用、可交接的产品化 workflow。

这条 workflow 的目标是：

> 输入一个题材、新词、新闻事件或盘面触发方向，系统输出定义、产业链、需求-瓶颈、细分方向、公司分层、证据强度、市场信号、验证清单和缺口队列。

它是 FDE 产品化路线中的第二条核心闭环，负责把知识库 Evidence Graph 与市场信号 Market Feature Store 连接起来。

整体链路：

```text
输入题材 / 盘面触发方向
  ↓
读取知识库概念、实体、证据、研报上下文
  ↓
可选接入题材信息池、方向池、补充数据池
  ↓
生成 Theme Radar 报告
  ↓
执行 readiness / quality / regression 检查
  ↓
识别证据缺口与补证队列
  ↓
可选触发 disclosure archive
  ↓
渲染为内部报告 / 工作台 / 网站专题页
```

## 2. 触发条件

适用场景：

- 用户输入一个新题材、新词、新闻事件或产业方向。
- 每日复盘发现盘面触发主题，需要生成题材简报。
- 某个题材已有研报/IMA/Obsidian 结构化数据，需要生成深拆报告。
- readiness 报告显示核心公司缺证，需要识别 disclosure archive 任务。
- Theme Radar 底层数据更新后，需要跑回归检查。
- 后续要把某个题材做成网站专题页或研究文章。

不适用场景：

- 只查询单个股票实时行情。
- 只生成纯文章而不需要证据链。
- 只做市场日内交易判断。
- 题材无任何本地上下文且用户不允许联网/补充定义时。

## 3. 输入参数

核心参数：

| 参数 | 说明 | 示例 |
|---|---|---|
| `term` | 题材、新词、新闻事件或方向 | `商业航天` |
| `mode` | 输出模式 | `radar` / `deep-dive` / `map` / `front-map` / `brief` |
| `vault` | 知识库 wiki 路径 | `/Users/lbq/Desktop/c c/知识库/wiki` |
| `definition` | 外部定义或技术拆解摘要 | `低轨卫星星座...` |
| `context_json` | 外部新词画像 JSON | `xxx.context.json` |
| `theme_info_jsonl` | 题材信息池 JSONL | `xxx.theme_information_items.jsonl` |
| `theme_direction_pool` | 标准细分方向池 JSON | `xxx.theme_direction_pool.json` |
| `theme_supplement_pool` | Theme Radar 补充数据池 JSON | `xxx.theme_supplement_pool.json` |
| `review_source` | 复盘触发来源 | `日复盘` |
| `review_direction` | 复盘识别方向 | `低空经济` |
| `review_companies` | 复盘触发公司 | `宗申动力,中无人机` |
| `out` | Markdown 输出路径 | `/tmp/theme-radar.md` |

## 4. 数据依赖

### 4.1 知识库 Evidence Graph

默认知识库路径：

```text
/Users/lbq/Desktop/c c/知识库/wiki
```

核心依赖：

```text
wiki/relations/concept_graph.json
wiki/relations/entity_exposures.json
wiki/relations/aliases.json
wiki/relations/evidence_index.json
wiki/relations/theme_signals.json
wiki/relations/pattern_library.json
wiki/relations/report_contexts.json
wiki/relations/benchmark_maps.json
wiki/concepts/
wiki/entities/
wiki/sources/
wiki/synthesis/
```

### 4.2 Theme Radar 结构化输入

可选输入：

- 题材信息池：`*.theme_information_items.jsonl`
- 方向池：`*.theme_direction_pool.json`
- 补充数据池：`*.theme_supplement_pool.json`
- 外部上下文：`context-json`
- 外部定义：`definition` 或 `definition-file`

### 4.3 市场信号输入

日终盘面触发题材依赖：

```text
fact_market_daily
fact_sector_daily
fact_sector_stock_daily
fact_stock_high_daily
fact_theme_limit_heat_daily
fact_theme_limit_stock_daily
fact_limit_advance_daily
fact_stock_daily
```

盘面触发题材简报会先调用每日复盘完整性闸门。

## 5. 标准执行路径

Theme Radar 有三类常用路径：

1. 单题材只读雷达。
2. 题材深拆 / 地图模式。
3. 日终盘面触发题材简报。

## 6. 路径 A：单题材只读雷达

适用场景：

- 用户直接问“研究一下某题材”。
- 需要快速查看一个题材在知识库中的公司暴露、证据和排序。
- 不需要额外导入方向池或补充数据池。

命令：

```bash
python3 skills/theme-radar/scripts/radar.py \
  --term 商业航天 \
  --out /tmp/商业航天-theme-radar.md
```

默认模式：

```text
--mode radar
```

输出：

```text
Markdown 报告
```

成功标准：

- 能解析题材主概念或相关概念。
- 能列出公司分层和证据桶。
- 能指出 missing evidence、graph_only、review_required 等问题。
- 报告不是纯泛化解释，而是能回到知识库关系数据。

## 7. 路径 B：题材深拆 / 题材地图

适用场景：

- 已有 IMA/Obsidian 题材信息池。
- 已有方向池或补充数据池。
- 需要输出产业链、需求-瓶颈、方向扫描、进度判断、验证清单。

### 7.1 构建方向池

输入：

```text
*.theme_information_items.jsonl
```

命令：

```bash
python3 scripts/build_theme_direction_pool.py \
  --theme 商业航天 \
  --theme-info-jsonl /path/to/商业航天.theme_information_items.jsonl \
  --out-dir /tmp/theme-radar \
  --prefix 商业航天
```

输出：

```text
/tmp/theme-radar/商业航天.theme_direction_pool.json
/tmp/theme-radar/商业航天.theme_direction_pool.md
```

方向池包含：

- 细分方向。
- 方向类型。
- 链条位置。
- 需求来源。
- 瓶颈。
- 公司候选。
- 证据 profile。
- 认知阶段。
- 机会优先级。
- 需求-瓶颈-环节传导表。

### 7.2 构建补充数据池

如有 Theme Radar 补充材料：

```bash
python3 scripts/build_theme_supplement_pool.py \
  /path/to/商业航天补充数据.md \
  --theme 商业航天 \
  --out-dir /tmp/theme-radar \
  --prefix 商业航天
```

输出：

```text
/tmp/theme-radar/商业航天.theme_supplement_pool.json
```

补充数据池可包含：

- 需求场景。
- 工艺材料。
- 验证节点。
- 催化日历。
- 认知演变。
- 操作建议。

### 7.3 检查补充数据池质量

命令：

```bash
python3 scripts/check_theme_supplement_pool.py \
  /tmp/theme-radar/商业航天.theme_supplement_pool.json
```

可选输出：

```bash
python3 scripts/check_theme_supplement_pool.py \
  /tmp/theme-radar/商业航天.theme_supplement_pool.json \
  --out-json /tmp/theme-radar/商业航天.supplement_qc.json \
  --out-md /tmp/theme-radar/商业航天.supplement_qc.md
```

### 7.4 生成 deep-dive 报告

命令：

```bash
python3 skills/theme-radar/scripts/radar.py \
  --term 商业航天 \
  --mode deep-dive \
  --theme-direction-pool /tmp/theme-radar/商业航天.theme_direction_pool.json \
  --theme-supplement-pool /tmp/theme-radar/商业航天.theme_supplement_pool.json \
  --out /tmp/theme-radar/商业航天-theme-radar-deep-dive.md
```

也可以生成题材地图：

```bash
python3 skills/theme-radar/scripts/radar.py \
  --term 商业航天 \
  --mode map \
  --theme-direction-pool /tmp/theme-radar/商业航天.theme_direction_pool.json \
  --out /tmp/theme-radar/商业航天-theme-map.md
```

前端精简地图：

```bash
python3 skills/theme-radar/scripts/radar.py \
  --term 商业航天 \
  --mode front-map \
  --theme-direction-pool /tmp/theme-radar/商业航天.theme_direction_pool.json \
  --out /tmp/theme-radar/商业航天-front-map.md
```

速读版：

```bash
python3 skills/theme-radar/scripts/radar.py \
  --term 商业航天 \
  --mode brief \
  --theme-direction-pool /tmp/theme-radar/商业航天.theme_direction_pool.json \
  --out /tmp/theme-radar/商业航天-brief.md
```

## 8. 路径 C：日终盘面触发题材简报

适用场景：

- 每日复盘后识别盘面触发主题。
- 需要把市场 feature store 和知识库 Evidence Graph 合并。
- 工作台中需要每日“市场复盘 / 题材雷达”子视图。

### 8.1 生成 JSON 和 Markdown 简报

命令：

```bash
python3 scripts/build_market_triggered_theme_brief.py YYYY-MM-DD
```

输出：

```text
market_feature_store/exports/YYYY-MM-DD-triggered-themes.json
market_feature_store/exports/YYYY-MM-DD-market-triggered-theme-brief.md
```

参数：

```bash
python3 scripts/build_market_triggered_theme_brief.py YYYY-MM-DD \
  --output /tmp/triggered-themes.json \
  --brief-output /tmp/theme-brief.md \
  --vault /Users/lbq/Desktop/c c/知识库/wiki
```

只生成 JSON：

```bash
python3 scripts/build_market_triggered_theme_brief.py YYYY-MM-DD --json-only
```

调试时跳过 gate：

```bash
python3 scripts/build_market_triggered_theme_brief.py YYYY-MM-DD --skip-gate
```

注意：

- `--skip-gate` 只用于调试。
- 正式复盘中不应跳过数据完整性闸门。

### 8.2 生成 HTML 简报

命令：

```bash
python3 scripts/render_market_triggered_theme_brief_html.py YYYY-MM-DD
```

输出：

```text
复盘/daily/YYYY-MM-DD/YYYY-MM-DD-market-triggered-theme-brief.html
```

该脚本会先调用 `build_market_triggered_theme_brief.py`。

### 8.3 生成新旧候选对照验证报告

命令：

```bash
python3 scripts/compare_theme_candidates.py YYYY-MM-DD
```

输入：

```text
market_feature_store/exports/YYYY-MM-DD-theme-candidates.json
market_feature_store/exports/YYYY-MM-DD-triggered-themes.json
```

输出：

```text
market_feature_store/exports/YYYY-MM-DD-theme-candidates-qa.md
```

该报告只读取本地 JSON 产物，不查询 DuckDB，不读取 wiki 正文，不写知识库，不调用大模型；用于对照共同候选、仅新候选、仅旧候选、Top N 排序、知识库命中、候选公司覆盖和 backfill gaps。

### 8.4 刷新工作台

命令：

```bash
python3 scripts/render_review_workbench.py
```

输出：

```text
复盘/matrices/strategy-review-workbench.html
```

成功标准：

- 对应日期每日复盘 HTML 存在。
- 对应日期题材简报 HTML 存在。
- 工作台“每日复盘”下可切换“市场复盘 / 题材雷达”。

## 9. Readiness 检查

适用场景：

- 需要判断某题材的公司证据是否够用。
- 需要识别哪些公司缺 baseline、官方证据或直接题材证据。
- 需要决定是否触发 disclosure archive 补证。

命令：

```bash
python3 scripts/build_theme_evidence_readiness.py --theme 商业航天
```

默认输出：

```text
wiki/raw/theme-radar/readiness/theme-evidence-readiness-商业航天.json
wiki/raw/theme-radar/readiness/theme-evidence-readiness-商业航天.md
```

可指定输出：

```bash
python3 scripts/build_theme_evidence_readiness.py \
  --theme 商业航天 \
  --out-json /tmp/商业航天-readiness.json \
  --out-md /tmp/商业航天-readiness.md
```

重点指标：

- `company_count`
- `high_confidence`
- `entity_baseline_ready`
- `theme_evidence_ready`
- `official_evidence_ready`
- `direct_theme_evidence_ready`
- `review_required`

## 10. Regression 检查

适用场景：

- Theme Radar 底层数据更新后。
- disclosure apply 后。
- 修改 `radar.py`、证据桶、排序规则、quality rules 后。
- 需要确认典型题材没有退化。

命令：

```bash
python3 scripts/run_theme_radar_regression.py
```

指定题材：

```bash
python3 scripts/run_theme_radar_regression.py \
  --themes 先进封装 商业航天 固态电池 人形机器人
```

输出：

```text
/Users/lbq/Desktop/c c/知识库/wiki/raw/theme-radar/regression/theme-radar-regression-matrix.json
/Users/lbq/Desktop/c c/知识库/wiki/raw/theme-radar/regression/theme-radar-regression-matrix.md
```

单题材报告：

```text
/Users/lbq/Desktop/c c/知识库/wiki/raw/theme-radar/regression/{theme}-theme-radar-regression.md
```

重点指标：

- 总分。
- Top10 公司排序。
- 证据桶准确性。
- weak granularity。
- chain_layer conflict。
- review_required。
- soft_fact_hardness。
- need_deep_read。

## 11. Disclosure Archive 补证衔接

当 readiness 显示官方证据不足时，不应直接把弱证据升级为强证据。

标准路径：

```text
readiness 识别缺口
  ↓
人工确认 P0/P1 公司和证据缺口
  ↓
调用知识库 disclosure-archive 进行 archive-only
  ↓
人工审核 review queue
  ↓
显式 apply 到 entity_exposures / evidence_index
  ↓
重新跑 readiness 和 regression
```

关键安全边界：

- archive-only 阶段不写入 `entity_exposures.json` 或 `evidence_index.json`。
- apply 必须显式 `--apply`。
- 写入前应 `--backup`。
- baseline 不得降级 hard_delta。
- graph_only / exposure_only 不得错误升级为官方证据。

## 12. 质量闸门

### 12.1 必须阻断的错误

以下情况必须阻断正式输出或发布：

- `radar.py` 无法读取知识库 relations。
- 题材完全无法匹配，且无外部定义或 context。
- 公司排序只来自 graph_only，且未明确标记弱关联。
- hard_delta 没有强证据来源。
- readiness 显示核心公司 `official_evidence_ready` 明显不足，但报告却给出强结论。
- direction pool 或 supplement pool QC 不通过。
- regression 总分显著下降。
- disclosure apply 出现 audit violations。

### 12.2 可以警告但不一定阻断的情况

- 题材是新词，本地概念图谱尚未覆盖。
- 公司存在研报线索但缺官方证据。
- 方向池只有少量来源。
- 市场信号暂未确认。
- 缺少短期催化，但产业链结构清楚。

这些应标记为：

```text
WARN / 待验证 / review_required / missing_confirmation
```

## 13. 输出清单

### 13.1 单题材输出

```text
{theme}-theme-radar.md
{theme}-theme-radar-deep-dive.md
{theme}-theme-map.md
{theme}-front-map.md
{theme}-brief.md
```

### 13.2 方向池输出

```text
{theme}.theme_direction_pool.json
{theme}.theme_direction_pool.md
```

### 13.3 补充数据池输出

```text
{theme}.theme_supplement_pool.json
{theme}.supplement_qc.json
{theme}.supplement_qc.md
```

### 13.4 日终触发题材输出

```text
market_feature_store/exports/YYYY-MM-DD-triggered-themes.json
market_feature_store/exports/YYYY-MM-DD-market-triggered-theme-brief.md
复盘/daily/YYYY-MM-DD/YYYY-MM-DD-market-triggered-theme-brief.html
```

### 13.5 readiness / regression 输出

```text
wiki/raw/theme-radar/readiness/theme-evidence-readiness-{theme}.json
wiki/raw/theme-radar/readiness/theme-evidence-readiness-{theme}.md
wiki/raw/theme-radar/regression/theme-radar-regression-matrix.json
wiki/raw/theme-radar/regression/theme-radar-regression-matrix.md
```

## 14. 建议的 machine-readable summary

未来统一 CLI 应输出：

```json
{
  "workflow": "theme-radar",
  "term": "商业航天",
  "mode": "deep-dive",
  "status": "PASS",
  "steps": [
    {"name": "resolve-theme", "status": "PASS"},
    {"name": "read-evidence-graph", "status": "PASS"},
    {"name": "build-direction-pool", "status": "PASS"},
    {"name": "build-radar-report", "status": "PASS"},
    {"name": "readiness", "status": "WARN"},
    {"name": "regression", "status": "PASS"}
  ],
  "outputs": [],
  "warnings": [],
  "missing_evidence": [],
  "next_actions": []
}
```

## 15. 常见失败和修复方式

### 15.1 `radar.py` 找不到知识库

表现：

- relation 文件缺失。
- vault 路径错误。

处理：

```bash
python3 skills/theme-radar/scripts/radar.py \
  --term 商业航天 \
  --vault /Users/lbq/Desktop/c c/知识库/wiki
```

### 15.2 题材匹配不到概念

处理：

1. 提供 `--definition` 或 `--definition-file`。
2. 提供 `--context-json`。
3. 检查 `aliases.json` 和 `concept_graph.json`。
4. 必要时先回到知识库补 concept/entity。

### 15.3 公司列表太泛或 weak_graph 过多

处理：

1. 检查 `entity_exposures.json` 中该题材的 strength 和 chain_layer。
2. 跑 readiness。
3. 对 P0/P1 公司补官方证据。
4. 跑 regression 确认排序改善。

### 15.4 direction pool 噪音大

处理：

1. 调整 `--min-score`。
2. 检查 theme information JSONL 是否混入泛主题。
3. 检查方向池中的 demand/bottleneck 是否泛化。
4. 优先保留有 evidence_trace 的方向。

### 15.5 日终触发题材简报失败

处理：

1. 先运行每日复盘 gate：

```bash
python3 scripts/check_daily_review_data.py YYYY-MM-DD
```

2. 如 gate 失败，先补市场数据。
3. gate 通过后再运行：

```bash
python3 scripts/render_market_triggered_theme_brief_html.py YYYY-MM-DD
python3 scripts/render_review_workbench.py
```

## 16. 后续产品化改造方向

### 16.1 统一 CLI

目标命令：

```bash
python3 -m intelligence.cli theme --term 商业航天 --mode deep-dive
python3 -m intelligence.cli theme-readiness --term 商业航天
python3 -m intelligence.cli theme-regression --themes 商业航天 固态电池
python3 -m intelligence.cli market-triggered-themes --date YYYY-MM-DD
```

### 16.2 ThemeRadarService

建议接口：

```text
ThemeRadarService.run(term, mode="radar", context=None)
ThemeRadarService.build_direction_pool(term, theme_info_jsonl)
ThemeRadarService.build_supplement_pool(term, source)
ThemeRadarService.readiness(term)
ThemeRadarService.regression(themes)
ThemeRadarService.render_html(report)
```

### 16.3 标准 JSON schema

下一阶段应定义：

```text
definition
chain_map
demand_drivers
bottlenecks
direction_scan
entity_tiers
evidence_items
market_signals
opportunity_profile
validation_checklist
missing_confirmations
rendered_markdown
rendered_html
```

## 17. 下一个 agent 接手方式

下次继续时：

1. 先执行 `git status --short && git branch --show-current`。
2. 读取 `fde/README.md`。
3. 读取 `docs/productization-roadmap.md`。
4. 读取本文档。
5. 如果用户要分析题材，按路径 A/B/C 选择执行。
6. 如果用户要继续产品化，下一步是设计统一 CLI 或 Theme Radar 标准 JSON schema。
