# Daily Review Workflow：每日复盘产品化闭环

更新时间：2026-06-11

## 1. 目标

把当前金融仓库里已经存在的日更、质检、复盘、题材简报、策略矩阵和工作台刷新流程，沉淀成一条可执行、可复用、可交接的产品化 workflow。

这条 workflow 是 FDE 产品化路线中的第一条闭环，因为它已经具备完整链路：

```text
市场数据同步
  ↓
数据完整性检查
  ↓
每日复盘生成
  ↓
盘面触发题材简报
  ↓
策略矩阵更新
  ↓
工作台刷新
  ↓
归档 / 可选发布
```

## 2. 触发条件

适用场景：

- 每个交易日收盘后生成复盘。
- 用户要求“生成今日复盘”“更新每日复盘”“刷新工作台”。
- 新补数据后需要重新生成历史日期复盘。
- 策略矩阵或题材简报更新后需要刷新 `strategy-review-workbench.html`。

不适用场景：

- 只想查询某个字段或单个指标。
- 只想更新某个策略矩阵的单行。
- 只想发布研究文章到网站。
- 数据源异常、CDP 未登录、目标日期不是交易日且未确认时。

## 3. 输入参数

核心参数：

| 参数 | 说明 | 示例 |
|---|---|---|
| `trade_date` | 交易日，格式 `YYYY-MM-DD` | `2026-06-10` |
| `skip_long` | 是否跳过板块成分股、全 A 日线等长任务 | `true/false` |
| `with_chart` | 是否生成或同步涨家数 MA5 图 | `true/false` |
| `start_date` | 用于日报主线启动日模块，可选 | `2026-04-08` |
| `publish` | 是否进入网站发布流程，第一阶段默认否 | `false` |

当前建议：

- 日常完整复盘默认不跳过长任务。
- 快速补报告时可使用 `--skip-long`，但必须在报告里明确数据覆盖风险。
- 对历史日期复盘，不要一次跑大区间，按用户偏好一个日期一个日期执行。

## 4. 数据依赖

每日复盘至少依赖以下表或文件。

### 4.1 DuckDB 数据表

质检脚本 `scripts/check_daily_review_data.py` 当前检查：

```text
fact_market_daily
fact_sector_daily
fact_sw_l1_daily
fact_sector_stock_daily
fact_stock_high_daily
fact_theme_limit_heat_daily
fact_theme_limit_stock_daily
fact_limit_advance_daily
fact_stock_daily
```

其中 `fact_market_daily` 必须具备以下核心字段：

```text
sh_index_close
sh_index_pct_chg
sh_week_ma
sh_deviation_pct
total_amount
amount_vs_yesterday_pct
amount_ma20
volume_ratio
advancers
limit_up
limit_down
top3_industry_ratio
strength_avg_pct
strength_amount_pct
strength_status
```

### 4.2 输出文件依赖

质检脚本还会检查：

```text
market_feature_store/exports/{trade_date}-daily-review.md
```

并检查以下占位或缺失信号：

```text
| 周均线 | - |
| 偏离度 | - |
| 涨停方向 | 核心涨停题材： |
暂无
未返回
```

### 4.3 数据源依赖

主要数据源：

- 复盘会 / fupanhui：市场总览、板块、涨停热度、新高、连板等。
- AkShare：指数、申万一级等补充数据。
- mootdx：全 A 个股日线。
- Feishu：部分历史或人工维护数据源。

注意：

- fupanhui 数据依赖本地 Chrome/CDP 登录态。
- 若 CDP proxy 不可用，应先修复数据源，不应伪造数据。
- 若只补报告不补数据，必须先确认目标日期数据已经完整入库。

## 5. 标准执行步骤

### Step 0：Git 与环境检查

每次开始前必须执行：

```bash
git status --short && git branch --show-current
```

要求：

- 确认当前分支。
- 确认是否有未提交文件。
- 若会改脚本、文档或矩阵，必须明确本轮写入范围。
- 不要在不相关分支上混入复盘产物。

### Step 1：同步市场数据

完整日更命令：

```bash
python3 -m market_feature_store.cli daily-update --trade-date YYYY-MM-DD
```

快速模式：

```bash
python3 -m market_feature_store.cli daily-update --trade-date YYYY-MM-DD --skip-long
```

等价完整闭环入口：

```bash
python3 -m market_feature_store.cli daily-full --trade-date YYYY-MM-DD
```

注意：

- `daily-update` 负责同步和补字段。
- `daily-review` 只从 DuckDB 生成复盘 Markdown。
- `daily-full` 是日更后生成复盘的组合入口。
- 若数据源报错，应先定位具体同步步骤，不要直接跳到报告生成。

### Step 2：生成每日复盘 Markdown

如果没有使用 `daily-full`，单独生成日报：

```bash
python3 -m market_feature_store.cli daily-review --trade-date YYYY-MM-DD
```

默认输出：

```text
market_feature_store/exports/YYYY-MM-DD-daily-review.md
market_feature_store/exports/YYYY-MM-DD-advancers-ma5.png
```

也可以使用稳定模板脚本：

