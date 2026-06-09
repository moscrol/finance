# 复盘目录

本目录存放本地市场复盘产物、策略矩阵和人工筛选记录。

## 目录结构

- `daily/`：按交易日归档的每日复盘 HTML 和涨家数 MA5 图片。
- `matrices/`：跨日期矩阵，包括策略1、策略2、策略3、二板晋级和申万题材矩阵。
- `templates/`：复盘模板。
- `selections/`：人工筛选、双红选择等专题记录。

## 当前重点文件

- `matrices/strategy1-priority-stock-matrix.html`：策略1每日优先个股矩阵。
- `matrices/strategy1-priority-stock-matrix.md`：策略1矩阵 Markdown 辅助稿。
- `matrices/strategy2-weak-market-matrix.html`：策略2弱市三路径观察矩阵。
- `matrices/strategy3-touch-up-rebound-matrix.html`：策略3 Touch UP 左侧反抽矩阵。
- `matrices/second-board-4plus-candidate-matrix.html`：二板冲四板以上候选矩阵。
- `matrices/strategy-review-workbench.html`：每日复盘与策略矩阵统一工作台。
- `matrices/sw-theme-matrix-2026-04-08-2026-06-05.html`：申万题材矩阵。
- `strategy3-strong-stock-rebound.md`：策略3强势股反抽策略说明。

## 生成与校验流程

- 数据完整性闸门：`python3 scripts/check_daily_review_data.py YYYY-MM-DD`。
- 生成每日复盘 Markdown：`python3 -m market_feature_store.cli daily-review --trade-date YYYY-MM-DD --output market_feature_store/exports/YYYY-MM-DD-daily-review.md --chart-output market_feature_store/exports/YYYY-MM-DD-advancers-ma5.png`。
- 渲染每日复盘 HTML：`python3 scripts/render_daily_review_briefing.py YYYY-MM-DD`，输出到 `daily/YYYY-MM-DD/`。
- 渲染统一工作台：`python3 scripts/render_review_workbench.py`。
- 二板晋级抓取：`python3 skills/limit-advance/scripts/scrape.py MM-DD --min-boards=2`，必要时用 `--json` 复核梯队数据。

## 策略矩阵回填约束

- 只写 D0 当日及以前可见数据，不用后续涨跌或晋级反推当日判断。
- 策略1、策略2、策略3和二板晋级矩阵都需要同步标题日期范围、当前已填日期和页脚说明。
- 策略3固定使用真实 UP 公式 `UP = MA26 + 0.764 × STD26`，候选池来自近端交易日单日加权涨幅 Top20 回溯，不只看目标日或区间终点榜。
- 二板晋级矩阵需要同时看市场环境、题材热度、唯一性、新高演化、理论四板是否突破前高和三板确认。

## 使用规则

- 新增某日复盘时，放入 `daily/YYYY-MM-DD/`。
- 新增跨日期矩阵时，放入 `matrices/`。
- 新增模板时，放入 `templates/`。
- 新增人工筛选记录时，放入 `selections/`。
- 不提交 `.DS_Store`、临时文件、数据库或压缩包。