```bash
python3 scripts/render_daily_review_template.py --trade-date YYYY-MM-DD
```

该模板脚本是现役只读渲染入口，读取 `db/market_feature_store.duckdb`；不要再使用已退役的 `scripts/sync_to_local.py` 写入旧库。

适用场景：

- 需要按固化版式快速生成完整每日市场复盘。
- 需要复用当前稳定模板。

### Step 3：数据完整性检查

必须执行：

```bash
python3 scripts/check_daily_review_data.py YYYY-MM-DD
```

成功标准：

```text
RESULT: COMPLETE
```

失败标准：

```text
RESULT: INCOMPLETE
```

如果失败：

- 停止进入 HTML / 发布阶段。
- 根据缺失项补对应同步任务。
- 不要手动删除占位符来绕过质检。

### Step 4：生成每日复盘 HTML

推荐使用带质检 gate 的脚本：

```bash
python3 scripts/render_daily_review_briefing.py YYYY-MM-DD
```

输出：

```text
复盘/daily/YYYY-MM-DD/YYYY-MM-DD-daily-review.html
```

备用脚本：

```bash
python3 scripts/render_daily_review_html.py YYYY-MM-DD
```

注意：

- `render_daily_review_briefing.py` 会先调用 `check_daily_review_data.py`。
- `render_daily_review_html.py` 只渲染 HTML，不负责质检。
- 日常产品化闭环优先使用 briefing 脚本。

### Step 5：生成盘面触发题材简报

Markdown / JSON 生成：

```bash
python3 scripts/build_market_triggered_theme_brief.py YYYY-MM-DD
```

新 `ThemeRadarService` 候选产物生成：

```bash
python3 -m intelligence.cli theme --date YYYY-MM-DD --market-triggered \
  --out-json market_feature_store/exports/YYYY-MM-DD-theme-candidates.json \
  --out-md market_feature_store/exports/YYYY-MM-DD-theme-candidates.md
```

HTML 生成：

```bash
python3 scripts/render_market_triggered_theme_brief_html.py YYYY-MM-DD
```

输出：

```text
market_feature_store/exports/YYYY-MM-DD-theme-candidates.json
market_feature_store/exports/YYYY-MM-DD-theme-candidates.md
market_feature_store/exports/YYYY-MM-DD-market-triggered-theme-brief.md
market_feature_store/exports/YYYY-MM-DD-market-triggered-theme-brief.json
复盘/daily/YYYY-MM-DD/YYYY-MM-DD-market-triggered-theme-brief.html
```

注意：

- Daily CLI 的 `theme-candidates` 步骤会生成新 JSON/MD 候选产物。
- HTML 脚本会先调用 Markdown/JSON 生成脚本。
- 新 `theme-candidates` 产物与旧 HTML 简报并行保留，暂不互相替换。
- 若题材简报缺失，工作台里的“题材雷达”按钮会禁用或为空。

### Step 6：更新策略矩阵

当前策略矩阵包括：

```text
复盘/matrices/strategy1-priority-stock-matrix.html
复盘/matrices/strategy2-weak-market-matrix.html
复盘/matrices/strategy3-touch-up-rebound-matrix.html
复盘/matrices/strategy4-dual-engine-matrix.html
复盘/matrices/second-board-4plus-candidate-matrix.html
```

已有自动化脚本：

```bash
python3 scripts/render_strategy4_dual_engine_matrix.py
```

其他策略矩阵当前可能仍包含人工 D0 判断和手工维护内容。更新时要求：

- 只使用 D0 当日及以前可见数据。
- 禁止用后续晋级或后续涨跌反推 D0。
- 明确市场环境、容量板块、双红数量、候选池、风险锚。
- 更新标题、日期范围、当前已填日期和 foot。

二板冲四板以上矩阵有独立固定流程，涉及时优先遵守该流程。

### Step 7：刷新复盘工作台

刷新命令：

```bash
python3 scripts/render_review_workbench.py
```

输出：

```text
复盘/matrices/strategy-review-workbench.html
```

成功标准：

- 工作台能识别最新每日复盘 HTML。
- 若题材简报 HTML 存在，同日期下“题材雷达”子视图可用。
- 策略矩阵 tab 能指向各矩阵文件。

### Step 8：可选本地预览

本地预览命令：

```bash
python3 -m http.server 8765
```

工作目录：项目根目录。

访问：

```text
http://127.0.0.1:8765/%E5%A4%8D%E7%9B%98/matrices/strategy-review-workbench.html
```

注意：

- 启动服务器前先检查是否已有服务器运行。
- 预览只用于人工检查，不作为生成步骤必需项。

## 6. 质量闸门

### 6.1 必须阻断的错误

以下情况必须阻断后续发布或归档：

- `check_daily_review_data.py` 输出 `INCOMPLETE`。
- `fact_market_daily` 缺目标日期。
- 核心市场字段为空。
- 涨停题材有涨停数量但没有明细。
- 日报存在占位符或“暂无/未返回”。
- 日报 Markdown 未生成。
- HTML 脚本报错。

### 6.2 可以警告但不一定阻断的情况

- 某些辅助字段暂缺但不影响核心复盘。
- 题材简报无有效主题，但日报完整。
- 个别历史日期缺少不可追溯的外部源。
- 使用 `--skip-long` 导致覆盖较弱，但用户明确接受。

这些情况必须在 summary 中标记为 `WARN`。

### 6.3 策略矩阵质量要求

策略矩阵必须满足：

- 只用 D0 数据。
- 明确候选和降级理由。
- 明确风险锚。
- 明确次日验证要点。
- 不把 hypothesis 写成 verified rule。

## 7. 输出清单

完整闭环结束后，至少应确认以下文件：

```text
market_feature_store/exports/YYYY-MM-DD-daily-review.md
market_feature_store/exports/YYYY-MM-DD-advancers-ma5.png
market_feature_store/exports/YYYY-MM-DD-theme-candidates.json
market_feature_store/exports/YYYY-MM-DD-theme-candidates.md
复盘/daily/YYYY-MM-DD/YYYY-MM-DD-daily-review.html
复盘/daily/YYYY-MM-DD/YYYY-MM-DD-market-triggered-theme-brief.html
复盘/matrices/strategy-review-workbench.html
```

如当日更新策略矩阵，还需确认：

```text
复盘/matrices/strategy1-priority-stock-matrix.html
复盘/matrices/strategy2-weak-market-matrix.html
复盘/matrices/strategy3-touch-up-rebound-matrix.html
复盘/matrices/strategy4-dual-engine-matrix.html
复盘/matrices/second-board-4plus-candidate-matrix.html
```

## 8. 建议的 machine-readable summary

未来统一 CLI 应输出类似结构：

```json
{
  "workflow": "daily-review",
  "trade_date": "YYYY-MM-DD",
  "status": "PASS",
  "steps": [
    {"name": "daily-update", "status": "PASS"},
    {"name": "daily-review", "status": "PASS"},
    {"name": "quality-gate", "status": "PASS"},
    {"name": "daily-html", "status": "PASS"},
    {"name": "theme-brief", "status": "PASS"},
    {"name": "workbench", "status": "PASS"}
  ],
  "outputs": [],
  "warnings": [],
  "next_actions": []
}
```

## 9. 常见失败和修复方式

### 9.1 CDP / fupanhui 连接失败

表现：

- 无法连接 CDP proxy。
- fupanhui API 调用失败。
- 需要登录态。

处理：

1. 确认 CDP proxy 是否运行。
2. 确认 Chrome 是否已登录 fupanhui。
3. 重新执行失败的单个同步步骤。
4. 不要伪造数据。

### 9.2 某张 fact 表缺目标日期

表现：

```text
fact_xxx: rows=0
RESULT: INCOMPLETE
```

处理：

1. 根据缺失表定位对应 sync 命令。
2. 单独补该日期。
3. 重新执行 `check_daily_review_data.py`。
4. 通过后再渲染 HTML。

### 9.3 日报有占位符

表现：

```text
日报存在占位/缺失
```

处理：

1. 不要直接编辑 Markdown 删除占位。
2. 回到数据源或 `daily_review.py` 定位字段为空的原因。
3. 补齐数据后重新生成日报。

### 9.4 题材简报 HTML 缺失

表现：

- 工作台题材雷达按钮不可用。
- `复盘/daily/YYYY-MM-DD/*theme-brief.html` 不存在。

处理：

```bash
python3 scripts/render_market_triggered_theme_brief_html.py YYYY-MM-DD
python3 scripts/render_review_workbench.py
```

### 9.5 工作台未显示最新日期

处理：

1. 确认每日复盘 HTML 是否存在于 `复盘/daily/YYYY-MM-DD/`。
2. 重新执行：

```bash
python3 scripts/render_review_workbench.py
```

3. 如仍未显示，检查文件命名是否符合：

```text
YYYY-MM-DD-daily-review.html
```

## 10. 后续产品化改造方向

### 10.1 统一 CLI

目标命令：

```bash
python3 -m intelligence.cli daily --date YYYY-MM-DD
```

封装步骤：

- `daily-update`
- `daily-review`
- `check_daily_review_data.py`
- `render_daily_review_briefing.py`
- `python3 -m intelligence.cli theme --market-triggered`
- `render_market_triggered_theme_brief_html.py`
- `render_review_workbench.py`

### 10.2 DailyReviewService

建议接口：

```text
DailyReviewService.run(date, sync=True, render_theme=True, render_workbench=True)
DailyReviewService.validate(date)
DailyReviewService.render(date)
DailyReviewService.summary(date)
```

### 10.3 统一质量输出

所有步骤统一返回：

```text
PASS / WARN / FAIL
outputs
warnings
errors
next_actions
```

## 11. 下一个 agent 接手方式

下次继续时：

1. 先执行 `git status --short && git branch --show-current`。
2. 读取 `fde/README.md`。
3. 读取本文档。
4. 如果用户要生成某日复盘，按本文档 Step 0 到 Step 8 执行。
5. 如果用户要继续产品化，下一步是写 `docs/workflows/theme-radar-workflow.md` 或设计统一 CLI。
